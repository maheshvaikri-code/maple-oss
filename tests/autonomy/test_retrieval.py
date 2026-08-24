"""Tests for bounded retrieval and source-bearing data contracts."""

from maple.autonomy.retrieval import (
    ChunkingPolicy,
    Document,
    InMemoryLexicalRetriever,
    SourceRef,
    TextChunker,
)


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
