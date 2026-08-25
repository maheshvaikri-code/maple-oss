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

# maple/adapters/doctrine_adapter.py
# Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

"""
Doctrine profile — first-class ``WORK.PACKAGE`` / ``GATE.RESULT`` schemas.

Delivers enhancement ask #4 from ``.Doctrine/integrations/maple.md``: typed
builders and validators for the two doctrine protocol message types, beside
the A2A/MCP adapters, so a doctrine workforce speaks a checked vocabulary
instead of ad-hoc dicts.

Payloads carry artifact **hashedrefs** (``{path, sha256}``), never prose, so a
message built here already satisfies the fresh-context verifier preset
(``maple.security.separation``). Schemas (per the integration doc):

* ``WORK.PACKAGE`` — ``package_id``, ``role``, ``file_scope`` (paths), and a
  ``brief`` artifact ref.
* ``GATE.RESULT`` — ``gate``, ``verdict`` (one of :data:`GATE_VERDICTS`), an
  ``artifact`` ref, and optional short ``evidence``.
"""

from typing import Any, Dict, List, Optional, Union, cast

from ..core.message import Message
from ..core.result import Result
from ..core.types import Priority
from ..security.separation import (
    GATE_RESULT,
    WORK_PACKAGE,
    ArtifactRef,
    is_artifact_ref,
)

# Canonical gate verdicts. Honest reporting is a doctrine non-negotiable:
# "blocked" and "failed" are first-class, respectable statuses.
GATE_VERDICTS = ("PASS", "FAIL", "BLOCKED", "WAIVED")

RefLike = Union[ArtifactRef, Dict[str, str]]


def _ref_dict(ref: Any) -> Optional[Dict[str, str]]:
    """Normalize an ArtifactRef or a ``{path, sha256}`` dict; None if invalid."""
    if isinstance(ref, ArtifactRef):
        return cast(Dict[str, str], ref.to_dict())
    if is_artifact_ref(ref):
        return cast(Dict[str, str], ref)
    return None


def _err(error_type: str, message: str, **details: Any) -> Result:
    return Result.err({"errorType": error_type, "message": message, "details": details})


# --------------------------------------------------------------------------- #
# WORK.PACKAGE
# --------------------------------------------------------------------------- #
def validate_work_package_payload(
    payload: Any,
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Validate a WORK.PACKAGE payload dict; return it on success."""
    if not isinstance(payload, dict):
        return _err("INVALID_WORK_PACKAGE", "payload must be a dict")

    package_id = payload.get("package_id")
    if not (isinstance(package_id, str) and package_id):
        return _err("INVALID_WORK_PACKAGE", "package_id must be a non-empty string")

    role = payload.get("role")
    if not (isinstance(role, str) and role):
        return _err("INVALID_WORK_PACKAGE", "role must be a non-empty string")

    file_scope = payload.get("file_scope")
    if not (
        isinstance(file_scope, (list, tuple))
        and file_scope
        and all(isinstance(p, str) and p for p in file_scope)
    ):
        return _err(
            "INVALID_WORK_PACKAGE",
            "file_scope must be a non-empty list of path strings",
        )

    if not is_artifact_ref(payload.get("brief")):
        return _err(
            "INVALID_WORK_PACKAGE",
            "brief must be an artifact reference {path, sha256}",
        )

    return Result.ok(payload)


def build_work_package(
    package_id: str,
    role: str,
    file_scope: List[str],
    brief: RefLike,
    *,
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    priority: Priority = Priority.HIGH,
) -> Result[Message, Dict[str, Any]]:
    """Build a schema-valid ``WORK.PACKAGE`` :class:`Message` (or an error)."""
    brief_dict = _ref_dict(brief)
    if brief_dict is None:
        return _err(
            "INVALID_WORK_PACKAGE",
            "brief must be an ArtifactRef or {path, sha256} dict",
        )

    payload = {
        "package_id": package_id,
        "role": role,
        "file_scope": (
            list(file_scope) if isinstance(file_scope, (list, tuple)) else file_scope
        ),
        "brief": brief_dict,
    }

    check = validate_work_package_payload(payload)
    if check.is_err():
        return Result.err(check.unwrap_err())

    try:
        message = Message(
            message_type=WORK_PACKAGE,
            sender=sender,
            receiver=receiver,
            priority=priority,
            payload=payload,
        )
    except (ValueError, TypeError) as exc:
        return _err("INVALID_WORK_PACKAGE", f"could not build message: {exc}")

    return Result.ok(message)


def validate_work_package(message: Any) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Validate an incoming WORK.PACKAGE :class:`Message`; return its payload."""
    mtype = getattr(message, "message_type", None)
    if mtype != WORK_PACKAGE:
        return _err(
            "WRONG_MESSAGE_TYPE",
            f"expected {WORK_PACKAGE}, got {mtype}",
        )
    return validate_work_package_payload(getattr(message, "payload", None))


# --------------------------------------------------------------------------- #
# GATE.RESULT
# --------------------------------------------------------------------------- #
def validate_gate_result_payload(
    payload: Any,
) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Validate a GATE.RESULT payload dict; return it on success."""
    if not isinstance(payload, dict):
        return _err("INVALID_GATE_RESULT", "payload must be a dict")

    gate = payload.get("gate")
    if not (isinstance(gate, str) and gate):
        return _err("INVALID_GATE_RESULT", "gate must be a non-empty string")

    verdict = payload.get("verdict")
    if verdict not in GATE_VERDICTS:
        return _err(
            "INVALID_GATE_RESULT",
            f"verdict must be one of {GATE_VERDICTS}",
            verdict=verdict,
        )

    if not is_artifact_ref(payload.get("artifact")):
        return _err(
            "INVALID_GATE_RESULT",
            "artifact must be an artifact reference {path, sha256}",
        )

    return Result.ok(payload)


def build_gate_result(
    gate: str,
    verdict: str,
    artifact: RefLike,
    *,
    evidence: Optional[str] = None,
    sender: Optional[str] = None,
    receiver: Optional[str] = None,
    priority: Priority = Priority.HIGH,
) -> Result[Message, Dict[str, Any]]:
    """Build a schema-valid ``GATE.RESULT`` :class:`Message` (or an error)."""
    artifact_dict = _ref_dict(artifact)
    if artifact_dict is None:
        return _err(
            "INVALID_GATE_RESULT",
            "artifact must be an ArtifactRef or {path, sha256} dict",
        )

    verdict_norm = verdict.upper() if isinstance(verdict, str) else verdict
    payload: Dict[str, Any] = {
        "gate": gate,
        "verdict": verdict_norm,
        "artifact": artifact_dict,
    }
    if evidence is not None:
        payload["evidence"] = evidence

    check = validate_gate_result_payload(payload)
    if check.is_err():
        return Result.err(check.unwrap_err())

    try:
        message = Message(
            message_type=GATE_RESULT,
            sender=sender,
            receiver=receiver,
            priority=priority,
            payload=payload,
        )
    except (ValueError, TypeError) as exc:
        return _err("INVALID_GATE_RESULT", f"could not build message: {exc}")

    return Result.ok(message)


def validate_gate_result(message: Any) -> Result[Dict[str, Any], Dict[str, Any]]:
    """Validate an incoming GATE.RESULT :class:`Message`; return its payload."""
    mtype = getattr(message, "message_type", None)
    if mtype != GATE_RESULT:
        return _err(
            "WRONG_MESSAGE_TYPE",
            f"expected {GATE_RESULT}, got {mtype}",
        )
    return validate_gate_result_payload(getattr(message, "payload", None))


# --------------------------------------------------------------------------- #
# Agent-bound adapter (matches the A2A/MCP adapter family)
# --------------------------------------------------------------------------- #
class DoctrineAdapter:
    """First-class doctrine message schemas bound to a MAPLE agent.

    Wraps the module-level builders/validators so an agent can dispatch typed
    ``WORK.PACKAGE`` / ``GATE.RESULT`` messages directly. Emitted payloads
    carry artifact hashedrefs (not prose), so they pass the fresh-context
    verifier preset. Pairs with ``require_routable`` so a dispatch that cannot
    reach its receiver surfaces as ``Result.err`` rather than a silent enqueue.
    """

    def __init__(self, maple_agent: Any):
        self.maple_agent = maple_agent

    def send_work_package(
        self,
        receiver: str,
        package_id: str,
        role: str,
        file_scope: List[str],
        brief: RefLike,
        *,
        priority: Priority = Priority.HIGH,
        require_routable: bool = False,
    ) -> Result[str, Dict[str, Any]]:
        """Build and send a WORK.PACKAGE; returns the send Result."""
        built = build_work_package(
            package_id,
            role,
            file_scope,
            brief,
            sender=self.maple_agent.agent_id,
            receiver=receiver,
            priority=priority,
        )
        if built.is_err():
            return Result.err(built.unwrap_err())
        return cast(
            Result[str, Dict[str, Any]],
            self.maple_agent.send(built.unwrap(), require_routable=require_routable),
        )

    def send_gate_result(
        self,
        receiver: str,
        gate: str,
        verdict: str,
        artifact: RefLike,
        *,
        evidence: Optional[str] = None,
        priority: Priority = Priority.HIGH,
        require_routable: bool = False,
    ) -> Result[str, Dict[str, Any]]:
        """Build and send a GATE.RESULT; returns the send Result."""
        built = build_gate_result(
            gate,
            verdict,
            artifact,
            evidence=evidence,
            sender=self.maple_agent.agent_id,
            receiver=receiver,
            priority=priority,
        )
        if built.is_err():
            return Result.err(built.unwrap_err())
        return cast(
            Result[str, Dict[str, Any]],
            self.maple_agent.send(built.unwrap(), require_routable=require_routable),
        )
