"""Tests for bounded artifacts and non-executing code-block extraction."""

from maple.autonomy.artifacts import (
    FileArtifactStore,
    InMemoryArtifactStore,
    extract_code_blocks,
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
