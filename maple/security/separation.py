"""
Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

This file is part of MAPLE - Multi Agent Protocol Language Engine.

MAPLE - Multi Agent Protocol Language Engine is free software: you can redistribute it and/or
modify it under the terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.
MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details. You should have
received a copy of the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
Language Engine. If not, see <https://www.gnu.org/licenses/>.
"""

# maple/security/separation.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

"""
Separation-of-duties runtime policy for MAPLE — the "fresh-context verifier"
preset.

Delivers enhancement ask #3 from ``.Doctrine/integrations/maple.md``: a
broker-enforced per-agent *sender allowlist* plus an *artifact-ref-only*
payload policy, so that separation of duties between builders and verifiers
is a runtime guarantee instead of a convention.

Two guarantees:

* **Sender allowlist** (deterministic) — an agent may send only to the
  receivers on its allowlist; an unlisted agent may send to no one unless
  ``default_allow_unlisted`` is set. This is the core separation-of-duties
  guarantee: a verifier can be wired so it can *only* reply to the
  orchestrator, never back to the builder it is judging.
* **Artifact-ref-only payload** (structural) — for ``guarded_types``
  (default ``WORK.PACKAGE`` / ``GATE.RESULT``), the payload must carry at
  least one well-formed artifact reference and may not carry prose (any
  string — value, dict key, or a ref's ``path`` — longer than
  ``max_prose_chars``). This keeps a builder's reasoning out of a verifier's
  context — the verifier receives a content-pinned pointer and reads the
  artifact fresh.

Scope: enforcement is applied by the in-memory ``MessageBroker`` (``send``
and ``publish``). Alternate transports (``nats_broker``, S2) do not yet
consult the policy — attach it on the in-memory broker, or treat those
transports as out of the guarantee until they wire it in.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional, Set

from ..core.result import Result

# Doctrine protocol message types that must carry artifact references only.
# Message.__init__ upper-cases message_type, so these match verbatim.
WORK_PACKAGE = "WORK.PACKAGE"
GATE_RESULT = "GATE.RESULT"

# A sha256 hex digest: 64 lowercase hex characters.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Maximum payload nesting depth the policy will traverse. Beyond this the
# payload is rejected rather than risking unbounded recursion on a crafted
# (deeply nested or self-referential) structure.
_MAX_PAYLOAD_DEPTH = 100


class _PayloadTooDeep(Exception):
    """Internal signal: payload traversal exceeded _MAX_PAYLOAD_DEPTH."""


@dataclass(frozen=True)
class ArtifactRef:
    """A content-pinned pointer to an artifact: a path plus its sha256.

    Doctrine payloads carry *references* to artifacts, never their prose. A
    verifier receives the ref and reads the artifact fresh, so a builder's
    narrative can never travel into the verifier's context.
    """

    path: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or not self.path:
            raise ValueError("ArtifactRef.path must be a non-empty string")
        if not isinstance(self.sha256, str) or not _SHA256_RE.match(self.sha256):
            raise ValueError(
                "ArtifactRef.sha256 must be a 64-character lowercase hex digest"
            )

    def to_dict(self) -> Dict[str, str]:
        """Serialize to the wire shape ``{"path": ..., "sha256": ...}``."""
        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def of(cls, path: str, content: Any) -> "ArtifactRef":
        """Build a ref from an artifact's path and its raw content.

        ``content`` may be ``bytes`` or ``str`` (encoded as UTF-8).
        """
        if isinstance(content, str):
            content = content.encode("utf-8")
        return cls(path=path, sha256=hashlib.sha256(content).hexdigest())

    @classmethod
    def for_file(cls, path: str) -> "ArtifactRef":
        """Build a ref by hashing a file on disk."""
        with open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        return cls(path=path, sha256=digest)


def is_artifact_ref(value: Any) -> bool:
    """Return True if ``value`` is a well-formed artifact reference dict.

    A ref is exactly ``{"path": <non-empty str>, "sha256": <64-hex str>}``
    — no extra keys, so it cannot double as a prose envelope.
    """
    if not isinstance(value, dict):
        return False
    if set(value.keys()) != {"path", "sha256"}:
        return False
    path = value.get("path")
    sha = value.get("sha256")
    return (
        isinstance(path, str)
        and bool(path)
        and "\n" not in path
        and "\r" not in path
        and isinstance(sha, str)
        and bool(_SHA256_RE.match(sha))
    )


@dataclass
class SeparationOfDutiesPolicy:
    """Broker-enforced separation of duties for a MAPLE agent fleet.

    Attributes:
        sender_allowlist: Maps an agent id to the set of receivers it may
            send to. An agent absent from the map may send to no one unless
            ``default_allow_unlisted`` is True.
        guarded_types: Message types whose payloads must be artifact-ref-only.
        require_artifact_ref: If True, a guarded payload must contain at
            least one well-formed artifact reference.
        max_prose_chars: Longest permitted string value inside a guarded
            payload. Strings longer than this are rejected as prose.
        default_allow_unlisted: If True, an agent with no allowlist entry may
            send to anyone (fail-open). Default False (fail-closed).

    The policy is read-only during ``authorize_send`` (no mutation), so it is
    safe to share one instance across the broker's delivery threads. Mutation
    (``allow``) is a setup-time operation.
    """

    sender_allowlist: Dict[str, Set[str]] = field(default_factory=dict)
    guarded_types: Set[str] = field(default_factory=lambda: {WORK_PACKAGE, GATE_RESULT})
    require_artifact_ref: bool = True
    max_prose_chars: int = 512
    default_allow_unlisted: bool = False

    def __post_init__(self) -> None:
        # Message.__init__ upper-cases message_type, so guarded_types must be
        # upper-cased too — otherwise a lower-case entry silently guards
        # nothing (fail-open).
        self.guarded_types = {str(t).upper() for t in self.guarded_types}

    def allow(self, sender: str, *receivers: str) -> "SeparationOfDutiesPolicy":
        """Grant ``sender`` permission to send to each of ``receivers``.

        Returns self for chaining. Calling with no receivers registers the
        sender with an (initially empty) allowlist, which under the default
        fail-closed policy still means "may send to no one".
        """
        bucket = self.sender_allowlist.setdefault(sender, set())
        bucket.update(receivers)
        return self

    def authorize_send(self, message: Any) -> Result[None, Dict[str, Any]]:
        """Authorize a message against the sender allowlist and payload policy.

        Returns ``Result.ok(None)`` when the send is permitted, or
        ``Result.err({...})`` describing the first violation found.
        """
        sender = getattr(message, "sender", None)
        receiver = getattr(message, "receiver", None)

        sender_check = self._check_sender(sender, receiver)
        if sender_check.is_err():
            return sender_check

        return self._check_payload(message)

    # -- internals ---------------------------------------------------------

    def _check_sender(
        self, sender: Optional[str], receiver: Optional[str]
    ) -> Result[None, Dict[str, Any]]:
        if not sender:
            return Result.err(
                {
                    "errorType": "MISSING_SENDER",
                    "message": "Message has no sender; cannot enforce separation of duties",
                }
            )

        allowed = self.sender_allowlist.get(sender)
        if allowed is None:
            if self.default_allow_unlisted:
                return Result.ok(None)
            return Result.err(
                {
                    "errorType": "SENDER_NOT_IN_ALLOWLIST",
                    "message": (
                        f"Agent '{sender}' has no send allowlist; "
                        "separation-of-duties policy denies all sends"
                    ),
                    "details": {"sender": sender},
                }
            )

        if receiver is None:
            # A listed sender under an active policy must name an explicit
            # receiver — a receiver-less send cannot be checked, so deny it
            # (fail-closed) rather than let it through.
            return Result.err(
                {
                    "errorType": "SEPARATION_OF_DUTIES_VIOLATION",
                    "message": (
                        f"Agent '{sender}' sent a message with no receiver; "
                        "separation-of-duties requires an explicit receiver"
                    ),
                    "details": {"sender": sender, "receiver": None},
                }
            )

        if receiver not in allowed:
            return Result.err(
                {
                    "errorType": "SEPARATION_OF_DUTIES_VIOLATION",
                    "message": (
                        f"Agent '{sender}' is not permitted to send to '{receiver}'"
                    ),
                    "details": {
                        "sender": sender,
                        "receiver": receiver,
                        "allowed": sorted(allowed),
                    },
                }
            )

        return Result.ok(None)

    def _check_payload(self, message: Any) -> Result[None, Dict[str, Any]]:
        message_type = getattr(message, "message_type", None)
        if message_type not in self.guarded_types:
            return Result.ok(None)

        payload = getattr(message, "payload", None) or {}

        try:
            has_ref = self._has_artifact_ref(payload)
            prose_field = self._find_prose(payload)
        except _PayloadTooDeep:
            return Result.err(
                {
                    "errorType": "PAYLOAD_TOO_DEEP",
                    "message": (
                        f"{message_type} payload nests deeper than "
                        f"{_MAX_PAYLOAD_DEPTH} levels (or is self-referential); "
                        "refusing to traverse"
                    ),
                    "details": {
                        "messageType": message_type,
                        "maxDepth": _MAX_PAYLOAD_DEPTH,
                    },
                }
            )

        if self.require_artifact_ref and not has_ref:
            return Result.err(
                {
                    "errorType": "MISSING_ARTIFACT_REF",
                    "message": (
                        f"{message_type} payload must carry at least one artifact "
                        "reference {path, sha256}"
                    ),
                    "details": {"messageType": message_type},
                }
            )

        if prose_field is not None:
            return Result.err(
                {
                    "errorType": "PROSE_IN_ARTIFACT_PAYLOAD",
                    "message": (
                        f"{message_type} payload field '{prose_field}' exceeds "
                        f"{self.max_prose_chars} characters; builder prose must not "
                        "travel to a verifier — pass an artifact reference instead"
                    ),
                    "details": {
                        "messageType": message_type,
                        "field": prose_field,
                        "maxProseChars": self.max_prose_chars,
                    },
                }
            )

        return Result.ok(None)

    def _has_artifact_ref(self, value: Any, depth: int = 0) -> bool:
        """True if ``value`` contains at least one well-formed artifact ref.

        Short-circuits on the first ref found; guards against pathological
        nesting via ``_MAX_PAYLOAD_DEPTH``.
        """
        if depth > _MAX_PAYLOAD_DEPTH:
            raise _PayloadTooDeep()
        if is_artifact_ref(value):
            return True
        if isinstance(value, dict):
            return any(self._has_artifact_ref(v, depth + 1) for v in value.values())
        if isinstance(value, (list, tuple)):
            return any(self._has_artifact_ref(v, depth + 1) for v in value)
        return False

    def _find_prose(self, value: Any, path: str = "", depth: int = 0) -> Optional[str]:
        """Return a dotted field path to the first prose violation, or None.

        "Prose" is any string longer than ``max_prose_chars``, wherever it
        appears — a value, a dict *key*, or an artifact ref's ``path`` (the
        ref's only free-text field; its ``sha256`` is fixed-width). This
        closes the "smuggle narrative in the path/key" bypass.
        """
        if depth > _MAX_PAYLOAD_DEPTH:
            raise _PayloadTooDeep()

        if is_artifact_ref(value):
            if len(value["path"]) > self.max_prose_chars:
                return f"{path}.path" if path else "path"
            return None
        if isinstance(value, str):
            if len(value) > self.max_prose_chars:
                return path or "<payload>"
            return None
        if isinstance(value, dict):
            for key, item in value.items():
                key_str = str(key)
                if len(key_str) > self.max_prose_chars:
                    return f"{path}.<key>" if path else "<key>"
                child = f"{path}.{key_str}" if path else key_str
                hit = self._find_prose(item, child, depth + 1)
                if hit is not None:
                    return hit
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                child = f"{path}[{index}]" if path else f"[{index}]"
                hit = self._find_prose(item, child, depth + 1)
                if hit is not None:
                    return hit
        return None


def fresh_context_verifier_preset(
    orchestrator: str,
    builders: Iterable[str],
    verifiers: Iterable[str],
    *,
    guarded_types: Optional[Iterable[str]] = None,
    max_prose_chars: int = 512,
) -> SeparationOfDutiesPolicy:
    """Build the doctrine's fresh-context separation-of-duties policy.

    Wiring (see ``.Doctrine/03-parallel-execution.md`` and
    ``.Doctrine/integrations/maple.md``):

    * the **orchestrator** may dispatch to every builder and verifier;
    * each **builder** may reply only to the orchestrator;
    * each **verifier** may reply only to the orchestrator — never to a
      builder, so a verifier's review can never be routed back to the author
      it is judging (separation of duties);
    * ``WORK.PACKAGE`` / ``GATE.RESULT`` payloads must be artifact-ref-only.

    Args:
        orchestrator: The orchestrating agent's id.
        builders: Builder/worker agent ids.
        verifiers: Verifier agent ids (code-reviewer, security-reviewer, ...).
        guarded_types: Override the artifact-ref-only message types.
        max_prose_chars: Longest permitted string in a guarded payload.

    Returns:
        A configured :class:`SeparationOfDutiesPolicy`.
    """
    builders = list(builders)
    verifiers = list(verifiers)

    guarded = (
        set(guarded_types) if guarded_types is not None else {WORK_PACKAGE, GATE_RESULT}
    )
    policy = SeparationOfDutiesPolicy(
        guarded_types=guarded,
        max_prose_chars=max_prose_chars,
    )

    # Orchestrator dispatches to every worker and verifier.
    policy.allow(orchestrator, *builders, *verifiers)

    # Builders and verifiers reply only to the orchestrator.
    for worker in (*builders, *verifiers):
        policy.allow(worker, orchestrator)

    return policy


def attach_to_config(config: Any, policy: SeparationOfDutiesPolicy) -> Any:
    """Attach ``policy`` to a :class:`~maple.agent.config.Config` in place.

    Creates a minimal ``SecurityConfig`` if the config has none, so a caller
    can enable separation of duties without hand-assembling auth credentials.
    Returns the same config for chaining.
    """
    from ..agent.config import SecurityConfig  # local import avoids a cycle

    if getattr(config, "security", None) is None:
        config.security = SecurityConfig(
            auth_type="none",
            credentials="",
            separation_policy=policy,
        )
    else:
        config.security.separation_policy = policy
    return config
