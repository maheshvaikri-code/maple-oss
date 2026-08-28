"""Tests for the bounded conversation session boundary."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor

from maple.autonomy import (
    FileSessionStore,
    InMemorySessionStore,
    SessionMessage,
)
from maple.llm.types import ChatMessage, ChatRole, ImageContent, ToolCall


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
