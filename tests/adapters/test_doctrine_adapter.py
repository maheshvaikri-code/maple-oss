"""Tests for maple/adapters/doctrine_adapter.py — WORK.PACKAGE/GATE.RESULT schemas (#4)."""

import pytest

from maple.adapters.doctrine_adapter import (
    GATE_VERDICTS,
    DoctrineAdapter,
    build_gate_result,
    build_work_package,
    validate_gate_result,
    validate_gate_result_payload,
    validate_work_package,
    validate_work_package_payload,
)
from maple.agent.agent import Agent
from maple.agent.config import Config
from maple.broker.broker import MessageBroker
from maple.core.message import Message
from maple.security.separation import (
    GATE_RESULT,
    WORK_PACKAGE,
    ArtifactRef,
    fresh_context_verifier_preset,
)


def _ref(path="docs/brief.md", content=b"brief bytes"):
    return ArtifactRef.of(path, content)


def _reset_broker_singleton():
    MessageBroker.reset_scopes()


@pytest.fixture(autouse=True)
def reset_broker():
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


# --------------------------------------------------------------------------- #
# WORK.PACKAGE builders / validators
# --------------------------------------------------------------------------- #
class TestWorkPackage:
    def test_build_valid(self):
        result = build_work_package(
            package_id="pkg-001",
            role="backend-engineer",
            file_scope=["maple/foo.py", "tests/test_foo.py"],
            brief=_ref(),
        )
        assert result.is_ok()
        msg = result.unwrap()
        assert msg.message_type == WORK_PACKAGE
        assert msg.payload["package_id"] == "pkg-001"
        assert msg.payload["brief"] == _ref().to_dict()

    def test_build_accepts_ref_dict(self):
        result = build_work_package("pkg", "role", ["a.py"], _ref().to_dict())
        assert result.is_ok()

    def test_build_rejects_empty_package_id(self):
        result = build_work_package("", "role", ["a.py"], _ref())
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INVALID_WORK_PACKAGE"

    def test_build_rejects_empty_file_scope(self):
        result = build_work_package("pkg", "role", [], _ref())
        assert result.is_err()

    def test_build_rejects_non_string_file_scope(self):
        result = build_work_package("pkg", "role", ["a.py", 5], _ref())
        assert result.is_err()

    def test_build_rejects_non_ref_brief(self):
        result = build_work_package("pkg", "role", ["a.py"], {"path": "x"})
        assert result.is_err()

    def test_validate_valid_message(self):
        msg = build_work_package("pkg", "role", ["a.py"], _ref()).unwrap()
        assert validate_work_package(msg).is_ok()

    def test_validate_wrong_type(self):
        msg = Message(message_type="CHAT", payload={})
        result = validate_work_package(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "WRONG_MESSAGE_TYPE"

    def test_validate_missing_field(self):
        msg = Message(message_type=WORK_PACKAGE, payload={"package_id": "p"})
        assert validate_work_package(msg).is_err()


# --------------------------------------------------------------------------- #
# GATE.RESULT builders / validators
# --------------------------------------------------------------------------- #
class TestGateResult:
    def test_build_valid(self):
        result = build_gate_result("G5", "PASS", _ref("docs/qa.md"))
        assert result.is_ok()
        msg = result.unwrap()
        assert msg.message_type == GATE_RESULT
        assert msg.payload["verdict"] == "PASS"

    def test_verdict_normalized_to_upper(self):
        result = build_gate_result("G4", "blocked", _ref())
        assert result.is_ok()
        assert result.unwrap().payload["verdict"] == "BLOCKED"

    def test_all_canonical_verdicts_accepted(self):
        for v in GATE_VERDICTS:
            assert build_gate_result("G5", v, _ref()).is_ok()

    def test_build_rejects_unknown_verdict(self):
        result = build_gate_result("G5", "MAYBE", _ref())
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INVALID_GATE_RESULT"

    def test_build_rejects_non_ref_artifact(self):
        result = build_gate_result("G5", "PASS", {"nope": 1})
        assert result.is_err()

    def test_optional_evidence_included(self):
        msg = build_gate_result("G5", "PASS", _ref(), evidence="52 tests").unwrap()
        assert msg.payload["evidence"] == "52 tests"

    def test_validate_wrong_type(self):
        msg = Message(message_type=WORK_PACKAGE, payload={})
        assert validate_gate_result(msg).is_err()

    def test_validate_valid(self):
        msg = build_gate_result("G5", "FAIL", _ref()).unwrap()
        assert validate_gate_result(msg).is_ok()


# --------------------------------------------------------------------------- #
# Cross-tie: built payloads satisfy the fresh-context verifier preset (#3)
# --------------------------------------------------------------------------- #
class TestSatisfiesSeparationPolicy:
    def test_work_package_passes_separation(self):
        policy = fresh_context_verifier_preset("orch", ["backend"], ["reviewer"])
        msg = build_work_package(
            "pkg",
            "backend",
            ["maple/foo.py"],
            _ref(),
            sender="orch",
            receiver="backend",
        ).unwrap()
        # orchestrator -> builder is allowed AND the payload is artifact-ref-only
        assert policy.authorize_send(msg).is_ok()

    def test_gate_result_passes_separation(self):
        policy = fresh_context_verifier_preset("orch", ["backend"], ["reviewer"])
        msg = build_gate_result(
            "G5",
            "PASS",
            _ref("docs/qa.md"),
            sender="reviewer",
            receiver="orch",
        ).unwrap()
        assert policy.authorize_send(msg).is_ok()


# --------------------------------------------------------------------------- #
# Agent-bound adapter (ties #1 uppercase types + #2 require_routable)
# --------------------------------------------------------------------------- #
class TestDoctrineAdapter:
    def test_send_work_package_to_live_agent(self):
        orch = Agent(Config(agent_id="orch", broker_url="memory://local"))
        worker = Agent(Config(agent_id="backend", broker_url="memory://local"))
        orch.start()
        worker.start()
        adapter = DoctrineAdapter(orch)
        result = adapter.send_work_package(
            "backend",
            "pkg-1",
            "backend",
            ["maple/foo.py"],
            _ref(),
            require_routable=True,
        )
        assert result.is_ok()
        orch.stop()
        worker.stop()

    def test_send_to_unroutable_receiver_errs(self):
        orch = Agent(Config(agent_id="orch", broker_url="memory://local"))
        orch.start()
        adapter = DoctrineAdapter(orch)
        result = adapter.send_work_package(
            "ghost",
            "pkg-1",
            "backend",
            ["maple/foo.py"],
            _ref(),
            require_routable=True,
        )
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "UNROUTABLE"
        orch.stop()

    def test_invalid_build_short_circuits_send(self):
        orch = Agent(Config(agent_id="orch", broker_url="memory://local"))
        orch.start()
        adapter = DoctrineAdapter(orch)
        # bad verdict -> build fails -> send never attempted
        result = adapter.send_gate_result("worker", "G5", "NOPE", _ref())
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INVALID_GATE_RESULT"
        orch.stop()

    def test_send_gate_result_ok(self):
        reviewer = Agent(Config(agent_id="reviewer", broker_url="memory://local"))
        orch = Agent(Config(agent_id="orch", broker_url="memory://local"))
        reviewer.start()
        orch.start()
        adapter = DoctrineAdapter(reviewer)
        result = adapter.send_gate_result(
            "orch",
            "G5",
            "PASS",
            _ref("docs/qa.md"),
            evidence="ok",
            require_routable=True,
        )
        assert result.is_ok()
        reviewer.stop()
        orch.stop()


# --------------------------------------------------------------------------- #
# Validator + builder edge cases (error branches)
# --------------------------------------------------------------------------- #
class TestValidatorEdges:
    def test_wp_payload_not_dict(self):
        assert validate_work_package_payload("nope").is_err()

    def test_wp_payload_bad_file_scope_type(self):
        r = validate_work_package_payload(
            {
                "package_id": "p",
                "role": "r",
                "file_scope": "notalist",
                "brief": _ref().to_dict(),
            }
        )
        assert r.is_err()

    def test_wp_payload_missing_role(self):
        r = validate_work_package_payload(
            {"package_id": "p", "file_scope": ["a.py"], "brief": _ref().to_dict()}
        )
        assert r.is_err()

    def test_gr_payload_not_dict(self):
        assert validate_gate_result_payload(123).is_err()

    def test_gr_payload_empty_gate(self):
        r = validate_gate_result_payload(
            {"gate": "", "verdict": "PASS", "artifact": _ref().to_dict()}
        )
        assert r.is_err()

    def test_gr_payload_bad_artifact(self):
        r = validate_gate_result_payload(
            {"gate": "G5", "verdict": "PASS", "artifact": {"x": 1}}
        )
        assert r.is_err()


class TestBuildBadReceiver:
    """A bad agent id must surface as a Result.err, not a raised exception."""

    def test_work_package_bad_receiver(self):
        r = build_work_package(
            "p", "r", ["a.py"], _ref(), receiver="bad id with spaces"
        )
        assert r.is_err()
        assert r.unwrap_err()["errorType"] == "INVALID_WORK_PACKAGE"

    def test_gate_result_bad_receiver(self):
        r = build_gate_result("G5", "PASS", _ref(), receiver="bad id with spaces")
        assert r.is_err()
        assert r.unwrap_err()["errorType"] == "INVALID_GATE_RESULT"


class TestAdapterShortCircuit:
    def test_send_work_package_invalid_short_circuits(self):
        orch = Agent(Config(agent_id="orch", broker_url="memory://local"))
        orch.start()
        # empty package_id -> build fails -> send never attempted
        result = DoctrineAdapter(orch).send_work_package(
            "worker", "", "role", ["a.py"], _ref()
        )
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "INVALID_WORK_PACKAGE"
        orch.stop()


class TestFileScopeGenerator:
    def test_non_string_element_in_populated_scope(self):
        # Forces the all(...) generator to evaluate a non-string element.
        r = validate_work_package_payload(
            {
                "package_id": "p",
                "role": "r",
                "file_scope": ["ok.py", 5],
                "brief": _ref().to_dict(),
            }
        )
        assert r.is_err()


class TestValidatorBriefBranch:
    def test_wp_payload_valid_fields_but_bad_brief(self):
        # Reaches the validator's brief check (an incoming message whose
        # package_id/role/file_scope are fine but brief is malformed).
        r = validate_work_package_payload(
            {
                "package_id": "p",
                "role": "r",
                "file_scope": ["a.py"],
                "brief": {"path": "x"},
            }
        )
        assert r.is_err()
        assert r.unwrap_err()["errorType"] == "INVALID_WORK_PACKAGE"
