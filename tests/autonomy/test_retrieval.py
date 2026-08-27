"""Tests for bounded retrieval and source-bearing data contracts."""

from maple.autonomy.retrieval import (
    ChunkingPolicy,
    Document,
    InMemoryLexicalRetriever,
    InMemoryVectorRetriever,
    RetrievalHit,
    SourceRef,
    TextChunker,
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
