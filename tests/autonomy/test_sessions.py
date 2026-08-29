"""Tests for the bounded conversation session boundary."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from maple.autonomy import (
    FileSessionStore,
    InMemorySessionStore,
    SessionMessage,
    SessionSnapshot,
)
from maple.llm.types import ChatMessage, ChatRole, ImageContent, ToolCall


def _session_store_variants(tmp_path, *, max_history=100):
    return [
        InMemorySessionStore(max_messages=8, max_history=max_history),
        FileSessionStore(
            tmp_path / f"file-{max_history}",
            max_messages=8,
            max_history=max_history,
        ),
    ]


def test_in_memory_session_appends_versioned_messages_and_returns_copies():
    store = InMemorySessionStore(max_messages=2)
    created = store.create("session-1", metadata={"tenant": "demo"})

    assert created.is_ok()
    assert created.unwrap().version == 0
    appended = store.append(
        "session-1",
        SessionMessage(role="user", content="hello"),
        expected_version=0,
    )

    assert appended.is_ok()
    assert appended.unwrap().version == 1
    assert [message.content for message in appended.unwrap().messages] == ["hello"]
    appended.unwrap().messages[0].metadata["mutated"] = True
    loaded = store.load("session-1")
    assert loaded.is_ok()
    assert loaded.unwrap().messages[0].metadata == {}


def test_session_append_conflict_and_message_limit_fail_without_mutation():
    store = InMemorySessionStore(max_messages=1)
    assert store.create("session-2").is_ok()
    first = store.append("session-2", SessionMessage(role="user", content="one"))
    assert first.is_ok()

    conflict = store.append(
        "session-2",
        SessionMessage(role="assistant", content="stale"),
        expected_version=0,
    )
    limited = store.append("session-2", SessionMessage(role="assistant", content="two"))

    assert conflict.is_err()
    assert conflict.unwrap_err()["errorType"] == "SESSION_CONFLICT"
    assert limited.is_err()
    assert limited.unwrap_err()["errorType"] == "SESSION_MESSAGE_LIMIT"
    assert len(store.load("session-2").unwrap().messages) == 1


def test_session_rejects_invalid_metadata_before_creating_session():
    store = InMemorySessionStore()

    result = store.create("session-3", metadata={"bad": object()})

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SESSION_METADATA_VALUE"
    assert store.load("session-3").unwrap() is None


def test_session_rejects_invalid_role_and_oversized_message_before_mutation():
    store = InMemorySessionStore(max_message_bytes=128)
    assert store.create("session-4").is_ok()

    invalid_role = store.append(
        "session-4", SessionMessage(role="unknown", content="x")
    )
    oversized = store.append(
        "session-4", SessionMessage(role="user", content="x" * 1_000)
    )

    assert invalid_role.is_err()
    assert invalid_role.unwrap_err()["errorType"] == "SESSION_MESSAGE_INVALID"
    assert oversized.is_err()
    assert oversized.unwrap_err()["errorType"] == "SESSION_MESSAGE_SIZE"
    assert store.load("session-4").unwrap().messages == ()


def test_session_accepts_empty_message_content_as_json_safe_data():
    store = InMemorySessionStore()
    assert store.create("session-empty").is_ok()

    result = store.append("session-empty", SessionMessage(role="assistant", content=""))

    assert result.is_ok()
    assert result.unwrap().messages[0].content == ""


def test_in_memory_session_store_serializes_concurrent_appends():
    store = InMemorySessionStore(max_messages=8)
    assert store.create("session-concurrent").is_ok()

    def append(index):
        return store.append(
            "session-concurrent",
            SessionMessage(role="user", content=f"message-{index}"),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(8)))

    assert all(result.is_ok() for result in results)
    snapshot = store.load("session-concurrent").unwrap()
    assert snapshot.version == 8
    assert sorted(message.content for message in snapshot.messages) == [
        f"message-{index}" for index in range(8)
    ]


def test_file_session_survives_store_recreation_and_clear(tmp_path):
    first_store = FileSessionStore(tmp_path)
    created = first_store.create("file-session")
    assert created.is_ok()
    appended = first_store.append(
        "file-session",
        SessionMessage(role="user", content="persist me"),
        expected_version=created.unwrap().version,
    )
    assert appended.is_ok()

    restarted = FileSessionStore(tmp_path)
    loaded = restarted.load("file-session")
    assert loaded.is_ok()
    assert loaded.unwrap().version == 1
    assert loaded.unwrap().messages[0].content == "persist me"

    cleared = restarted.clear("file-session", expected_version=1)
    assert cleared.is_ok()
    assert cleared.unwrap().messages == ()
    assert restarted.load("file-session").unwrap().version == 2


def test_file_session_malformed_payload_fails_closed(tmp_path):
    (tmp_path / "bad.json").write_text(
        json.dumps({"session_id": "bad"}), encoding="utf-8"
    )
    store = FileSessionStore(tmp_path)

    result = store.load("bad")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SESSION_LOAD_ERROR"


def test_session_message_round_trips_typed_llm_tool_call():
    original = ChatMessage(
        role=ChatRole.ASSISTANT,
        content="Calling a tool",
        name="agent",
        tool_calls=[ToolCall(id="call-1", name="lookup", arguments={"q": "MAPLE"})],
    )

    stored = SessionMessage.from_chat_message(original)
    restored = stored.to_chat_message()

    assert restored.role == ChatRole.ASSISTANT
    assert restored.content == original.content
    assert restored.name == "agent"
    assert restored.tool_calls[0].arguments == {"q": "MAPLE"}


def test_session_message_round_trips_typed_image_content():
    original = ChatMessage(
        role=ChatRole.USER,
        content=[
            "describe this",
            ImageContent(
                source="data:image/png;base64," + base64.b64encode(b"image").decode(),
                detail="high",
            ),
        ],
    )

    stored = SessionMessage.from_chat_message(original)
    restored = SessionMessage.from_dict(stored.to_dict()).to_chat_message()

    assert restored.content == original.content


def test_session_history_is_bounded_chronological_and_detached(tmp_path):
    for store in _session_store_variants(tmp_path, max_history=2):
        assert store.create("history-session").is_ok()
        for index in range(3):
            assert store.append(
                "history-session",
                SessionMessage(role="user", content=f"message-{index}"),
            ).is_ok()

        history = store.history("history-session")

        assert history.is_ok()
        assert [snapshot.version for snapshot in history.unwrap()] == [2, 3]
        assert [snapshot.messages[-1].content for snapshot in history.unwrap()] == [
            "message-1",
            "message-2",
        ]
        history.unwrap()[0].messages[0].metadata["changed"] = True
        assert (
            "changed"
            not in store.history("history-session").unwrap()[0].messages[0].metadata
        )


def test_session_fork_copies_selected_version_without_sharing_state(tmp_path):
    for store in _session_store_variants(tmp_path):
        assert store.create(
            "source-session", metadata={"tenant": "demo", "labels": ["a"]}
        ).is_ok()
        assert store.append(
            "source-session",
            SessionMessage(role="user", content="first"),
        ).is_ok()
        assert store.append(
            "source-session",
            SessionMessage(role="assistant", content="second"),
        ).is_ok()

        forked = store.fork("source-session", "branch-session", at_version=1)

        assert forked.is_ok()
        branch = forked.unwrap()
        assert branch.version == 0
        assert [message.content for message in branch.messages] == ["first"]
        assert branch.metadata == {"tenant": "demo", "labels": ["a"]}
        branch.metadata["labels"].append("branch")
        branch.messages[0].metadata["branch"] = True
        assert store.load("source-session").unwrap().metadata == {
            "tenant": "demo",
            "labels": ["a"],
        }
        assert (
            "branch" not in store.load("source-session").unwrap().messages[0].metadata
        )
        assert store.append(
            "branch-session",
            SessionMessage(role="user", content="branch-only"),
            expected_version=0,
        ).is_ok()
        assert store.load("source-session").unwrap().version == 2


def test_session_fork_rejects_stale_existing_and_evicted_versions(tmp_path):
    for store in _session_store_variants(tmp_path, max_history=2):
        assert store.create("fork-source").is_ok()
        for index in range(3):
            assert store.append(
                "fork-source",
                SessionMessage(role="user", content=str(index)),
            ).is_ok()

        stale = store.fork(
            "fork-source",
            "stale-branch",
            expected_version=1,
        )
        evicted = store.fork("fork-source", "evicted-branch", at_version=1)
        assert stale.is_err()
        assert stale.unwrap_err()["errorType"] == "SESSION_CONFLICT"
        assert evicted.is_err()
        assert evicted.unwrap_err()["errorType"] == "SESSION_VERSION_UNAVAILABLE"
        assert store.create("existing-branch").is_ok()
        existing = store.fork("fork-source", "existing-branch")
        missing = store.fork("missing-source", "missing-branch")
        assert existing.is_err()
        assert existing.unwrap_err()["errorType"] == "SESSION_EXISTS"
        assert missing.is_err()
        assert missing.unwrap_err()["errorType"] == "SESSION_NOT_FOUND"
        assert store.load("stale-branch").unwrap() is None
        assert store.load("evicted-branch").unwrap() is None


def test_session_fork_rejects_explicit_empty_target_without_creating_branch(tmp_path):
    for store in (
        InMemorySessionStore(max_sessions=2),
        FileSessionStore(tmp_path / "file-empty-target", max_sessions=2),
    ):
        assert store.create("fork-source").is_ok()

        invalid = store.fork("fork-source", "")

        assert invalid.is_err()
        assert invalid.unwrap_err()["errorType"] == "INVALID_IDENTIFIER"
        assert store.fork("fork-source", "explicit-branch").is_ok()


def test_session_history_validates_bounds_and_constructor_limit():
    with pytest.raises(ValueError, match="max_history"):
        InMemorySessionStore(max_history=0)
    with pytest.raises(ValueError, match="max_history"):
        InMemorySessionStore(max_history=10_001)

    store = InMemorySessionStore(max_history=2)
    assert store.create("history-limits").is_ok()
    invalid_limit = store.history("history-limits", limit=True)
    oversized_limit = store.history("history-limits", limit=3)
    assert invalid_limit.is_err()
    assert invalid_limit.unwrap_err()["errorType"] == "SESSION_HISTORY_LIMIT"
    assert oversized_limit.is_err()
    assert oversized_limit.unwrap_err()["errorType"] == "SESSION_HISTORY_LIMIT"


def test_file_session_legacy_snapshot_is_read_without_rewrite_then_migrated(tmp_path):
    legacy = SessionSnapshot(session_id="legacy-session")
    path = tmp_path / "legacy-session.json"
    path.write_text(json.dumps(legacy.to_dict(), indent=2), encoding="utf-8")
    before = path.read_bytes()
    store = FileSessionStore(tmp_path)

    inspected = store.history("legacy-session")

    assert inspected.is_ok()
    assert [snapshot.version for snapshot in inspected.unwrap()] == [0]
    assert path.read_bytes() == before
    appended = store.append(
        "legacy-session", SessionMessage(role="user", content="migrated")
    )

    assert appended.is_ok()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert [snapshot["version"] for snapshot in payload["history"]] == [0, 1]


def test_file_session_history_can_be_reopened_with_a_smaller_bound(tmp_path):
    original = FileSessionStore(tmp_path, max_history=3)
    assert original.create("resize-session").is_ok()
    for index in range(3):
        assert original.append(
            "resize-session", SessionMessage(role="user", content=str(index))
        ).is_ok()

    resized = FileSessionStore(tmp_path, max_history=2)

    assert [item.version for item in resized.history("resize-session").unwrap()] == [
        2,
        3,
    ]
    assert resized.append(
        "resize-session",
        SessionMessage(role="user", content="new"),
        expected_version=3,
    ).is_ok()
    assert [item.version for item in resized.history("resize-session").unwrap()] == [
        3,
        4,
    ]


def test_file_session_malformed_history_fails_closed_without_rewriting(tmp_path):
    store = FileSessionStore(tmp_path)
    assert store.create("corrupt-history").is_ok()
    path = tmp_path / "corrupt-history.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["history"] = []
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()

    inspected = store.history("corrupt-history")
    blocked = store.append(
        "corrupt-history", SessionMessage(role="user", content="blocked")
    )

    assert inspected.is_err()
    assert inspected.unwrap_err()["errorType"] == "SESSION_HISTORY_INVALID"
    assert blocked.is_err()
    assert blocked.unwrap_err()["errorType"] == "SESSION_HISTORY_INVALID"
    assert path.read_bytes() == before


def test_session_history_size_limit_rejects_mutation_without_partial_state(tmp_path):
    stores = [
        InMemorySessionStore(
            max_messages=2,
            max_message_bytes=600,
            max_session_bytes=600,
            max_history=2,
        ),
        FileSessionStore(
            tmp_path / "size-file",
            max_messages=2,
            max_message_bytes=600,
            max_session_bytes=600,
            max_history=2,
        ),
    ]
    for store in stores:
        created = store.create("size-session")
        assert created.is_ok()
        before = store.load("size-session").unwrap().to_dict()

        appended = store.append(
            "size-session", SessionMessage(role="user", content="fits alone")
        )

        assert appended.is_err()
        assert appended.unwrap_err()["errorType"] == "SESSION_SIZE_EXCEEDED"
        assert store.load("size-session").unwrap().to_dict() == before
