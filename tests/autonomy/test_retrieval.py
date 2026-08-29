"""Tests for bounded retrieval and source-bearing data contracts."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from maple.autonomy.retrieval import (
    ChunkingPolicy,
    Document,
    DocumentBatch,
    DocumentCursorCheckpoint,
    FileLexicalRetriever,
    FileVectorRetriever,
    FileDocumentCursorCheckpointStore,
    InMemoryDocumentConnectorRateLimiter,
    InMemoryDocumentCursorCheckpointStore,
    InMemoryLexicalRetriever,
    InMemoryVectorRetriever,
    RetrievalHit,
    SourceRef,
    TextChunker,
    ingest_documents,
    rerank_hits,
)
from maple.core.result import Result


def make_document(document_id="doc-1", text="MAPLE agent orchestration uses resources"):
    return Document(
        document_id=document_id,
        text=text,
        source=SourceRef(uri=f"memory://{document_id}", title="Example"),
        metadata={"kind": "test"},
    )


def test_chunker_preserves_source_and_character_offsets():
    document = make_document(text="alpha beta gamma delta epsilon zeta eta theta")
    chunker = TextChunker(ChunkingPolicy(max_chars=20, overlap_chars=5, max_chunks=10))

    result = chunker.chunk(document)

    assert result.is_ok()
    chunks = result.unwrap()
    assert len(chunks) > 1
    assert all(chunk.source.uri == document.source.uri for chunk in chunks)
    assert all(
        document.text[chunk.start_char : chunk.end_char] == chunk.text
        for chunk in chunks
    )
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_chunker_rejects_document_and_chunk_limits():
    oversized = TextChunker(
        ChunkingPolicy(max_chars=10, overlap_chars=1, max_document_bytes=5)
    ).chunk(make_document(text="this is too large"))
    too_many = TextChunker(
        ChunkingPolicy(max_chars=5, overlap_chars=1, max_chunks=1)
    ).chunk(make_document(text="one two three four five six"))

    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "RETRIEVAL_DOCUMENT_TOO_LARGE"
    assert too_many.is_err()
    assert too_many.unwrap_err()["errorType"] == "RETRIEVAL_CHUNK_LIMIT"


def test_document_connector_ingests_cursor_pages_into_a_bounded_sink():
    pages = {
        None: DocumentBatch((make_document("doc-a"),), "cursor-1"),
        "cursor-1": DocumentBatch((make_document("doc-b"),), None),
    }
    calls = []

    class Connector:
        def fetch(self, cursor, *, limit):
            calls.append((cursor, limit))
            return Result.ok(pages[cursor])

    sink = InMemoryLexicalRetriever()
    result = ingest_documents(Connector(), sink, batch_size=1, max_documents=10)

    assert result.is_ok()
    assert result.unwrap().to_dict() == {
        "documents_ingested": 2,
        "batches_fetched": 2,
        "next_cursor": None,
        "complete": True,
    }
    assert calls == [(None, 1), ("cursor-1", 1)]
    assert sink.stats()["documents"] == 2


def test_document_connector_returns_resume_cursor_at_batch_quota():
    calls = []

    class Connector:
        def fetch(self, cursor, *, limit):
            calls.append((cursor, limit))
            document_id = "doc-a" if cursor is None else "doc-b"
            next_cursor = "next" if cursor is None else "last"
            return Result.ok(DocumentBatch((make_document(document_id),), next_cursor))

    result = ingest_documents(
        Connector(),
        InMemoryLexicalRetriever(),
        batch_size=10,
        max_documents=10,
        max_batches=1,
    )

    assert result.is_ok()
    assert result.unwrap().to_dict() == {
        "documents_ingested": 1,
        "batches_fetched": 1,
        "next_cursor": "next",
        "complete": False,
    }
    assert calls == [(None, 10)]


def test_document_connector_resumes_from_in_memory_checkpoint():
    pages = {
        None: DocumentBatch((make_document("doc-a"),), "cursor-1"),
        "cursor-1": DocumentBatch((make_document("doc-b"),), None),
    }
    calls = []

    class Connector:
        def fetch(self, cursor, *, limit):
            calls.append((cursor, limit))
            return Result.ok(pages[cursor])

    checkpoint = InMemoryDocumentCursorCheckpointStore()
    first = ingest_documents(
        Connector(),
        InMemoryLexicalRetriever(),
        batch_size=10,
        max_batches=1,
        checkpoint_store=checkpoint,
    )
    second = ingest_documents(
        Connector(),
        InMemoryLexicalRetriever(),
        batch_size=10,
        checkpoint_store=checkpoint,
    )

    assert first.is_ok()
    assert first.unwrap().to_dict() == {
        "documents_ingested": 1,
        "batches_fetched": 1,
        "next_cursor": "cursor-1",
        "complete": False,
    }
    assert second.is_ok()
    assert second.unwrap().to_dict() == {
        "documents_ingested": 1,
        "batches_fetched": 1,
        "next_cursor": None,
        "complete": True,
    }
    assert calls == [(None, 10), ("cursor-1", 10)]
    assert checkpoint.load().unwrap() == DocumentCursorCheckpoint(
        complete=True, revision=2
    )


def test_file_document_checkpoint_survives_restart_and_fences_stale_writes(
    tmp_path,
):
    store = FileDocumentCursorCheckpointStore(tmp_path)
    saved = store.save(DocumentCursorCheckpoint(cursor="next", revision=1))
    restarted = FileDocumentCursorCheckpointStore(tmp_path)

    assert saved.is_ok()
    assert restarted.load().unwrap() == DocumentCursorCheckpoint(
        cursor="next", revision=1
    )
    stale = restarted.save(DocumentCursorCheckpoint(cursor="other", revision=1))
    assert stale.is_err()
    assert stale.unwrap_err()["errorType"] == "RETRIEVAL_CHECKPOINT_CONFLICT"
    cleared = restarted.clear()
    assert cleared.is_ok()
    assert cleared.unwrap() == DocumentCursorCheckpoint(revision=2)


def test_completed_document_checkpoint_short_circuits_connector():
    class Connector:
        def fetch(self, cursor, *, limit):
            raise AssertionError("completed streams must not fetch")

    result = ingest_documents(
        Connector(),
        InMemoryLexicalRetriever(),
        checkpoint_store=InMemoryDocumentCursorCheckpointStore(
            DocumentCursorCheckpoint(complete=True, revision=4)
        ),
    )

    assert result.is_ok()
    assert result.unwrap().to_dict() == {
        "documents_ingested": 0,
        "batches_fetched": 0,
        "next_cursor": None,
        "complete": True,
    }


def test_document_checkpoint_load_fails_closed_on_corrupt_file(tmp_path):
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text("{not-json", encoding="utf-8")

    class Connector:
        def fetch(self, cursor, *, limit):
            raise AssertionError("corrupt checkpoints must stop before fetch")

    result = ingest_documents(
        Connector(),
        InMemoryLexicalRetriever(),
        checkpoint_store=FileDocumentCursorCheckpointStore(tmp_path),
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CHECKPOINT_LOAD_ERROR"


def test_document_checkpoint_rejects_explicit_cursor_source_of_truth():
    result = ingest_documents(
        object(),
        InMemoryLexicalRetriever(),
        cursor="explicit",
        checkpoint_store=InMemoryDocumentCursorCheckpointStore(),
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CHECKPOINT_INPUT_INVALID"


def test_document_connector_rate_limiter_denies_until_window_expires():
    now = [0.0]
    limiter = InMemoryDocumentConnectorRateLimiter(
        max_calls=2, window_seconds=10.0, clock=lambda: now[0]
    )

    assert limiter.allow().is_ok()
    assert limiter.allow().is_ok()
    denied = limiter.allow()
    now[0] = 10.0
    allowed_after_window = limiter.allow()

    assert denied.is_err()
    assert denied.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_RATE_LIMITED"
    assert denied.unwrap_err()["details"]["retry_after_seconds"] == 10.0
    assert allowed_after_window.is_ok()


def test_document_connector_rate_limit_fails_before_next_fetch():
    calls = []

    class Connector:
        def fetch(self, cursor, *, limit):
            calls.append(cursor)
            return Result.ok(DocumentBatch((make_document("doc-a"),), "next"))

    sink = InMemoryLexicalRetriever()
    result = ingest_documents(
        Connector(),
        sink,
        max_batches=2,
        rate_limiter=InMemoryDocumentConnectorRateLimiter(
            max_calls=1, window_seconds=60.0
        ),
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_RATE_LIMITED"
    assert calls == [None]
    assert sink.stats()["documents"] == 1


def test_document_connector_rate_limiter_redacts_host_failures():
    class Connector:
        def fetch(self, cursor, *, limit):
            raise AssertionError("fetch must not run")

    class FailedLimiter:
        def allow(self):
            return Result.err(
                {"errorType": "PRIVATE_LIMITER_ERROR", "message": "secret"}
            )

    result = ingest_documents(
        Connector(), InMemoryLexicalRetriever(), rate_limiter=FailedLimiter()
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == (
        "RETRIEVAL_CONNECTOR_RATE_LIMITER_ERROR"
    )
    assert "secret" not in str(result.unwrap_err())


def test_document_connector_rejects_over_limit_pages_without_sink_mutation():
    page = DocumentBatch((make_document("doc-a"), make_document("doc-b")), "next")

    class Connector:
        def fetch(self, cursor, *, limit):
            assert cursor is None
            assert limit == 1
            return Result.ok(page)

    sink = InMemoryLexicalRetriever()
    result = ingest_documents(Connector(), sink, max_documents=1)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_LIMIT"
    assert sink.stats() == {"documents": 0, "chunks": 0, "terms": 0}


def test_document_connector_fails_closed_on_stalled_cursor_and_errors():
    document = make_document("doc-a")

    class StalledConnector:
        def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((document,), cursor))

    class RaisingConnector:
        def fetch(self, cursor, *, limit):
            raise RuntimeError("private connector detail")

    class ErrorConnector:
        def fetch(self, cursor, *, limit):
            return Result.err(
                {"errorType": "PRIVATE_CONNECTOR_ERROR", "message": "secret"}
            )

    class RaisingSink:
        def add_document(self, document):
            raise RuntimeError("private sink detail")

    class SinglePageConnector:
        def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((document,), None))

    stalled = ingest_documents(
        StalledConnector(), InMemoryLexicalRetriever(), cursor="cursor-1"
    )
    failed = ingest_documents(RaisingConnector(), InMemoryLexicalRetriever())
    error_result = ingest_documents(ErrorConnector(), InMemoryLexicalRetriever())
    failed_sink = ingest_documents(SinglePageConnector(), RaisingSink())

    assert stalled.is_err()
    assert stalled.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_CURSOR_STALLED"
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_ERROR"
    assert "private connector detail" not in str(failed.unwrap_err())
    assert error_result.is_err()
    assert error_result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_ERROR"
    assert "secret" not in str(error_result.unwrap_err())
    assert failed_sink.is_err()
    assert failed_sink.unwrap_err()["errorType"] == "RETRIEVAL_SINK_ERROR"
    assert "private sink detail" not in str(failed_sink.unwrap_err())


def test_document_connector_rejects_empty_advancing_pages():
    class Connector:
        def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((), "next"))

    result = ingest_documents(Connector(), InMemoryLexicalRetriever())

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_INVALID"


def test_document_connector_rejects_repeated_ids_before_second_sink_write():
    document = make_document("doc-a")
    calls = []

    class Connector:
        def fetch(self, cursor, *, limit):
            calls.append(cursor)
            return Result.ok(
                DocumentBatch((document,), "next" if cursor is None else None)
            )

    sink = InMemoryLexicalRetriever()
    first = ingest_documents(Connector(), sink, max_batches=2)

    assert first.is_err()
    assert first.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_DUPLICATE_DOCUMENT"
    assert calls == [None, "next"]
    assert sink.stats()["documents"] == 1


def test_retriever_returns_ranked_hits_with_citations():
    retriever = InMemoryLexicalRetriever()
    retriever.add_document(make_document())
    retriever.add_document(
        make_document(
            "doc-2",
            "A completely unrelated note about cooking and gardens",
        )
    )

    result = retriever.search("agent resources", top_k=3)

    assert result.is_ok()
    hits = result.unwrap()
    assert hits
    assert hits[0].chunk.document_id == "doc-1"
    assert hits[0].chunk.source.uri == "memory://doc-1"
    assert set(hits[0].matched_terms) == {"agent", "resources"}
    assert hits[0].score > 0


def test_reranker_reorders_lexical_hits_and_preserves_original_scores():
    retriever = InMemoryLexicalRetriever()
    retriever.add_document(make_document("doc-a", "agent resources"))
    retriever.add_document(make_document("doc-b", "agent resources"))
    candidates = retriever.search("agent resources", top_k=2).unwrap()

    class HostReranker:
        def score(self, query, chunk):
            assert query == "agent resources"
            return Result.ok(1.0 if chunk.document_id == "doc-b" else 0.5)

    result = rerank_hits("agent resources", candidates, HostReranker(), top_k=2)

    assert result.is_ok()
    reranked = result.unwrap()
    assert [hit.chunk.document_id for hit in reranked] == ["doc-b", "doc-a"]
    assert [hit.score for hit in reranked] == [1.0, 0.5]
    assert all(hit.original_score > 0 for hit in reranked)
    assert all(hit.chunk.source.uri.startswith("memory://") for hit in reranked)


def test_reranker_bounds_candidates_and_redacts_callback_failures():
    chunk = TextChunker().chunk(make_document()).unwrap()[0]
    candidate = RetrievalHit(
        chunk=chunk,
        score=1.0,
        matched_terms=(),
    )

    class RaisingReranker:
        def score(self, query, chunk):
            raise RuntimeError("private reranking detail")

    invalid = rerank_hits("agent", [object()], RaisingReranker())
    invalid_bound = rerank_hits(
        "agent", [candidate], RaisingReranker(), max_candidates=101
    )
    too_many = rerank_hits(
        "agent", [candidate, candidate], RaisingReranker(), max_candidates=1
    )
    failed = rerank_hits("agent", [candidate], RaisingReranker())

    assert invalid.is_err()
    assert invalid.unwrap_err()["errorType"] == "RETRIEVAL_CANDIDATE_INVALID"
    assert invalid_bound.is_err()
    assert invalid_bound.unwrap_err()["errorType"] == "RETRIEVAL_RERANK_CONFIG_INVALID"
    assert too_many.is_err()
    assert too_many.unwrap_err()["errorType"] == "RETRIEVAL_RERANK_LIMIT"
    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RETRIEVAL_RERANKER_ERROR"
    assert "private reranking detail" not in str(failed.unwrap_err())


def test_retriever_search_is_bounded_and_empty_queries_fail():
    retriever = InMemoryLexicalRetriever(max_query_bytes=5, max_results=2)
    empty = retriever.search("   ")
    oversized = retriever.search("too long")
    invalid_top_k = retriever.search("agent", top_k=3)

    assert empty.is_err()
    assert empty.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_INVALID"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_TOO_LARGE"
    assert invalid_top_k.is_err()
    assert invalid_top_k.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_INVALID"


def test_file_lexical_retriever_rejects_invalid_configuration(tmp_path):
    with pytest.raises(ValueError, match="max_bytes"):
        FileLexicalRetriever(tmp_path, max_bytes=511)
    with pytest.raises(ValueError, match="max_documents"):
        FileLexicalRetriever(tmp_path, max_documents=0)
    with pytest.raises(TypeError, match="chunker"):
        FileLexicalRetriever(tmp_path, chunker=object())


def test_file_lexical_retriever_rejects_corrupt_or_oversized_state(tmp_path):
    index_path = tmp_path / "lexical-index.json"
    index_path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path)

    index_path.write_bytes(b"x" * 513)
    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path, max_bytes=512)

    index_path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path)

    index_path.write_text(
        json.dumps(
            {
                "version": 1,
                "chunking_policy": {
                    "max_chars": 1200,
                    "overlap_chars": 200,
                    "max_chunks": 10000,
                    "max_document_bytes": 5 * 1024 * 1024,
                },
                "documents": [{"source": {}}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path)

    index_path.write_text(
        json.dumps({"version": 99, "documents": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path)


def test_file_lexical_retriever_persists_and_reloads_documents(tmp_path):
    first = FileLexicalRetriever(tmp_path)
    document = make_document("durable", "durable agent resources")

    added = first.add_document(document)
    second = FileLexicalRetriever(tmp_path)
    found = second.search("durable resources")

    assert added.is_ok()
    assert found.is_ok()
    assert [hit.chunk.document_id for hit in found.unwrap()] == ["durable"]
    assert found.unwrap()[0].chunk.source.uri == "memory://durable"
    assert second.stats() == {"documents": 1, "chunks": 1, "terms": 3}


def test_file_lexical_retriever_rejects_chunking_policy_mismatch(tmp_path):
    first = FileLexicalRetriever(
        tmp_path,
        chunker=TextChunker(ChunkingPolicy(max_chars=20, overlap_chars=5)),
    )
    assert first.add_document(make_document("policy")).is_ok()

    with pytest.raises(ValueError, match="state"):
        FileLexicalRetriever(tmp_path)


def test_file_lexical_retriever_remove_persists_and_is_fail_closed(
    tmp_path, monkeypatch
):
    retriever = FileLexicalRetriever(tmp_path)
    document = make_document("remove-me", "remove me from durable index")
    assert retriever.add_document(document).is_ok()
    before = retriever.path.read_bytes()

    def fail_write(_documents):
        return Result.err(
            {"errorType": "RETRIEVAL_INDEX_SAVE_ERROR", "message": "save failed"}
        )

    monkeypatch.setattr(retriever, "_write_documents_unlocked", fail_write)
    failed = retriever.remove_document(document.document_id)

    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RETRIEVAL_INDEX_SAVE_ERROR"
    assert retriever.path.read_bytes() == before
    assert retriever.search("durable index").unwrap()

    monkeypatch.undo()
    assert retriever.remove_document(document.document_id).unwrap() is True
    assert FileLexicalRetriever(tmp_path).stats() == {
        "documents": 0,
        "chunks": 0,
        "terms": 0,
    }
    assert retriever.remove_document(document.document_id).unwrap() is False


def test_file_lexical_retriever_serializes_shared_directory_mutations(tmp_path):
    first = FileLexicalRetriever(tmp_path)
    second = FileLexicalRetriever(tmp_path)
    documents = (
        make_document("parallel-a", "parallel agent alpha"),
        make_document("parallel-b", "parallel agent beta"),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda pair: pair[0].add_document(pair[1]),
                ((first, documents[0]), (second, documents[1])),
            )
        )

    fresh = FileLexicalRetriever(tmp_path)
    assert all(result.is_ok() for result in results)
    assert fresh.stats()["documents"] == 2
    assert fresh.search("alpha").unwrap()[0].chunk.document_id == "parallel-a"
    assert fresh.search("beta").unwrap()[0].chunk.document_id == "parallel-b"


def test_file_lexical_retriever_refreshes_external_updates_and_bounds_queries(
    tmp_path,
):
    first = FileLexicalRetriever(tmp_path, max_query_bytes=5, max_results=2)
    second = FileLexicalRetriever(tmp_path, max_query_bytes=5, max_results=2)
    assert first.add_document(make_document("refresh", "refreshable agent")).is_ok()

    refreshed = second.search("agent", top_k=2)
    oversized = second.search("too long", top_k=2)
    invalid_top_k = second.search("agent", top_k=3)

    assert refreshed.is_ok()
    assert refreshed.unwrap()[0].chunk.document_id == "refresh"
    assert oversized.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_TOO_LARGE"
    assert invalid_top_k.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_INVALID"


def test_file_lexical_retriever_rejects_non_json_documents_without_mutation(tmp_path):
    retriever = FileLexicalRetriever(tmp_path)
    assert retriever.add_document(make_document("stable")).is_ok()
    before = retriever.path.read_bytes()
    invalid = Document(
        document_id="invalid",
        text="not persisted",
        source=SourceRef(uri="memory://invalid"),
        metadata={"bad": object()},
    )

    result = retriever.add_document(invalid)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_NON_JSON_METADATA"
    assert retriever.path.read_bytes() == before
    assert retriever.stats()["documents"] == 1


def test_file_lexical_retriever_redacts_storage_failures(tmp_path, monkeypatch):
    retriever = FileLexicalRetriever(tmp_path)

    def raise_private_failure(_documents):
        raise RuntimeError("private-path-secret")

    monkeypatch.setattr(retriever, "_write_documents_unlocked", raise_private_failure)
    result = retriever.add_document(make_document("redacted"))

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_INDEX_ERROR"
    assert "private-path-secret" not in str(result.unwrap_err())


def test_file_vector_retriever_rejects_invalid_configuration(tmp_path):
    with pytest.raises(ValueError, match="max_bytes"):
        FileVectorRetriever(tmp_path, max_bytes=511)
    with pytest.raises(ValueError, match="max_documents"):
        FileVectorRetriever(tmp_path, max_documents=0)
    with pytest.raises(ValueError, match="max_dimensions"):
        FileVectorRetriever(tmp_path, max_dimensions=0)
    with pytest.raises(ValueError, match="lease_ttl_seconds"):
        FileVectorRetriever(tmp_path, lease_ttl_seconds=float("nan"))
    with pytest.raises(TypeError, match="chunker"):
        FileVectorRetriever(tmp_path, chunker=object())


def test_file_vector_retriever_rejects_corrupt_oversized_or_mismatched_state(
    tmp_path,
):
    index_path = tmp_path / "vector-index.json"
    index_path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path)

    index_path.write_bytes(b"x" * 513)
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path, max_bytes=512)

    index_path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path)

    index_path.write_text(
        json.dumps({"version": 99, "documents": []}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path)

    index_path.unlink()
    first = FileVectorRetriever(
        tmp_path,
        chunker=TextChunker(ChunkingPolicy(max_chars=20, overlap_chars=5)),
    )
    assert first.add_document(
        make_document("policy"), [(1.0, 0.0), (1.0, 0.0), (1.0, 0.0)]
    ).is_ok()
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path)


def test_file_vector_retriever_persists_and_reloads_embeddings(tmp_path):
    first = FileVectorRetriever(tmp_path)
    document = make_document("durable-vector", "durable agent resources")

    added = first.add_document(document, [(1.0, 0.0)])
    second = FileVectorRetriever(tmp_path)
    found = second.search((1.0, 0.0))

    assert added.is_ok()
    assert len(added.unwrap()) == 1
    assert found.is_ok()
    assert [hit.chunk.document_id for hit in found.unwrap()] == ["durable-vector"]
    assert found.unwrap()[0].chunk.source.uri == "memory://durable-vector"
    assert second.stats() == {"documents": 1, "vectors": 1, "dimensions": 2}
    persisted = json.loads(second.path.read_text(encoding="utf-8"))
    assert persisted["version"] == 1
    assert persisted["documents"][0]["embeddings"] == [[1.0, 0.0]]

    persisted["documents"][0]["embeddings"] = [["not-a-number", 0.0]]
    second.path.write_text(json.dumps(persisted), encoding="utf-8")
    with pytest.raises(ValueError, match="state"):
        FileVectorRetriever(tmp_path)


def test_file_vector_retriever_rejects_vector_dimension_mismatch_without_mutation(
    tmp_path,
):
    retriever = FileVectorRetriever(tmp_path)
    assert retriever.add_document(make_document("stable"), [(1.0, 0.0)]).is_ok()
    before = retriever.path.read_bytes()

    count_mismatch = retriever.add_document(make_document("count"), [])
    dimension_mismatch = retriever.add_document(
        make_document("dimension"), [(1.0, 0.0, 0.0)]
    )
    duplicate = retriever.add_document(make_document("stable"), [(1.0, 0.0)])
    huge_component = retriever.add_document(make_document("huge"), [(10**10_000, 0.0)])

    assert count_mismatch.is_err()
    assert count_mismatch.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_COUNT_MISMATCH"
    assert dimension_mismatch.is_err()
    assert (
        dimension_mismatch.unwrap_err()["errorType"]
        == "RETRIEVAL_VECTOR_DIMENSION_MISMATCH"
    )
    assert duplicate.is_err()
    assert duplicate.unwrap_err()["errorType"] == "RETRIEVAL_DUPLICATE_DOCUMENT"
    assert huge_component.is_err()
    assert huge_component.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INVALID"
    assert retriever.path.read_bytes() == before
    assert retriever.stats() == {"documents": 1, "vectors": 1, "dimensions": 2}


def test_file_vector_retriever_remove_persists_and_is_fail_closed(
    tmp_path, monkeypatch
):
    retriever = FileVectorRetriever(tmp_path)
    document = make_document("remove-me", "remove me from durable vector index")
    assert retriever.add_document(document, [(1.0, 0.0)]).is_ok()
    before = retriever.path.read_bytes()

    def fail_write(_records):
        return Result.err(
            {
                "errorType": "RETRIEVAL_VECTOR_INDEX_SAVE_ERROR",
                "message": "save failed",
            }
        )

    monkeypatch.setattr(retriever, "_write_records_unlocked", fail_write)
    failed = retriever.remove_document(document.document_id)

    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INDEX_SAVE_ERROR"
    assert retriever.path.read_bytes() == before
    assert retriever.search((1.0, 0.0)).unwrap()

    monkeypatch.undo()
    assert retriever.remove_document(document.document_id).unwrap() is True
    assert FileVectorRetriever(tmp_path).stats() == {
        "documents": 0,
        "vectors": 0,
        "dimensions": 0,
    }
    assert retriever.remove_document(document.document_id).unwrap() is False


def test_file_vector_retriever_serializes_shared_directory_mutations(tmp_path):
    first = FileVectorRetriever(tmp_path)
    second = FileVectorRetriever(tmp_path)
    documents = (
        (first, make_document("parallel-a", "parallel agent alpha")),
        (second, make_document("parallel-b", "parallel agent beta")),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda pair: pair[0].add_document(pair[1], [(1.0, 0.0)]),
                documents,
            )
        )

    fresh = FileVectorRetriever(tmp_path)
    assert all(result.is_ok() for result in results)
    assert fresh.stats() == {"documents": 2, "vectors": 2, "dimensions": 2}
    assert fresh.search((1.0, 0.0)).unwrap()[0].chunk.document_id == "parallel-a"


def test_file_vector_retriever_refreshes_external_updates_and_bounds_queries(
    tmp_path,
):
    first = FileVectorRetriever(tmp_path, max_results=2)
    second = FileVectorRetriever(tmp_path, max_results=2)
    assert first.add_document(
        make_document("refresh", "refreshable agent"), [(1.0, 0.0)]
    ).is_ok()

    refreshed = second.search((1.0, 0.0), top_k=2)
    invalid_top_k = second.search((1.0, 0.0), top_k=3)
    invalid_query = second.search((float("nan"), 0.0), top_k=2)

    assert refreshed.is_ok()
    assert refreshed.unwrap()[0].chunk.document_id == "refresh"
    assert invalid_top_k.unwrap_err()["errorType"] == "RETRIEVAL_QUERY_INVALID"
    assert invalid_query.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INVALID"


def test_file_vector_retriever_rejects_non_json_documents_and_redacts_storage_failures(
    tmp_path, monkeypatch
):
    retriever = FileVectorRetriever(tmp_path)
    assert retriever.add_document(make_document("stable"), [(1.0, 0.0)]).is_ok()
    before = retriever.path.read_bytes()
    invalid = Document(
        document_id="invalid",
        text="not persisted",
        source=SourceRef(uri="memory://invalid"),
        metadata={"bad": object()},
    )

    invalid_result = retriever.add_document(invalid, [(1.0, 0.0)])

    assert invalid_result.is_err()
    assert invalid_result.unwrap_err()["errorType"] == "RETRIEVAL_NON_JSON_METADATA"
    assert retriever.path.read_bytes() == before
    assert retriever.stats()["documents"] == 1

    def raise_private_failure(_records):
        raise RuntimeError("private-path-secret")

    monkeypatch.setattr(retriever, "_write_records_unlocked", raise_private_failure)
    failed = retriever.add_document(make_document("redacted"), [(1.0, 0.0)])

    assert failed.is_err()
    assert failed.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INDEX_ERROR"
    assert "private-path-secret" not in str(failed.unwrap_err())


def test_retriever_rejects_duplicates_and_removes_documents():
    retriever = InMemoryLexicalRetriever()
    document = make_document()
    first = retriever.add_document(document)
    duplicate = retriever.add_document(document)
    removed = retriever.remove_document(document.document_id)
    missing = retriever.remove_document(document.document_id)

    assert first.is_ok()
    assert duplicate.is_err()
    assert duplicate.unwrap_err()["errorType"] == "RETRIEVAL_DUPLICATE_DOCUMENT"
    assert removed.unwrap() is True
    assert missing.unwrap() is False
    assert retriever.stats() == {"documents": 0, "chunks": 0, "terms": 0}


def test_document_validation_rejects_non_json_metadata():
    document = Document(
        document_id="bad-metadata",
        text="value",
        source=SourceRef(uri="memory://bad"),
        metadata={"bad": object()},
    )

    result = TextChunker().chunk(document)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_NON_JSON_METADATA"


def test_vector_retriever_returns_ranked_source_bearing_hits():
    retriever = InMemoryVectorRetriever()
    first = make_document("doc-a", "agent orchestration")
    second = make_document("doc-b", "resource allocation")
    assert retriever.add_document(first, [(1.0, 0.0)]).is_ok()
    assert retriever.add_document(second, [(0.0, 1.0)]).is_ok()

    result = retriever.search((0.9, 0.1), top_k=2)

    assert result.is_ok()
    hits = result.unwrap()
    assert [hit.chunk.document_id for hit in hits] == ["doc-a", "doc-b"]
    assert hits[0].chunk.source.uri == "memory://doc-a"
    assert hits[0].score > hits[1].score
    assert retriever.stats() == {"documents": 2, "vectors": 2, "dimensions": 2}


def test_vector_retriever_rejects_count_dimension_and_nonfinite_inputs_atomically():
    retriever = InMemoryVectorRetriever()
    document = make_document("vector-boundary")

    count_mismatch = retriever.add_document(document, [])
    invalid_zero = retriever.add_document(document, [(0.0, 0.0)])
    valid = retriever.add_document(document, [(1.0, 0.0)])
    dimension_mismatch = retriever.add_document(
        make_document("vector-other"), [(1.0, 0.0, 0.0)]
    )
    invalid_query = retriever.search((float("nan"), 0.0))
    wrong_query_dimension = retriever.search((1.0,))

    assert count_mismatch.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_COUNT_MISMATCH"
    assert invalid_zero.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INVALID"
    assert valid.is_ok()
    assert dimension_mismatch.unwrap_err()["errorType"] == (
        "RETRIEVAL_VECTOR_DIMENSION_MISMATCH"
    )
    assert invalid_query.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_INVALID"
    assert wrong_query_dimension.unwrap_err()["errorType"] == (
        "RETRIEVAL_VECTOR_DIMENSION_MISMATCH"
    )
    assert retriever.stats() == {"documents": 1, "vectors": 1, "dimensions": 2}


def test_vector_retriever_tie_breaks_by_chunk_id_and_removes_documents():
    retriever = InMemoryVectorRetriever()
    retriever.add_document(make_document("doc-b"), [(1.0, 0.0)])
    retriever.add_document(make_document("doc-a"), [(1.0, 0.0)])

    tied = retriever.search((1.0, 0.0), top_k=2)
    removed = retriever.remove_document("doc-a")
    remaining = retriever.search((1.0, 0.0))

    assert [hit.chunk.document_id for hit in tied.unwrap()] == ["doc-a", "doc-b"]
    assert removed.unwrap() is True
    assert [hit.chunk.document_id for hit in remaining.unwrap()] == ["doc-b"]


def test_vector_retriever_enforces_vector_quota():
    retriever = InMemoryVectorRetriever(max_vectors=1)
    assert retriever.add_document(make_document("doc-a"), [(1.0, 0.0)]).is_ok()

    rejected = retriever.add_document(make_document("doc-b"), [(0.0, 1.0)])

    assert rejected.is_err()
    assert rejected.unwrap_err()["errorType"] == "RETRIEVAL_VECTOR_LIMIT"
    assert retriever.stats() == {"documents": 1, "vectors": 1, "dimensions": 2}
