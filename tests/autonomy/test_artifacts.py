"""Tests for bounded artifacts and non-executing code-block extraction."""

from maple.autonomy.artifacts import (
    CodeBlock,
    FileArtifactStore,
    InMemoryArtifactStore,
    extract_code_blocks,
    materialize_code_block,
)


def test_extract_code_blocks_returns_bounded_code_as_data():
    result = extract_code_blocks(
        "before\n```python\nprint('safe data')\n```\n```json\n{}\n```"
    )

    assert result.is_ok()
    blocks = result.unwrap()
    assert [(block.index, block.language) for block in blocks] == [
        (0, "python"),
        (1, "json"),
    ]
    assert blocks[0].code == "print('safe data')\n"


def test_extract_code_blocks_rejects_unclosed_and_oversized_fences():
    unclosed = extract_code_blocks("```python\nprint('never runs')\n")
    oversized = extract_code_blocks("```text\n12345\n```", max_block_bytes=4)

    assert unclosed.is_err()
    assert unclosed.unwrap_err()["errorType"] == "CODE_FENCE_UNCLOSED"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "CODE_BLOCK_TOO_LARGE"


def test_materialize_code_block_preserves_exact_bytes_and_digest():
    block = CodeBlock(index=2, language="python", code="print('data')\n")
    store = InMemoryArtifactStore()

    result = materialize_code_block(store, block)

    assert result.is_ok()
    artifact = result.unwrap()
    assert block.sha256 == artifact.sha256
    assert artifact.artifact_id == "sha256:" + block.sha256
    assert artifact.name == "code-block-2.python"
    assert artifact.media_type == "text/plain"
    assert store.get(artifact.artifact_id).unwrap() == b"print('data')\n"


def test_materialize_code_block_public_example_round_trips():
    from maple import InMemoryArtifactStore as PublicInMemoryArtifactStore
    from maple import extract_code_blocks as public_extract_code_blocks
    from maple import materialize_code_block as public_materialize_code_block

    source = "```" + "python\nprint('data only')\n" + "```"
    block = public_extract_code_blocks(source).unwrap()[0]
    store = PublicInMemoryArtifactStore()

    artifact = public_materialize_code_block(store, block).unwrap()

    assert artifact.sha256 == block.sha256
    assert store.get(artifact.artifact_id).unwrap() == b"print('data only')\n"


def test_materialize_code_block_survives_file_store_restart_without_execution(
    tmp_path,
):
    block = CodeBlock(index=0, language="python", code="open('should-not-run', 'w')")
    store = FileArtifactStore(tmp_path)

    created = materialize_code_block(store, block).unwrap()
    restarted = FileArtifactStore(tmp_path)

    assert restarted.get(created.artifact_id).unwrap() == block.code.encode("utf-8")
    assert not (tmp_path / "should-not-run").exists()


def test_materialize_code_block_rejects_invalid_bounds_and_store_without_mutation():
    oversized = CodeBlock(
        index=0,
        language="python",
        code="x" * (128 * 1024 + 1),
    )
    store = InMemoryArtifactStore()
    invalid_store = materialize_code_block(object(), CodeBlock(0, "text", "data"))
    invalid_name = materialize_code_block(
        store, CodeBlock(0, "text", "data"), name="../escape"
    )
    too_large = materialize_code_block(store, oversized)

    assert invalid_store.is_err()
    assert invalid_store.unwrap_err()["errorType"] == "CODE_ARTIFACT_STORE_INVALID"
    assert invalid_name.is_err()
    assert invalid_name.unwrap_err()["errorType"] == "CODE_ARTIFACT_NAME_INVALID"
    assert too_large.is_err()
    assert too_large.unwrap_err()["errorType"] == "CODE_BLOCK_TOO_LARGE"
    assert store.describe("sha256:" + ("0" * 64)).is_err()


def test_materialize_code_block_propagates_store_full_without_partial_mutation():
    store = InMemoryArtifactStore(max_artifact_bytes=4, max_store_bytes=4)
    first = materialize_code_block(store, CodeBlock(0, "text", "1234")).unwrap()
    second = CodeBlock(1, "text", "5")

    full = materialize_code_block(store, second)

    assert full.is_err()
    assert full.unwrap_err()["errorType"] == "ARTIFACT_STORE_FULL"
    assert store.get(first.artifact_id).unwrap() == b"1234"
    assert store.get("sha256:" + second.sha256).is_err()


def test_materialize_code_block_converts_store_exception_to_typed_error():
    class RaisingStore:
        def put(self, data, *, name, media_type):
            raise RuntimeError("store unavailable")

    result = materialize_code_block(RaisingStore(), CodeBlock(0, "text", "data"))

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "CODE_ARTIFACT_STORE_ERROR"


def test_in_memory_artifacts_are_content_addressed_and_quota_bounded():
    store = InMemoryArtifactStore(max_artifact_bytes=4, max_store_bytes=4)
    first = store.put(b"1234", name="one.txt", media_type="text/plain")
    duplicate = store.put(b"1234", name="renamed.txt")
    full = store.put(b"5")

    assert first.is_ok()
    assert duplicate.unwrap() == first.unwrap()
    assert store.get(first.unwrap().artifact_id).unwrap() == b"1234"
    assert full.is_err()
    assert full.unwrap_err()["errorType"] == "ARTIFACT_STORE_FULL"


def test_file_artifacts_survive_restart_and_verify_content_hash(tmp_path):
    store = FileArtifactStore(tmp_path, max_artifact_bytes=16, max_store_bytes=32)
    created = store.put(
        b"persisted", name="result.txt", media_type="text/plain"
    ).unwrap()

    restarted = FileArtifactStore(tmp_path, max_artifact_bytes=16, max_store_bytes=32)
    assert restarted.get(created.artifact_id).unwrap() == b"persisted"
    assert restarted.describe(created.artifact_id).unwrap() == created

    data_path = tmp_path / f"sha256-{created.sha256}.bin"
    data_path.write_bytes(b"tampered")
    corrupt = restarted.get(created.artifact_id)
    assert corrupt.is_err()
    assert corrupt.unwrap_err()["errorType"] == "ARTIFACT_CORRUPT"


def test_artifact_ids_and_names_reject_path_traversal(tmp_path):
    store = FileArtifactStore(tmp_path)

    bad_name = store.put(b"data", name="..\\secret.txt")
    bad_id = store.get("sha256:..\\secret")

    assert bad_name.is_err()
    assert bad_name.unwrap_err()["errorType"] == "ARTIFACT_NAME_INVALID"
    assert bad_id.is_err()
    assert bad_id.unwrap_err()["errorType"] == "ARTIFACT_ID_INVALID"
