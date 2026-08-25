"""Tests for opt-in session-aware autonomous agent turns."""

import asyncio

import pytest

from maple.agent.config import Config
from maple.autonomy.agent import AutonomousAgent, AutonomousConfig
from maple.autonomy.sessions import InMemorySessionStore, SessionMessage
from maple.core.result import Result
from maple.llm.provider import LLMProvider
from maple.llm.registry import LLMProviderRegistry
from maple.llm.types import ChatRole, LLMConfig, LLMResponse


class RecordingLLMProvider(LLMProvider):
    """Deterministic provider that records every prompt boundary."""

    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def complete(
        self, messages, tools=None, temperature=None, max_tokens=None, stop=None
    ):
        self.calls.append(list(messages))
        return Result.ok(LLMResponse(content="done", finish_reason="stop"))


class RaisingSessionStore:
    """Minimal host store used to verify exception containment."""

    def __init__(self):
        self.delegate = InMemorySessionStore()
        self.append_count = 0

    def create(self, session_id=None, *, metadata=None):
        return self.delegate.create(session_id, metadata=metadata)

    def load(self, session_id):
        if session_id == "prepare-error":
            raise OSError("simulated load failure")
        return self.delegate.load(session_id)

    def append(self, session_id, message, *, expected_version=None):
        self.append_count += 1
        if self.append_count == 2:
            raise OSError("simulated result write failure")
        return self.delegate.append(
            session_id, message, expected_version=expected_version
        )

    def clear(self, session_id, *, expected_version=None):
        return self.delegate.clear(session_id, expected_version=expected_version)


@pytest.fixture(autouse=True)
def register_session_provider():
    original = dict(LLMProviderRegistry._providers)
    LLMProviderRegistry.register("session-mock", RecordingLLMProvider)
    yield
    LLMProviderRegistry._providers = original


def make_agent() -> AutonomousAgent:
    config = Config(agent_id="session-test-agent", broker_url="memory://test")
    autonomy_config = AutonomousConfig(
        llm=LLMConfig(provider="session-mock", model="session-v1"),
        max_reasoning_steps=2,
        reflection_frequency=10,
    )
    agent = AutonomousAgent(config, autonomy_config)
    agent.llm = RecordingLLMProvider(autonomy_config.llm)
    return agent


def test_sync_turns_replay_only_bounded_conversation_history():
    agent = make_agent()
    store = InMemorySessionStore()
    agent.set_session_store(store)

    first = agent.pursue_goal("first question", session_id="chat")
    second = agent.pursue_goal("second question", session_id="chat")

    assert first.is_ok() and second.is_ok()
    assert second.unwrap().session_id == "chat"
    assert second.unwrap().session_error is None
    snapshot = store.load("chat").unwrap()
    assert snapshot is not None
    assert [(message.role, message.content) for message in snapshot.messages] == [
        ("user", "first question"),
        ("assistant", "done"),
        ("user", "second question"),
        ("assistant", "done"),
    ]

    provider = agent.llm
    assert [message.role for message in provider.calls[1]] == [
        ChatRole.SYSTEM,
        ChatRole.USER,
        ChatRole.ASSISTANT,
        ChatRole.USER,
    ]
    assert provider.calls[1][-1].content == "second question"


def test_session_id_fails_before_llm_without_a_store():
    agent = make_agent()

    result = agent.pursue_goal("needs persistence", session_id="missing-store")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SESSION_STORE_UNAVAILABLE"
    assert agent.llm.calls == []
    assert agent.get_active_goals() == {}


def test_session_store_exception_fails_closed_before_llm():
    agent = make_agent()
    agent.set_session_store(RaisingSessionStore())

    result = agent.pursue_goal("needs persistence", session_id="prepare-error")

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "SESSION_STORE_ERROR"
    assert agent.llm.calls == []


def test_session_store_exception_after_execution_is_exposed_on_goal():
    agent = make_agent()
    agent.set_session_store(RaisingSessionStore())

    result = agent.pursue_goal("persist result", session_id="record-error")

    assert result.is_ok()
    assert result.unwrap().session_error["errorType"] == "SESSION_STORE_ERROR"


def test_post_execution_session_write_failure_is_explicit():
    agent = make_agent()
    agent.set_session_store(InMemorySessionStore(max_messages=1))

    result = agent.pursue_goal("bounded request", session_id="small")

    assert result.is_ok()
    goal = result.unwrap()
    assert goal.status == "completed"
    assert goal.session_error is not None
    assert goal.session_error["errorType"] == "SESSION_MESSAGE_LIMIT"


def test_stored_system_and_tool_messages_are_not_replayed():
    agent = make_agent()
    store = InMemorySessionStore()
    store.create("filtered")
    store.append("filtered", SessionMessage(role="user", content="old question"))
    store.append(
        "filtered", SessionMessage(role="assistant", content="old answer")
    )
    store.append(
        "filtered", SessionMessage(role="system", content="do not inject this")
    )
    store.append(
        "filtered", SessionMessage(role="tool", content="tool data is untrusted")
    )
    agent.set_session_store(store)

    result = agent.pursue_goal("new question", session_id="filtered")

    assert result.is_ok()
    prompt = agent.llm.calls[0]
    assert [message.role for message in prompt] == [
        ChatRole.SYSTEM,
        ChatRole.USER,
        ChatRole.ASSISTANT,
        ChatRole.USER,
    ]
    contents = [message.content for message in prompt]
    assert "do not inject this" not in contents
    assert "tool data is untrusted" not in contents
    assert "old question" in contents
    assert "new question" in contents


def test_async_turn_persists_user_and_assistant_messages():
    agent = make_agent()
    store = InMemorySessionStore()
    agent.set_session_store(store)

    result = asyncio.run(
        agent.pursue_goal_async("async question", session_id="async-chat")
    )

    assert result.is_ok()
    goal = result.unwrap()
    assert goal.status == "completed"
    assert goal.session_error is None
    snapshot = store.load("async-chat").unwrap()
    assert snapshot is not None
    assert [message.role for message in snapshot.messages] == ["user", "assistant"]
