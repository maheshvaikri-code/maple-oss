"""Tests for maple/security/separation.py — the fresh-context verifier preset.

Covers the two runtime guarantees from enhancement ask #3
(.Doctrine/integrations/maple.md):

* a broker-enforced per-agent sender allowlist (separation of duties), and
* an artifact-ref-only payload policy for guarded message types.
"""

import hashlib

import pytest

from maple.core.message import Message
from maple.agent.config import Config, SecurityConfig
from maple.broker.broker import MessageBroker, SecurityError
from maple.security.separation import (
    ArtifactRef,
    SeparationOfDutiesPolicy,
    fresh_context_verifier_preset,
    attach_to_config,
    is_artifact_ref,
    WORK_PACKAGE,
    GATE_RESULT,
    _MAX_PAYLOAD_DEPTH,
)


def _ref_dict(path="docs/qa/task.md", content=b"artifact bytes"):
    return ArtifactRef.of(path, content).to_dict()


# --------------------------------------------------------------------------- #
# ArtifactRef
# --------------------------------------------------------------------------- #
class TestArtifactRef:
    def test_of_bytes_computes_sha256(self):
        ref = ArtifactRef.of("docs/brief.md", b"hello")
        assert ref.path == "docs/brief.md"
        assert ref.sha256 == hashlib.sha256(b"hello").hexdigest()

    def test_of_str_is_utf8_encoded(self):
        ref = ArtifactRef.of("docs/brief.md", "hello")
        assert ref.sha256 == hashlib.sha256(b"hello").hexdigest()

    def test_to_dict_shape(self):
        ref = ArtifactRef.of("p", b"x")
        assert set(ref.to_dict().keys()) == {"path", "sha256"}

    def test_for_file(self, tmp_path):
        f = tmp_path / "artifact.txt"
        f.write_bytes(b"file body")
        ref = ArtifactRef.for_file(str(f))
        assert ref.sha256 == hashlib.sha256(b"file body").hexdigest()

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError):
            ArtifactRef(path="", sha256="a" * 64)

    def test_rejects_bad_sha_length(self):
        with pytest.raises(ValueError):
            ArtifactRef(path="p", sha256="abc")

    def test_rejects_non_hex_sha(self):
        with pytest.raises(ValueError):
            ArtifactRef(path="p", sha256="z" * 64)

    def test_frozen(self):
        ref = ArtifactRef.of("p", b"x")
        with pytest.raises(Exception):
            ref.path = "other"  # frozen dataclass


class TestIsArtifactRef:
    def test_valid(self):
        assert is_artifact_ref(_ref_dict())

    def test_missing_key(self):
        assert not is_artifact_ref({"path": "p"})

    def test_extra_key(self):
        d = _ref_dict()
        d["note"] = "reasoning"
        assert not is_artifact_ref(d)

    def test_non_dict(self):
        assert not is_artifact_ref("not a dict")
        assert not is_artifact_ref(None)

    def test_bad_sha(self):
        assert not is_artifact_ref({"path": "p", "sha256": "short"})

    def test_empty_path(self):
        assert not is_artifact_ref({"path": "", "sha256": "a" * 64})


# --------------------------------------------------------------------------- #
# SeparationOfDutiesPolicy — sender allowlist
# --------------------------------------------------------------------------- #
class TestSenderAllowlist:
    def test_allowed_send_passes(self):
        policy = SeparationOfDutiesPolicy().allow("orch", "builder")
        msg = Message(message_type="TEST", sender="orch", receiver="builder")
        assert policy.authorize_send(msg).is_ok()

    def test_disallowed_receiver_denied(self):
        policy = SeparationOfDutiesPolicy().allow("verifier", "orch")
        msg = Message(message_type="TEST", sender="verifier", receiver="builder")
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "SEPARATION_OF_DUTIES_VIOLATION"

    def test_unlisted_sender_denied_by_default(self):
        policy = SeparationOfDutiesPolicy()
        msg = Message(message_type="TEST", sender="stranger", receiver="orch")
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "SENDER_NOT_IN_ALLOWLIST"

    def test_unlisted_sender_allowed_when_fail_open(self):
        policy = SeparationOfDutiesPolicy(default_allow_unlisted=True)
        msg = Message(message_type="TEST", sender="stranger", receiver="orch")
        assert policy.authorize_send(msg).is_ok()

    def test_missing_sender_denied(self):
        policy = SeparationOfDutiesPolicy(default_allow_unlisted=True)
        msg = Message(message_type="TEST", receiver="orch")
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "MISSING_SENDER"

    def test_allow_is_chainable_and_accumulates(self):
        policy = SeparationOfDutiesPolicy()
        policy.allow("orch", "a").allow("orch", "b")
        assert policy.sender_allowlist["orch"] == {"a", "b"}


# --------------------------------------------------------------------------- #
# SeparationOfDutiesPolicy — artifact-ref-only payload
# --------------------------------------------------------------------------- #
class TestArtifactRefPayloadPolicy:
    def _policy(self, **kw):
        # sender permitted so payload rules are what we exercise
        return SeparationOfDutiesPolicy(**kw).allow("verifier", "orch")

    def test_guarded_type_requires_ref(self):
        policy = self._policy()
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="orch",
            payload={"gate": "G5", "verdict": "PASS"},
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "MISSING_ARTIFACT_REF"

    def test_guarded_type_with_ref_passes(self):
        policy = self._policy()
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="orch",
            payload={"gate": "G5", "verdict": "PASS", "artifact": _ref_dict()},
        )
        assert policy.authorize_send(msg).is_ok()

    def test_prose_rejected(self):
        policy = self._policy(max_prose_chars=32)
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="orch",
            payload={
                "artifact": _ref_dict(),
                "reasoning": "x" * 100,  # smuggled narrative
            },
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        err = result.unwrap_err()
        assert err["errorType"] == "PROSE_IN_ARTIFACT_PAYLOAD"
        assert err["details"]["field"] == "reasoning"

    def test_prose_detected_in_nested_structure(self):
        policy = self._policy(max_prose_chars=16)
        msg = Message(
            message_type=WORK_PACKAGE,
            sender="verifier",
            receiver="orch",
            payload={"brief": _ref_dict(), "notes": ["ok", "y" * 50]},
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["details"]["field"] == "notes[1]"

    def test_short_control_strings_are_not_prose(self):
        policy = self._policy(max_prose_chars=512)
        msg = Message(
            message_type=WORK_PACKAGE,
            sender="verifier",
            receiver="orch",
            payload={
                "package_id": "pkg-001",
                "role": "backend-engineer",
                "file_scope": ["maple/foo.py", "tests/test_foo.py"],
                "brief": _ref_dict(),
            },
        )
        assert policy.authorize_send(msg).is_ok()

    def test_ref_sha_is_not_counted_as_prose(self):
        # A ref's 64-char sha256 must not trip the prose check even when the
        # ceiling is below 64 (the sha is fixed-width structure, not prose).
        # The ceiling still applies to the ref's path (see M1 regression test).
        policy = self._policy(max_prose_chars=32)
        msg = Message(
            message_type=WORK_PACKAGE,
            sender="verifier",
            receiver="orch",
            payload={"brief": _ref_dict(path="docs/q.md")},
        )
        assert policy.authorize_send(msg).is_ok()

    def test_non_guarded_type_skips_payload_policy(self):
        policy = self._policy(max_prose_chars=8)
        msg = Message(
            message_type="CHAT",
            sender="verifier",
            receiver="orch",
            payload={"reasoning": "a very long free-form explanation " * 5},
        )
        assert policy.authorize_send(msg).is_ok()

    def test_require_artifact_ref_can_be_disabled(self):
        policy = SeparationOfDutiesPolicy(require_artifact_ref=False).allow(
            "verifier", "orch"
        )
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="orch",
            payload={"gate": "G5", "verdict": "PASS"},
        )
        assert policy.authorize_send(msg).is_ok()


# --------------------------------------------------------------------------- #
# fresh_context_verifier_preset
# --------------------------------------------------------------------------- #
class TestPreset:
    def _preset(self):
        return fresh_context_verifier_preset(
            orchestrator="orch",
            builders=["backend", "frontend"],
            verifiers=["code-reviewer", "security-reviewer"],
        )

    def _send(self, policy, sender, receiver, message_type="TEST", payload=None):
        msg = Message(
            message_type=message_type,
            sender=sender,
            receiver=receiver,
            payload=payload,
        )
        return policy.authorize_send(msg)

    def test_orchestrator_reaches_builders_and_verifiers(self):
        p = self._preset()
        assert self._send(p, "orch", "backend").is_ok()
        assert self._send(p, "orch", "code-reviewer").is_ok()

    def test_builder_replies_only_to_orchestrator(self):
        p = self._preset()
        assert self._send(p, "backend", "orch").is_ok()
        assert self._send(p, "backend", "frontend").is_err()
        assert self._send(p, "backend", "code-reviewer").is_err()

    def test_verifier_never_reaches_a_builder(self):
        p = self._preset()
        assert self._send(p, "code-reviewer", "orch").is_ok()
        result = self._send(p, "code-reviewer", "backend")
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "SEPARATION_OF_DUTIES_VIOLATION"

    def test_verifier_cannot_reach_another_verifier(self):
        p = self._preset()
        assert self._send(p, "code-reviewer", "security-reviewer").is_err()

    def test_preset_guards_doctrine_message_types(self):
        p = self._preset()
        # GATE.RESULT from verifier to orch still needs an artifact ref
        assert self._send(
            p, "code-reviewer", "orch", GATE_RESULT, {"verdict": "PASS"}
        ).is_err()
        assert self._send(
            p,
            "code-reviewer",
            "orch",
            GATE_RESULT,
            {"verdict": "PASS", "artifact": _ref_dict()},
        ).is_ok()

    def test_custom_guarded_types(self):
        p = fresh_context_verifier_preset(
            "orch", ["b"], ["v"], guarded_types=["REVIEW.NOTE"]
        )
        assert "REVIEW.NOTE" in p.guarded_types
        assert WORK_PACKAGE not in p.guarded_types


# --------------------------------------------------------------------------- #
# attach_to_config
# --------------------------------------------------------------------------- #
class TestAttachToConfig:
    def test_creates_security_config_when_absent(self):
        policy = SeparationOfDutiesPolicy()
        cfg = Config(agent_id="a", broker_url="memory://local")
        returned = attach_to_config(cfg, policy)
        assert returned is cfg
        assert cfg.security is not None
        assert cfg.security.separation_policy is policy

    def test_reuses_existing_security_config(self):
        policy = SeparationOfDutiesPolicy()
        sec = SecurityConfig(auth_type="token", credentials="secret")
        cfg = Config(agent_id="a", broker_url="memory://local", security=sec)
        attach_to_config(cfg, policy)
        assert cfg.security is sec  # not replaced
        assert sec.separation_policy is policy


# --------------------------------------------------------------------------- #
# Broker integration — enforcement as a runtime guarantee
# --------------------------------------------------------------------------- #
def _reset_broker_singleton():
    MessageBroker._instance = None
    MessageBroker._agent_queues = {}
    MessageBroker._agent_handlers = {}
    MessageBroker._temp_handlers = {}
    MessageBroker._topic_subscribers = {}
    MessageBroker._topic_handlers = {}


@pytest.fixture(autouse=True)
def reset_broker():
    _reset_broker_singleton()
    yield
    _reset_broker_singleton()


class TestBrokerEnforcement:
    def _broker_with_preset(self):
        policy = fresh_context_verifier_preset(
            orchestrator="orch",
            builders=["builder"],
            verifiers=["verifier"],
        )
        config = attach_to_config(
            Config(agent_id="orch", broker_url="memory://local"), policy
        )
        broker = MessageBroker(config)
        # Subscribe so the AuthorizationManager assigns the default 'agent'
        # role; that isolates this test to separation-of-duties enforcement.
        for agent_id in ("orch", "builder", "verifier"):
            broker.subscribe(agent_id, lambda m: None)
        return broker

    def test_verifier_to_builder_is_rejected(self):
        broker = self._broker_with_preset()
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="builder",
            payload={"verdict": "FAIL", "artifact": _ref_dict()},
        )
        with pytest.raises(SecurityError):
            broker.send(msg)

    def test_verifier_to_orchestrator_with_ref_is_accepted(self):
        broker = self._broker_with_preset()
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="orch",
            payload={"gate": "G5", "verdict": "PASS", "artifact": _ref_dict()},
        )
        message_id = broker.send(msg)
        assert isinstance(message_id, str)

    def test_guarded_payload_without_ref_is_rejected_by_broker(self):
        broker = self._broker_with_preset()
        msg = Message(
            message_type=WORK_PACKAGE,
            sender="orch",
            receiver="builder",
            payload={"package_id": "pkg-1", "role": "backend"},  # no ref
        )
        with pytest.raises(SecurityError):
            broker.send(msg)

    def test_no_policy_means_no_enforcement(self):
        # Sanity: a plain broker (no separation policy) does not raise.
        config = Config(agent_id="plain", broker_url="memory://local")
        broker = MessageBroker(config)
        broker.subscribe("verifier", lambda m: None)
        broker.subscribe("builder", lambda m: None)
        msg = Message(
            message_type=GATE_RESULT, sender="verifier", receiver="builder"
        )
        assert isinstance(broker.send(msg), str)


# --------------------------------------------------------------------------- #
# Regression tests for G4 fresh-context review findings.
# Each proves a bypass the direct-send allowlist did NOT originally cover.
# --------------------------------------------------------------------------- #
class TestReviewRegressions:
    # -- H1: topic publish must not bypass the allowlist ------------------- #
    def _preset_broker(self):
        policy = fresh_context_verifier_preset(
            orchestrator="orch", builders=["builder"], verifiers=["verifier"]
        )
        cfg = attach_to_config(
            Config(agent_id="orch", broker_url="memory://local"), policy
        )
        return MessageBroker(cfg)

    def test_publish_verifier_to_builder_topic_rejected(self):
        broker = self._preset_broker()
        broker.subscribe_topic("reviews", lambda t, m: None, agent_id="builder")
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            payload={"verdict": "FAIL", "artifact": _ref_dict()},
        )
        with pytest.raises(SecurityError):
            broker.publish("reviews", msg)

    def test_publish_orchestrator_to_builder_topic_allowed(self):
        broker = self._preset_broker()
        broker.subscribe_topic("dispatch", lambda t, m: None, agent_id="builder")
        msg = Message(
            message_type=WORK_PACKAGE,
            sender="orch",
            payload={"package_id": "p1", "brief": _ref_dict()},
        )
        assert isinstance(broker.publish("dispatch", msg), str)

    # -- H2: singleton must adopt a policy supplied on a later construction - #
    def test_singleton_adopts_policy_from_later_config(self):
        # First construction has NO policy (e.g. a builder built first).
        MessageBroker(Config(agent_id="first", broker_url="memory://local"))
        # Later construction carries the policy.
        policy = fresh_context_verifier_preset("orch", ["builder"], ["verifier"])
        cfg = attach_to_config(
            Config(agent_id="orch", broker_url="memory://local"), policy
        )
        broker = MessageBroker(cfg)
        assert broker._separation_policy is policy
        for agent_id in ("orch", "builder", "verifier"):
            broker.subscribe(agent_id, lambda m: None)
        msg = Message(
            message_type=GATE_RESULT,
            sender="verifier",
            receiver="builder",
            payload={"artifact": _ref_dict()},
        )
        with pytest.raises(SecurityError):
            broker.send(msg)

    def test_set_separation_policy_explicit(self):
        broker = MessageBroker(
            Config(agent_id="plain2", broker_url="memory://local")
        )
        assert broker._separation_policy is None
        policy = fresh_context_verifier_preset("orch", ["builder"], ["verifier"])
        broker.set_separation_policy(policy)
        assert broker._separation_policy is policy

    # -- M1: prose smuggled into a ref's path is caught ------------------- #
    def test_long_ref_path_is_rejected_as_prose(self):
        policy = SeparationOfDutiesPolicy(max_prose_chars=64).allow("v", "o")
        ref = {"path": "docs/" + "x" * 300, "sha256": "a" * 64}
        msg = Message(
            message_type=WORK_PACKAGE, sender="v", receiver="o", payload={"brief": ref}
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        err = result.unwrap_err()
        assert err["errorType"] == "PROSE_IN_ARTIFACT_PAYLOAD"
        assert err["details"]["field"] == "brief.path"

    def test_ref_path_with_newline_is_not_a_valid_ref(self):
        assert not is_artifact_ref({"path": "a\nb", "sha256": "a" * 64})

    # -- M2: lowercase custom guarded types are normalized ---------------- #
    def test_lowercase_guarded_type_still_guards(self):
        policy = fresh_context_verifier_preset(
            "o", ["b"], ["v"], guarded_types=["review.note"]
        )
        assert "REVIEW.NOTE" in policy.guarded_types
        msg = Message(
            message_type="review.note",  # Message upper-cases this
            sender="v",
            receiver="o",
            payload={"note": "short"},  # no artifact ref
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "MISSING_ARTIFACT_REF"

    # -- L1: prose in a dict key is caught -------------------------------- #
    def test_long_dict_key_is_rejected_as_prose(self):
        policy = SeparationOfDutiesPolicy(max_prose_chars=16).allow("v", "o")
        payload = {"brief": _ref_dict(), "k" * 100: "ok"}
        msg = Message(
            message_type=WORK_PACKAGE, sender="v", receiver="o", payload=payload
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "PROSE_IN_ARTIFACT_PAYLOAD"

    # -- L2: a listed sender with no receiver is denied (fail-closed) ----- #
    def test_listed_sender_without_receiver_denied(self):
        policy = SeparationOfDutiesPolicy().allow("v", "o")
        msg = Message(message_type="TEST", sender="v")  # no receiver
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "SEPARATION_OF_DUTIES_VIOLATION"

    # -- L3: deep / cyclic payloads are rejected, not crashed on --------- #
    def test_deeply_nested_payload_rejected(self):
        policy = SeparationOfDutiesPolicy().allow("v", "o")
        inner = {}
        node = inner
        for _ in range(_MAX_PAYLOAD_DEPTH + 5):
            nxt = {}
            node["n"] = nxt
            node = nxt
        payload = {"brief": _ref_dict(), "deep": inner}
        msg = Message(
            message_type=WORK_PACKAGE, sender="v", receiver="o", payload=payload
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "PAYLOAD_TOO_DEEP"

    def test_cyclic_payload_rejected(self):
        policy = SeparationOfDutiesPolicy().allow("v", "o")
        payload = {"brief": _ref_dict()}
        payload["self"] = payload  # cycle
        msg = Message(
            message_type=WORK_PACKAGE, sender="v", receiver="o", payload=payload
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "PAYLOAD_TOO_DEEP"

    def test_deep_payload_without_ref_rejected(self):
        # No ref anywhere: the depth guard must trip inside the ref search
        # itself (not only in the prose scan).
        policy = SeparationOfDutiesPolicy().allow("v", "o")
        node = payload = {}
        for _ in range(_MAX_PAYLOAD_DEPTH + 5):
            nxt = {}
            node["n"] = nxt
            node = nxt
        msg = Message(
            message_type=WORK_PACKAGE, sender="v", receiver="o", payload=payload
        )
        result = policy.authorize_send(msg)
        assert result.is_err()
        assert result.unwrap_err()["errorType"] == "PAYLOAD_TOO_DEEP"
