"""Tests for bounded retrieval and source-bearing data contracts."""

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from maple.autonomy.retrieval import (
    DEFAULT_MAX_RETRIEVAL_TOOL_OUTPUT_BYTES,
    DEFAULT_MAX_RETRIEVAL_TOOL_RESULTS,
    AsyncDocumentConnector,
    AsyncEmbeddingProvider,
    ChunkingPolicy,
    Document,
    DocumentBatch,
    DocumentCursorCheckpoint,
    FileDocumentCursorCheckpointStore,
    FileLexicalRetriever,
    FileVectorRetriever,
    InMemoryDocumentConnectorRateLimiter,
    InMemoryDocumentCursorCheckpointStore,
    InMemoryLexicalRetriever,
    InMemoryVectorRetriever,
    RetrievalHit,
    SourceRef,
    TextChunker,
    VectorRetrievalHit,
    create_async_vector_retrieval_tool,
    create_retrieval_tool,
    create_vector_retrieval_tool,
    ingest_documents,
    ingest_documents_async,
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


@pytest.mark.asyncio
async def test_async_document_connector_ingests_cursor_pages_without_blocking_sink():
    pages = {
        None: DocumentBatch((make_document("async-doc-a"),), "cursor-1"),
        "cursor-1": DocumentBatch((make_document("async-doc-b"),), None),
    }
    calls = []
    sink_calls = []
    event_loop_thread = threading.get_ident()

    class Connector:
        async def fetch(self, cursor, *, limit):
            calls.append((cursor, limit))
            await asyncio.sleep(0)
            return Result.ok(pages[cursor])

    class Sink:
        def add_document(self, document):
            sink_calls.append((document.document_id, threading.get_ident()))
            return Result.ok([])

    result = await ingest_documents_async(
        Connector(), Sink(), batch_size=1, max_documents=10
    )

    assert result.is_ok()
    assert result.unwrap().to_dict() == {
        "documents_ingested": 2,
        "batches_fetched": 2,
        "next_cursor": None,
        "complete": True,
    }
    assert calls == [(None, 1), ("cursor-1", 1)]
    assert [document_id for document_id, _ in sink_calls] == [
        "async-doc-a",
        "async-doc-b",
    ]
    assert all(thread_id != event_loop_thread for _, thread_id in sink_calls)


@pytest.mark.asyncio
async def test_async_document_connector_runs_sync_callbacks_in_default_executor():
    event_loop_thread = threading.get_ident()
    callback_threads = []
    saved = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            document_id = "async-callback-a" if cursor is None else "async-callback-b"
            next_cursor = "next" if cursor is None else None
            return Result.ok(DocumentBatch((make_document(document_id),), next_cursor))

    class Sink:
        def add_document(self, document):
            callback_threads.append(threading.get_ident())
            return Result.ok([])

    class Checkpoint:
        def load(self):
            callback_threads.append(threading.get_ident())
            return Result.ok(DocumentCursorCheckpoint())

        def save(self, checkpoint):
            callback_threads.append(threading.get_ident())
            saved.append(checkpoint)
            return Result.ok(checkpoint)

    class Limiter:
        def allow(self):
            callback_threads.append(threading.get_ident())
            return Result.ok(None)

    result = await ingest_documents_async(
        Connector(),
        Sink(),
        checkpoint_store=Checkpoint(),
        rate_limiter=Limiter(),
    )

    assert result.is_ok()
    assert result.unwrap().complete is True
    assert [checkpoint.revision for checkpoint in saved] == [1, 2]
    assert [checkpoint.cursor for checkpoint in saved] == ["next", None]
    assert callback_threads
    assert all(thread_id != event_loop_thread for thread_id in callback_threads)


@pytest.mark.asyncio
async def test_async_document_connector_rejects_over_limit_page_without_sink_mutation():
    page = DocumentBatch(
        (make_document("async-doc-a"), make_document("async-doc-b")), "next"
    )
    sink_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            assert cursor is None
            assert limit == 1
            return Result.ok(page)

    class Sink:
        def add_document(self, document):
            sink_calls.append(document.document_id)
            return Result.ok([])

    result = await ingest_documents_async(Connector(), Sink(), max_documents=1)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_LIMIT"
    assert sink_calls == []


@pytest.mark.asyncio
async def test_async_document_connector_does_not_checkpoint_incomplete_page():
    saved = []
    sink_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            return Result.ok(
                DocumentBatch(
                    (
                        make_document("async-failure-a"),
                        make_document("async-failure-b"),
                    ),
                    "next",
                )
            )

    class Sink:
        def add_document(self, document):
            sink_calls.append(document.document_id)
            if document.document_id == "async-failure-b":
                return Result.err({"errorType": "PRIVATE_SINK", "message": "secret"})
            return Result.ok([])

    class Checkpoint:
        def load(self):
            return Result.ok(DocumentCursorCheckpoint())

        def save(self, checkpoint):
            saved.append(checkpoint)
            return Result.ok(checkpoint)

    result = await ingest_documents_async(
        Connector(), Sink(), checkpoint_store=Checkpoint()
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_SINK_ERROR"
    assert "secret" not in str(result.unwrap_err())
    assert sink_calls == ["async-failure-a", "async-failure-b"]
    assert saved == []


@pytest.mark.asyncio
async def test_async_document_connector_rejects_stalled_cursor_before_sink_write():
    sink_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((make_document("async-stalled"),), cursor))

    class Sink:
        def add_document(self, document):
            sink_calls.append(document.document_id)
            return Result.ok([])

    result = await ingest_documents_async(Connector(), Sink(), cursor="cursor-1")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_CURSOR_STALLED"
    assert sink_calls == []


@pytest.mark.asyncio
async def test_async_document_connector_rejects_duplicate_across_pages():
    document = make_document("async-duplicate")
    sink_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            next_cursor = "next" if cursor is None else None
            return Result.ok(DocumentBatch((document,), next_cursor))

    class Sink:
        def add_document(self, document):
            sink_calls.append(document.document_id)
            return Result.ok([])

    result = await ingest_documents_async(Connector(), Sink())

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_DUPLICATE_DOCUMENT"
    assert sink_calls == ["async-duplicate"]


@pytest.mark.asyncio
async def test_async_document_connector_rate_limit_stops_before_next_fetch():
    fetch_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            fetch_calls.append(cursor)
            return Result.ok(
                DocumentBatch((make_document("async-rate-limited"),), "next")
            )

    result = await ingest_documents_async(
        Connector(),
        InMemoryLexicalRetriever(),
        max_batches=2,
        rate_limiter=InMemoryDocumentConnectorRateLimiter(
            max_calls=1, window_seconds=60.0
        ),
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_RATE_LIMITED"
    assert fetch_calls == [None]


@pytest.mark.asyncio
async def test_async_document_connector_reports_checkpoint_save_failure():
    saved = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((make_document("async-checkpoint"),), None))

    class Checkpoint:
        def load(self):
            return Result.ok(DocumentCursorCheckpoint())

        def save(self, checkpoint):
            saved.append(checkpoint)
            return Result.err({"errorType": "PRIVATE_CHECKPOINT", "message": "secret"})

    result = await ingest_documents_async(
        Connector(), InMemoryLexicalRetriever(), checkpoint_store=Checkpoint()
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CHECKPOINT_SAVE_ERROR"
    assert "secret" not in str(result.unwrap_err())
    assert len(saved) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
async def test_async_document_connector_redacts_connector_failures(mode):
    class Connector:
        async def fetch(self, cursor, *, limit):
            if mode == "raises":
                raise RuntimeError("private async connector path")
            if mode == "non_result":
                return {"private": "async payload"}
            return Result.err(
                {"errorType": "PRIVATE_ASYNC_CONNECTOR", "message": "secret"}
            )

    result = await ingest_documents_async(Connector(), InMemoryLexicalRetriever())

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_CONNECTOR_ERROR"
    assert "private async connector path" not in str(result.unwrap_err())
    assert "async payload" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())


@pytest.mark.asyncio
async def test_async_document_connector_redacts_sink_failure():
    class Connector:
        async def fetch(self, cursor, *, limit):
            return Result.ok(DocumentBatch((make_document("async-sink"),), None))

    class Sink:
        def add_document(self, document):
            raise RuntimeError("private async sink path")

    result = await ingest_documents_async(Connector(), Sink())

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_SINK_ERROR"
    assert "private async sink path" not in str(result.unwrap_err())


@pytest.mark.asyncio
async def test_async_document_connector_preserves_task_cancellation():
    started = asyncio.Event()
    release = asyncio.Event()
    sink_calls = []

    class Connector:
        async def fetch(self, cursor, *, limit):
            started.set()
            await release.wait()
            return Result.ok(DocumentBatch((make_document("cancelled"),), None))

    class Sink:
        def add_document(self, document):
            sink_calls.append(document.document_id)
            return Result.ok([])

    task = asyncio.create_task(ingest_documents_async(Connector(), Sink()))
    await asyncio.wait_for(started.wait(), timeout=1.0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert sink_calls == []


def test_async_document_connector_is_publicly_exported():
    from maple import AsyncDocumentConnector as public_connector
    from maple import ingest_documents_async as public_ingest

    assert public_connector is AsyncDocumentConnector
    assert public_ingest is ingest_documents_async


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


def test_retrieval_tool_returns_bounded_source_citations_without_metadata():
    retriever = InMemoryLexicalRetriever()
    retriever.add_document(
        Document(
            document_id="tool-doc",
            text="MAPLE provides resource-aware orchestration.",
            source=SourceRef(
                uri="https://example.invalid/maple",
                title="MAPLE Guide",
                metadata={"private": "omit"},
            ),
            metadata={"private": "omit"},
        )
    )

    tool = create_retrieval_tool(retriever, max_top_k=3)
    result = tool.execute(query="resource orchestration", top_k=1)

    assert result.is_ok()
    assert tool.requires_approval is False
    assert tool.tags == ["retrieval", "read-only"]
    hit = result.unwrap()["hits"][0]
    assert hit["document_id"] == "tool-doc"
    assert hit["source"] == {
        "uri": "https://example.invalid/maple",
        "title": "MAPLE Guide",
    }
    assert "metadata" not in hit
    assert hit["text"] == "MAPLE provides resource-aware orchestration."
    assert hit["matched_terms"] == ["orchestration", "resource"]


def test_retrieval_tool_configuration_is_bounded():
    retriever = InMemoryLexicalRetriever()

    assert DEFAULT_MAX_RETRIEVAL_TOOL_RESULTS == 5
    assert DEFAULT_MAX_RETRIEVAL_TOOL_OUTPUT_BYTES == 256 * 1024
    with pytest.raises(TypeError, match="retriever"):
        create_retrieval_tool(object())
    with pytest.raises(ValueError, match="name"):
        create_retrieval_tool(retriever, name="bad\nname")
    with pytest.raises(ValueError, match="description"):
        create_retrieval_tool(retriever, description="")
    with pytest.raises(ValueError, match="max_top_k"):
        create_retrieval_tool(retriever, max_top_k=101)
    with pytest.raises(ValueError, match="max_output_bytes"):
        create_retrieval_tool(retriever, max_output_bytes=1023)
    with pytest.raises(ValueError, match="requires_approval"):
        create_retrieval_tool(retriever, requires_approval=1)


def test_retrieval_tool_rejects_invalid_queries_and_top_k():
    tool = create_retrieval_tool(InMemoryLexicalRetriever(), max_top_k=2)

    empty = tool.execute(query="   ")
    control = tool.execute(query="bad\nquery")
    invalid_top_k = tool.execute(query="maple", top_k=3)
    boolean_top_k = tool.execute(query="maple", top_k=True)

    assert empty.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_QUERY_INVALID"
    assert control.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_QUERY_INVALID"
    assert invalid_top_k.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
    assert boolean_top_k.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"


def test_retrieval_tool_rejects_malformed_hits_and_duplicate_chunks():
    chunk = TextChunker().chunk(make_document("tool-boundary")).unwrap()[0]

    class Backend:
        def __init__(self, hits):
            self.hits = hits

        def search(self, query, *, top_k=5):
            return Result.ok(self.hits)

    invalid_score = create_retrieval_tool(
        Backend([RetrievalHit(chunk, float("nan"), ())])
    ).execute(query="maple")
    huge_score = create_retrieval_tool(
        Backend([RetrievalHit(chunk, 10**10_000, ())])
    ).execute(query="maple")
    duplicate = create_retrieval_tool(
        Backend([RetrievalHit(chunk, 1.0, ()), RetrievalHit(chunk, 1.0, ())])
    ).execute(query="maple", top_k=2)
    too_many = create_retrieval_tool(
        Backend([RetrievalHit(chunk, 1.0, ()), RetrievalHit(chunk, 0.5, ())])
    ).execute(query="maple", top_k=1)

    assert invalid_score.unwrap_err()["errorType"] == ("RETRIEVAL_TOOL_RESULT_INVALID")
    assert huge_score.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_RESULT_INVALID"
    assert duplicate.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_RESULT_INVALID"
    assert too_many.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_RESULT_INVALID"


def test_retrieval_tool_rejects_oversized_output_without_partial_hits():
    retriever = InMemoryLexicalRetriever(
        chunker=TextChunker(ChunkingPolicy(max_chars=2_048, overlap_chars=100))
    )
    retriever.add_document(make_document("large-tool", " ".join(["maple"] * 300)))
    tool = create_retrieval_tool(retriever, max_output_bytes=1_024)

    result = tool.execute(query="maple", top_k=1)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_OUTPUT_TOO_LARGE"
    assert "hits" not in result.unwrap_err()


@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
def test_retrieval_tool_redacts_backend_failures(mode):
    class Backend:
        def search(self, query, *, top_k=5):
            if mode == "raises":
                raise RuntimeError("private-path-secret")
            if mode == "non_result":
                return {"private": "payload"}
            return Result.err(
                {"errorType": "PRIVATE_BACKEND_ERROR", "message": "secret"}
            )

    result = create_retrieval_tool(Backend()).execute(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert "private-path-secret" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())
    assert "payload" not in str(result.unwrap_err())


def test_vector_retrieval_tool_delegates_host_embedding_and_returns_citations():
    retriever = InMemoryVectorRetriever()
    retriever.add_document(
        Document(
            document_id="vector-tool-doc",
            text="MAPLE vector retrieval returns grounded source citations.",
            source=SourceRef(
                uri="https://example.invalid/vector",
                title="Vector Guide",
                metadata={"private": "omit"},
            ),
            metadata={"private": "omit"},
        ),
        [(1.0, 0.0)],
    )

    class Provider:
        def __init__(self):
            self.queries = []

        def embed(self, text):
            self.queries.append(text)
            return Result.ok((1.0, 0.0))

    provider = Provider()
    tool = create_vector_retrieval_tool(
        retriever,
        provider,
        max_top_k=2,
        requires_approval=True,
    )
    result = tool.execute(query="source citations", top_k=1)

    assert result.is_ok()
    assert provider.queries == ["source citations"]
    assert tool.requires_approval is True
    assert tool.tags == ["retrieval", "read-only"]
    assert (
        tool.parameters["properties"]["query"]["description"]
        == "The bounded vector search query."
    )
    hit = result.unwrap()["hits"][0]
    assert hit["document_id"] == "vector-tool-doc"
    assert hit["source"] == {
        "uri": "https://example.invalid/vector",
        "title": "Vector Guide",
    }
    assert hit["matched_terms"] == []
    assert "metadata" not in hit
    assert "embedding" not in hit

    from maple import create_vector_retrieval_tool as public_factory

    assert public_factory is create_vector_retrieval_tool


def test_vector_retrieval_tool_configuration_is_bounded():
    retriever = InMemoryVectorRetriever()

    class Provider:
        def embed(self, text):
            return Result.ok((1.0, 0.0))

    provider = Provider()
    with pytest.raises(TypeError, match="vector_retriever"):
        create_vector_retrieval_tool(object(), provider)
    with pytest.raises(TypeError, match="embedding_provider"):
        create_vector_retrieval_tool(retriever, object())
    with pytest.raises(ValueError, match="name"):
        create_vector_retrieval_tool(retriever, provider, name="bad\nname")
    with pytest.raises(ValueError, match="max_top_k"):
        create_vector_retrieval_tool(retriever, provider, max_top_k=101)
    with pytest.raises(ValueError, match="max_output_bytes"):
        create_vector_retrieval_tool(retriever, provider, max_output_bytes=1023)
    with pytest.raises(ValueError, match="requires_approval"):
        create_vector_retrieval_tool(retriever, provider, requires_approval=1)


@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
def test_vector_retrieval_tool_redacts_provider_failures(mode):
    class Provider:
        def embed(self, text):
            if mode == "raises":
                raise RuntimeError("provider-secret-path")
            if mode == "non_result":
                return {"private": "vector-payload"}
            return Result.err(
                {"errorType": "PRIVATE_PROVIDER_ERROR", "message": "secret"}
            )

    result = create_vector_retrieval_tool(
        InMemoryVectorRetriever(), Provider()
    ).execute(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert "provider-secret-path" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())
    assert "vector-payload" not in str(result.unwrap_err())


@pytest.mark.parametrize("vector", [(), (float("nan"), 0.0), object()])
def test_vector_retrieval_tool_rejects_invalid_provider_vectors(vector):
    class Provider:
        def embed(self, text):
            return Result.ok(vector)

    class Backend:
        def __init__(self):
            self.calls = 0

        def search(self, query_vector, *, top_k=5):
            self.calls += 1
            return Result.ok([])

    backend = Backend()
    result = create_vector_retrieval_tool(backend, Provider()).execute(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert backend.calls == 0


@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
def test_vector_retrieval_tool_redacts_vector_backend_failures(mode):
    class Provider:
        def embed(self, text):
            return Result.ok((1.0, 0.0))

    class Backend:
        def search(self, query_vector, *, top_k=5):
            if mode == "raises":
                raise RuntimeError("backend-private-path")
            if mode == "non_result":
                return {"private": "backend-payload"}
            return Result.err(
                {"errorType": "PRIVATE_VECTOR_ERROR", "message": "secret"}
            )

    result = create_vector_retrieval_tool(Backend(), Provider()).execute(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert "backend-private-path" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())
    assert "backend-payload" not in str(result.unwrap_err())


def test_vector_retrieval_tool_reuses_bounded_result_validation():
    chunk = TextChunker().chunk(make_document("vector-tool-boundary")).unwrap()[0]

    class Provider:
        def embed(self, text):
            return Result.ok((1.0, 0.0))

    class Backend:
        def __init__(self, hits):
            self.hits = hits

        def search(self, query_vector, *, top_k=5):
            return Result.ok(self.hits)

    invalid_score = create_vector_retrieval_tool(
        Backend([VectorRetrievalHit(chunk, float("nan"))]), Provider()
    ).execute(query="maple")
    duplicate = create_vector_retrieval_tool(
        Backend(
            [
                VectorRetrievalHit(chunk, 1.0),
                VectorRetrievalHit(chunk, 0.5),
            ]
        ),
        Provider(),
    ).execute(query="maple", top_k=2)
    invalid_hit = create_vector_retrieval_tool(Backend([object()]), Provider()).execute(
        query="maple"
    )

    assert invalid_score.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_RESULT_INVALID"
    assert duplicate.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_RESULT_INVALID"
    assert invalid_hit.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"


def test_vector_retrieval_tool_rejects_oversized_output_without_partial_hits():
    retriever = InMemoryVectorRetriever(
        chunker=TextChunker(ChunkingPolicy(max_chars=2_048, overlap_chars=100))
    )
    retriever.add_document(
        make_document("large-vector-tool", " ".join(["maple"] * 300)),
        [(1.0, 0.0)],
    )

    class Provider:
        def embed(self, text):
            return Result.ok((1.0, 0.0))

    result = create_vector_retrieval_tool(
        retriever, Provider(), max_output_bytes=1_024
    ).execute(query="maple", top_k=1)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_OUTPUT_TOO_LARGE"
    assert "hits" not in result.unwrap_err()


@pytest.mark.asyncio
async def test_async_vector_retrieval_tool_delegates_without_blocking_event_loop():
    retriever = InMemoryVectorRetriever()
    retriever.add_document(
        make_document(
            "async-vector-tool",
            "MAPLE async vector retrieval returns source citations.",
        ),
        [(1.0, 0.0)],
    )

    class Provider:
        def __init__(self):
            self.queries = []

        async def embed(self, text):
            self.queries.append(text)
            await asyncio.sleep(0)
            return Result.ok((1.0, 0.0))

    class Backend:
        def __init__(self, delegate):
            self.delegate = delegate
            self.thread_id = None

        def search(self, query_vector, *, top_k=5):
            self.thread_id = threading.get_ident()
            return self.delegate.search(query_vector, top_k=top_k)

    provider = Provider()
    backend = Backend(retriever)
    tool = create_async_vector_retrieval_tool(backend, provider, max_top_k=2)
    event_loop_thread = threading.get_ident()

    result = await tool.execute_async(query="source citations", top_k=1)

    assert result.is_ok()
    assert provider.queries == ["source citations"]
    assert backend.thread_id is not None
    assert backend.thread_id != event_loop_thread
    hit = result.unwrap()["hits"][0]
    assert hit["document_id"] == "async-vector-tool"
    assert hit["matched_terms"] == []
    assert "embedding" not in hit
    from maple import AsyncEmbeddingProvider as public_provider_protocol

    assert public_provider_protocol is AsyncEmbeddingProvider


@pytest.mark.asyncio
async def test_async_vector_retrieval_tool_is_async_only_and_validates_before_provider():
    calls = []

    class Provider:
        async def embed(self, text):
            calls.append(text)
            return Result.ok((1.0, 0.0))

    tool = create_async_vector_retrieval_tool(
        InMemoryVectorRetriever(), Provider(), max_top_k=2
    )
    sync_result = tool.execute(query="maple")
    invalid_query = await tool.execute_async(query="bad\nquery")
    invalid_top_k = await tool.execute_async(query="maple", top_k=3)

    assert sync_result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_ASYNC_REQUIRED"
    assert invalid_query.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_QUERY_INVALID"
    assert invalid_top_k.unwrap_err()["errorType"] == "TOOL_INPUT_INVALID"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
async def test_async_vector_retrieval_tool_redacts_provider_failures(mode):
    class Provider:
        async def embed(self, text):
            if mode == "raises":
                raise RuntimeError("async-provider-secret")
            if mode == "non_result":
                return {"private": "async-vector-payload"}
            return Result.err(
                {"errorType": "PRIVATE_ASYNC_PROVIDER", "message": "secret"}
            )

    result = await create_async_vector_retrieval_tool(
        InMemoryVectorRetriever(), Provider()
    ).execute_async(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert "async-provider-secret" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())
    assert "async-vector-payload" not in str(result.unwrap_err())


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["raises", "non_result", "error_result"])
async def test_async_vector_retrieval_tool_redacts_backend_failures(mode):
    class Provider:
        async def embed(self, text):
            return Result.ok((1.0, 0.0))

    class Backend:
        def search(self, query_vector, *, top_k=5):
            if mode == "raises":
                raise RuntimeError("async-backend-private")
            if mode == "non_result":
                return {"private": "async-backend-payload"}
            return Result.err(
                {"errorType": "PRIVATE_ASYNC_BACKEND", "message": "secret"}
            )

    result = await create_async_vector_retrieval_tool(
        Backend(), Provider()
    ).execute_async(query="maple")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert "async-backend-private" not in str(result.unwrap_err())
    assert "secret" not in str(result.unwrap_err())
    assert "async-backend-payload" not in str(result.unwrap_err())


@pytest.mark.asyncio
async def test_async_vector_retrieval_tool_rejects_invalid_vectors_and_oversized_output():
    calls = []

    class Provider:
        async def embed(self, text):
            return Result.ok((float("nan"), 0.0))

    class Backend:
        def search(self, query_vector, *, top_k=5):
            calls.append(query_vector)
            return Result.ok([])

    invalid = await create_async_vector_retrieval_tool(
        Backend(), Provider()
    ).execute_async(query="maple")
    assert invalid.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_BACKEND_ERROR"
    assert calls == []

    retriever = InMemoryVectorRetriever(
        chunker=TextChunker(ChunkingPolicy(max_chars=2_048, overlap_chars=100))
    )
    retriever.add_document(
        make_document("large-async-vector-tool", " ".join(["maple"] * 300)),
        [(1.0, 0.0)],
    )

    class ValidProvider:
        async def embed(self, text):
            return Result.ok((1.0, 0.0))

    oversized = await create_async_vector_retrieval_tool(
        retriever,
        ValidProvider(),
        max_output_bytes=1_024,
    ).execute_async(query="maple", top_k=1)

    assert oversized.unwrap_err()["errorType"] == "RETRIEVAL_TOOL_OUTPUT_TOO_LARGE"
    assert "hits" not in oversized.unwrap_err()


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

    index_path.write_text(
        json.dumps({"version": True, "documents": []}), encoding="utf-8"
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
