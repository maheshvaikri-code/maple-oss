"""Tests for the trusted-local bounded execution boundary."""

import threading
import time

from maple.autonomy.execution import (
    CancellationToken,
    ExecutionPolicy,
    TrustedLocalExecutor,
)
from maple.autonomy.tools import Tool
from maple.core.result import Result


def test_executor_returns_handler_value_and_measures_json_output():
    executor = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, max_output_bytes=100)
    )

    result = executor.execute("echo", lambda value: value, kwargs={"value": "ok"})

    assert result.is_ok()
    assert result.unwrap() == "ok"


def test_executor_rejects_oversized_input_and_output():
    input_limited = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, max_input_bytes=10)
    )
    output_limited = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, max_output_bytes=10)
    )

    too_large_input = input_limited.execute(
        "input", lambda **kwargs: kwargs, kwargs={"value": "large"}
    )
    too_large_output = output_limited.execute("output", lambda: "0123456789-too-large")

    assert too_large_input.is_err()
    assert too_large_input.unwrap_err()["errorType"] == "EXECUTION_INPUT_TOO_LARGE"
    assert too_large_output.is_err()
    assert too_large_output.unwrap_err()["errorType"] == "EXECUTION_OUTPUT_TOO_LARGE"


def test_timeout_sets_token_and_cooperative_handler_finishes():
    token = CancellationToken()
    started = threading.Event()
    finished = threading.Event()

    def cooperative_handler():
        started.set()
        while not token.is_cancelled():
            time.sleep(0.002)
        finished.set()
        return "stopped"

    executor = TrustedLocalExecutor(ExecutionPolicy(timeout_seconds=0.02))
    result = executor.execute("slow", cooperative_handler, cancellation=token)

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EXECUTION_TIMEOUT"
    assert started.is_set()
    assert token.is_cancelled()
    assert finished.wait(0.5)


def test_external_cancellation_returns_without_waiting_for_timeout():
    token = CancellationToken()
    started = threading.Event()
    finished = threading.Event()
    holder = {}

    def cooperative_handler():
        started.set()
        while not token.is_cancelled():
            time.sleep(0.002)
        finished.set()

    executor = TrustedLocalExecutor(ExecutionPolicy(timeout_seconds=1))

    def invoke():
        holder["result"] = executor.execute(
            "cancel", cooperative_handler, cancellation=token
        )

    thread = threading.Thread(target=invoke)
    thread.start()
    assert started.wait(0.5)
    token.cancel()
    thread.join(0.5)

    assert not thread.is_alive()
    assert holder["result"].unwrap_err()["errorType"] == "EXECUTION_CANCELLED"
    assert finished.wait(0.5)


def test_approval_is_fail_closed():
    required = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, require_approval=True)
    )
    denied = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, require_approval=True),
        approval_callback=lambda operation: False,
    )
    approved = TrustedLocalExecutor(
        ExecutionPolicy(timeout_seconds=1, require_approval=True),
        approval_callback=lambda operation: True,
    )

    assert (
        required.execute("write", lambda: "ok").unwrap_err()["errorType"]
        == "EXECUTION_APPROVAL_REQUIRED"
    )
    assert (
        denied.execute("write", lambda: "ok").unwrap_err()["errorType"]
        == "EXECUTION_APPROVAL_DENIED"
    )
    assert approved.execute("write", lambda: "ok").unwrap() == "ok"


def test_tool_can_opt_into_trusted_executor():
    tool = Tool(
        name="bounded",
        description="Bounded tool",
        parameters={"type": "object"},
        handler=lambda: Result.ok({"status": "ok"}),
        result_schema={"type": "object", "required": ["status"]},
        executor=TrustedLocalExecutor(ExecutionPolicy(timeout_seconds=1)),
    )

    result = tool.execute()

    assert result.is_ok()
    assert result.unwrap() == {"status": "ok"}


def test_cancellation_before_start_does_not_call_handler():
    token = CancellationToken()
    token.cancel()
    called = []
    executor = TrustedLocalExecutor(ExecutionPolicy(timeout_seconds=1))

    result = executor.execute(
        "cancelled", lambda: called.append(True), cancellation=token
    )

    assert result.is_err()
    assert result.unwrap_err()["errorType"] == "EXECUTION_CANCELLED"
    assert called == []
