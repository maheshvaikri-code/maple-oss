"""Dependency-free loopback HTTP access to registered MAPLE workflows."""

from __future__ import annotations

import ipaddress
import json
import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Mapping, Optional, Tuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ..core.result import Result
from .interactions import HumanInputRequest, HumanInputStore
from .workflow import Workflow, WorkflowRun

Error = Dict[str, Any]
_MAX_PATH_BYTES = 4_096
_MAX_WORKFLOWS = 64
_DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_DEFAULT_CLIENT_TIMEOUT_SECONDS = 10.0
_MAX_HUMAN_INPUT_LIMIT = 1_000


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


def _validate_auth_token(auth_token: Optional[str]) -> None:
    if auth_token is None:
        return
    if not isinstance(auth_token, str) or not auth_token.strip():
        raise ValueError("auth_token must be a non-empty string when provided")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in auth_token):
        raise ValueError("auth_token must not contain control characters")


def _run_to_dict(run: WorkflowRun) -> Dict[str, Any]:
    """Convert a workflow result into the stable HTTP response shape."""
    return {
        "run_id": run.run_id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "state": dict(run.state),
        "completed_nodes": list(run.completed_nodes),
        "next_node": run.next_node,
        "checkpoint_version": run.checkpoint_version,
        "step_count": run.step_count,
        "interrupt_payload": run.interrupt_payload,
        "error": run.error,
    }


def _status_for_error(error: Error) -> int:
    error_type = error.get("errorType")
    if error_type in {"RUN_NOT_FOUND", "WORKFLOW_NOT_FOUND"}:
        return 404
    if error_type == "HUMAN_INPUT_NOT_FOUND":
        return 404
    if error_type in {"RUN_ID_EXISTS", "CHECKPOINT_CONFLICT"}:
        return 409
    if error_type in {
        "HUMAN_INPUT_CONFLICT",
        "HUMAN_INPUT_NOT_READY",
        "HUMAN_INPUT_ROUND_CONFLICT",
        "HUMAN_INPUT_ROUND_LIMIT",
    }:
        return 409
    if error_type in {
        "INVALID_STATE",
        "INVALID_IDENTIFIER",
        "INVALID_WORKFLOW",
        "INVALID_JSON",
        "REQUEST_BODY_INVALID",
        "WORKFLOW_MISMATCH",
        "HUMAN_INPUT_IDENTIFIER_INVALID",
        "HUMAN_INPUT_ACTOR_INVALID",
        "HUMAN_INPUT_LIMIT_INVALID",
        "HUMAN_INPUT_PROMPT_INVALID",
        "HUMAN_INPUT_REASON_INVALID",
        "HUMAN_INPUT_RESPONSE_INVALID",
        "HUMAN_INPUT_ROUND_LIMIT_INVALID",
        "HUMAN_INPUT_VALUE_INVALID",
        "HUMAN_INPUT_VALUE_TOO_DEEP",
        "HUMAN_INPUT_VALUE_TOO_LARGE",
    }:
        return 400
    if error_type == "HUMAN_INPUT_STORE_UNAVAILABLE":
        return 503
    if error_type == "HUMAN_INPUT_MULTI_ROUND_UNSUPPORTED":
        return 501
    if error_type in {
        "HUMAN_INPUT_ACTOR_REQUIRED",
        "HUMAN_INPUT_UNAUTHORIZED",
    }:
        return 403
    return 500


class WorkflowRegistry:
    """Thread-safe registry of workflows configured by the host process."""

    def __init__(self, *, max_workflows: int = _MAX_WORKFLOWS) -> None:
        if (
            not isinstance(max_workflows, int)
            or isinstance(max_workflows, bool)
            or not 0 < max_workflows <= _MAX_WORKFLOWS
        ):
            raise ValueError("max_workflows must be between 1 and 64")
        self.max_workflows = max_workflows
        self._workflows: Dict[str, Workflow] = {}
        self._lock = threading.RLock()

    def register(self, workflow: Workflow) -> Result[None, Error]:
        """Register a configured workflow before serving requests."""
        if not isinstance(workflow, Workflow):
            return Result.err(
                _error("INVALID_WORKFLOW", "WorkflowRegistry requires a Workflow.")
            )
        with self._lock:
            if workflow.name in self._workflows:
                return Result.err(
                    _error(
                        "WORKFLOW_EXISTS",
                        "A workflow with this name is already registered.",
                        workflow_name=workflow.name,
                    )
                )
            if len(self._workflows) >= self.max_workflows:
                return Result.err(
                    _error(
                        "WORKFLOW_LIMIT",
                        "WorkflowRegistry has reached its workflow limit.",
                        max_workflows=self.max_workflows,
                    )
                )
            self._workflows[workflow.name] = workflow
        return Result.ok(None)

    def _get(self, workflow_name: str) -> Result[Workflow, Error]:
        with self._lock:
            workflow = self._workflows.get(workflow_name)
        if workflow is None:
            return Result.err(
                _error(
                    "WORKFLOW_NOT_FOUND",
                    "Workflow was not found.",
                    workflow_name=workflow_name,
                )
            )
        return Result.ok(workflow)

    def run(
        self,
        workflow_name: str,
        initial_state: Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
    ) -> Result[WorkflowRun, Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        return workflow_result.unwrap().run(initial_state, run_id=run_id)

    def resume(
        self,
        workflow_name: str,
        run_id: str,
        *,
        resume_value: Any = None,
    ) -> Result[WorkflowRun, Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        return workflow_result.unwrap().resume(run_id, resume_value=resume_value)

    def inspect(
        self, workflow_name: str, run_id: str
    ) -> Result[Optional[WorkflowRun], Error]:
        workflow_result = self._get(workflow_name)
        if workflow_result.is_err():
            return Result.err(workflow_result.unwrap_err())
        workflow = workflow_result.unwrap()
        checkpoint_result = workflow.checkpoint_store.load(run_id)
        if checkpoint_result.is_err():
            return Result.err(checkpoint_result.unwrap_err())
        checkpoint = checkpoint_result.unwrap()
        if checkpoint is None:
            return Result.ok(None)
        if checkpoint.workflow_name != workflow.name:
            return Result.err(
                _error(
                    "WORKFLOW_MISMATCH",
                    "Stored run belongs to a different workflow.",
                    run_id=run_id,
                )
            )
        return Result.ok(WorkflowRun.from_checkpoint(checkpoint))


class _MAPLEHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: Any, handler: Any, application: Any) -> None:
        self.application = application
        super().__init__(address, handler)


class _RequestHandler(BaseHTTPRequestHandler):
    server: _MAPLEHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Do not log request bodies, session content, or credentials."""

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        try:
            if not self._authorize():
                return
            path = self._path_segments()
            if path is None:
                return
            if method == "GET" and path == ("healthz",):
                self._write_json(200, {"status": "ok", "service": "maple-run-server"})
                return
            if self._interaction_route(method, path):
                return
            if (
                method == "GET"
                and len(path) == 5
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
            ):
                self._inspect(path[2], path[4])
                return
            if (
                method == "POST"
                and len(path) == 4
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
            ):
                self._run(path[2])
                return
            if (
                method == "POST"
                and len(path) == 6
                and path[0:4]
                == (
                    "v1",
                    "workflows",
                    path[2],
                    "runs",
                )
                and path[5] == "resume"
            ):
                self._resume(path[2], path[4])
                return
            self._write_error(404, _error("NOT_FOUND", "Route was not found."))
        except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            self._write_error(
                400, _error("REQUEST_BODY_INVALID", "Request is invalid.")
            )
        except _ResponseWritten:
            return
        except Exception:
            self._write_error(
                500, _error("INTERNAL_ERROR", "Request could not be processed.")
            )

    def _interaction_route(self, method: str, path: Tuple[str, ...]) -> bool:
        store = self.server.application.human_input_store
        if not path or path[0:2] != ("v1", "interactions"):
            return False
        if store is None:
            self._write_error(
                503,
                _error(
                    "HUMAN_INPUT_STORE_UNAVAILABLE",
                    "No human input store is configured.",
                ),
            )
            return True
        if method == "GET" and len(path) == 4 and path[2] == "pending":
            try:
                limit = int(path[3])
            except ValueError:
                self._write_error(
                    400,
                    _error(
                        "HUMAN_INPUT_LIMIT_INVALID",
                        "Human input list limit must be an integer.",
                    ),
                )
                return True
            result = store.list_pending(limit)
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            self._write_json(
                200,
                {
                    "interactions": [
                        self._interaction_to_dict(item) for item in result.unwrap()
                    ]
                },
            )
            return True
        if method == "GET" and len(path) == 3:
            result = store.get(path[2])
            if result.is_err():
                self._write_error(
                    _status_for_error(result.unwrap_err()), result.unwrap_err()
                )
                return True
            request = result.unwrap()
            if request is None:
                self._write_error(
                    404,
                    _error(
                        "HUMAN_INPUT_NOT_FOUND", "Human input request was not found."
                    ),
                )
                return True
            self._write_json(200, {"interaction": self._interaction_to_dict(request)})
            return True
        if method == "POST" and len(path) == 4:
            self._mutate_interaction(store, path[2], path[3])
            return True
        self._write_error(404, _error("NOT_FOUND", "Interaction route was not found."))
        return True

    @staticmethod
    def _interaction_to_dict(request: HumanInputRequest) -> Dict[str, Any]:
        return cast(Dict[str, Any], request.to_dict())

    def _mutate_interaction(
        self, store: HumanInputStore, interaction_id: str, action: str
    ) -> None:
        body = self._read_body()
        actor_id = body.get("actor_id")
        if actor_id is not None and not isinstance(actor_id, str):
            self._write_error(
                400,
                _error("HUMAN_INPUT_IDENTIFIER_INVALID", "actor_id must be a string."),
            )
            return
        if action == "respond":
            if "response" not in body:
                self._write_error(
                    400,
                    _error("HUMAN_INPUT_RESPONSE_INVALID", "response is required."),
                )
                return
            result = store.respond(interaction_id, body["response"], actor_id=actor_id)
        elif action == "reject":
            result = store.reject(
                interaction_id,
                body.get("reason", "Operator rejected the request."),
                actor_id=actor_id,
            )
        elif action == "continue":
            continue_round = getattr(store, "continue_round", None)
            if not callable(continue_round):
                self._write_error(
                    501,
                    _error(
                        "HUMAN_INPUT_MULTI_ROUND_UNSUPPORTED",
                        "The configured human input store does not support multi-round input.",
                    ),
                )
                return
            if "prompt" not in body or "input_schema" not in body:
                self._write_error(
                    400,
                    _error(
                        "REQUEST_BODY_INVALID",
                        "prompt and input_schema are required.",
                    ),
                )
                return
            result = continue_round(
                interaction_id,
                body["prompt"],
                body["input_schema"],
                actor_id=actor_id,
            )
        elif action == "consume":
            result = store.consume(interaction_id)
        else:
            self._write_error(
                404, _error("NOT_FOUND", "Interaction action was not found.")
            )
            return
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        self._write_json(
            200, {"interaction": self._interaction_to_dict(result.unwrap())}
        )

    def _authorize(self) -> bool:
        expected_token = self.server.application.auth_token
        if expected_token is None:
            return True
        presented = self.headers.get("Authorization", "")
        expected = f"Bearer {expected_token}"
        if not hmac.compare_digest(presented, expected):
            self._write_json(
                401,
                {"error": _error("UNAUTHORIZED", "A valid bearer token is required.")},
                extra_headers={"WWW-Authenticate": "Bearer"},
            )
            return False
        return True

    def _path_segments(self) -> Optional[Tuple[str, ...]]:
        raw_path = self.path.encode("utf-8", errors="replace")
        if len(raw_path) > _MAX_PATH_BYTES:
            self._write_error(
                414, _error("PATH_TOO_LARGE", "Request path is too large.")
            )
            return None
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/"):
            self._write_error(400, _error("PATH_INVALID", "Request path is invalid."))
            return None
        parts = tuple(unquote(part) for part in parsed.path.split("/") if part)
        if any(part in {".", ".."} or not part for part in parts):
            self._write_error(400, _error("PATH_INVALID", "Request path is invalid."))
            return None
        return parts

    def _read_body(self) -> Dict[str, Any]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().split(";", 1)[0].strip() == "application/json":
            raise ValueError("request must use application/json")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("content length is required")
        length = int(raw_length)
        if length < 0 or length > self.server.application.max_body_bytes:
            self._write_error(
                413,
                _error(
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the configured byte limit.",
                    max_bytes=self.server.application.max_body_bytes,
                ),
            )
            raise _ResponseWritten()
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise ValueError("request body is truncated")
        decoded = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("request body must be an object")
        return decoded

    def _run(self, workflow_name: str) -> None:
        body = self._read_body()
        if "state" not in body or not isinstance(body["state"], Mapping):
            self._write_error(
                400, _error("INVALID_STATE", "Run state must be an object.")
            )
            return
        run_id = body.get("run_id")
        if run_id is not None and not isinstance(run_id, str):
            self._write_error(
                400, _error("INVALID_IDENTIFIER", "run_id must be a string.")
            )
            return
        result = self.server.application.registry.run(
            workflow_name, body["state"], run_id=run_id
        )
        self._write_result(result, success_status=201)

    def _resume(self, workflow_name: str, run_id: str) -> None:
        body = self._read_body()
        result = self.server.application.registry.resume(
            workflow_name, run_id, resume_value=body.get("value")
        )
        self._write_result(result, success_status=200)

    def _inspect(self, workflow_name: str, run_id: str) -> None:
        result = self.server.application.registry.inspect(workflow_name, run_id)
        if result.is_err():
            self._write_error(
                _status_for_error(result.unwrap_err()), result.unwrap_err()
            )
            return
        run = result.unwrap()
        if run is None:
            self._write_error(
                404, _error("RUN_NOT_FOUND", "Workflow run was not found.")
            )
            return
        self._write_json(200, {"run": _run_to_dict(run)})

    def _write_result(
        self, result: Result[WorkflowRun, Error], *, success_status: int
    ) -> None:
        if result.is_err():
            error = result.unwrap_err()
            self._write_error(_status_for_error(error), error)
            return
        self._write_json(success_status, {"run": _run_to_dict(result.unwrap())})

    def _write_error(self, status: int, error: Error) -> None:
        self._write_json(status, {"error": error})

    def _write_json(
        self,
        status: int,
        payload: Dict[str, Any],
        *,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        try:
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            status = 500
            encoded = (
                b'{"error":{"errorType":"INTERNAL_ERROR",'
                b'"message":"Response could not be encoded."}}'
            )
        if len(encoded) > self.server.application.max_response_bytes:
            status = 500
            encoded = (
                b'{"error":{"errorType":"RESPONSE_TOO_LARGE",'
                b'"message":"Response exceeds the configured byte limit."}}'
            )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Connection", "close")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.close_connection = True
        self.wfile.write(encoded)
        self.wfile.flush()


class _ResponseWritten(Exception):
    """Internal control flow after a bounded request error was written."""


class RunServer:
    """Loopback-only HTTP server for configured workflow runs."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        auth_token: Optional[str] = None,
        human_input_store: Optional[HumanInputStore] = None,
    ) -> None:
        if not isinstance(registry, WorkflowRegistry):
            raise TypeError("registry must be a WorkflowRegistry")
        if not isinstance(host, str) or not host:
            raise ValueError("host must be a non-empty string")
        if host not in {"localhost", "127.0.0.1"}:
            try:
                is_loopback = ipaddress.ip_address(host).is_loopback
            except ValueError as exc:
                raise ValueError("RunServer only binds to loopback hosts") from exc
            if not is_loopback or host != "127.0.0.1":
                raise ValueError("RunServer only binds to loopback hosts")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 0 <= port <= 65_535
        ):
            raise ValueError("port must be between 0 and 65535")
        limits = (max_body_bytes, max_response_bytes)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in limits
        ):
            raise ValueError("server limits must be positive integers")
        _validate_auth_token(auth_token)
        if human_input_store is not None:
            required_methods = ("get", "list_pending", "respond", "reject", "consume")
            if any(
                not callable(getattr(human_input_store, name, None))
                for name in required_methods
            ):
                raise TypeError(
                    "human_input_store must implement get, list_pending, respond, "
                    "reject, and consume"
                )
        self.registry = registry
        self.host = host
        self.port = port
        self.max_body_bytes = max_body_bytes
        self.max_response_bytes = max_response_bytes
        self._auth_token = auth_token
        self.human_input_store = human_input_store
        self._server: Optional[_MAPLEHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def auth_token(self) -> Optional[str]:
        """Return the configured bearer token without exposing a setter."""
        return self._auth_token

    @property
    def url(self) -> str:
        """Return the bound base URL after `start`; otherwise raise."""
        if self._server is None:
            raise RuntimeError("RunServer has not been started")
        address = self._server.server_address
        return f"http://{self.host}:{address[1]}"

    def start(self) -> str:
        """Start a daemon request thread and return the bound base URL."""
        if self._server is not None:
            raise RuntimeError("RunServer is already started")
        self._server = _MAPLEHTTPServer((self.host, self.port), _RequestHandler, self)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="maple-run-server",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def close(self) -> None:
        """Stop request handling and release the bound socket."""
        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        self._server = None
        self._thread = None

    def __enter__(self) -> "RunServer":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class RunClient:
    """Bounded dependency-free client for the MAPLE workflow HTTP contract.

    The client can target a loopback ``RunServer`` or a separately hosted
    implementation of the same contract. It performs no retries and never
    embeds credentials in URLs; callers own transport retry and idempotency
    policy for remote side effects.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: Optional[str] = None,
        timeout_seconds: float = _DEFAULT_CLIENT_TIMEOUT_SECONDS,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty URL")
        if any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in base_url
        ):
            raise ValueError("base_url must not contain control characters")
        parsed = urlsplit(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must use http or https and include a host")
        if not parsed.hostname:
            raise ValueError("base_url must include a host")
        hostname = parsed.hostname.lower()
        is_loopback = hostname == "localhost"
        if not is_loopback:
            try:
                is_loopback = ipaddress.ip_address(hostname).is_loopback
            except ValueError:
                is_loopback = False
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not include user information")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not include a query or fragment")
        _validate_auth_token(auth_token)
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive number")
        if (
            not isinstance(max_body_bytes, int)
            or isinstance(max_body_bytes, bool)
            or max_body_bytes <= 0
        ):
            raise ValueError("max_body_bytes must be a positive integer")
        if (
            not isinstance(max_response_bytes, int)
            or isinstance(max_response_bytes, bool)
            or max_response_bytes <= 0
        ):
            raise ValueError("max_response_bytes must be a positive integer")
        if auth_token is not None and parsed.scheme != "https" and not is_loopback:
            raise ValueError("authenticated non-loopback transport requires https")
        self.base_url = urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
        )
        self.auth_token = auth_token
        self.timeout_seconds = float(timeout_seconds)
        self.max_body_bytes = max_body_bytes
        self.max_response_bytes = max_response_bytes

    def healthz(self) -> Result[Dict[str, Any], Error]:
        """Check the remote workflow service health endpoint."""
        return self._request("GET", ("healthz",))

    def run(
        self,
        workflow_name: str,
        state: Mapping[str, Any],
        *,
        run_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Start a workflow run and return the remote response envelope."""
        if not isinstance(state, Mapping):
            return Result.err(_error("INVALID_STATE", "Run state must be an object."))
        if run_id is not None and not isinstance(run_id, str):
            return Result.err(_error("INVALID_IDENTIFIER", "run_id must be a string."))
        body: Dict[str, Any] = {"state": dict(state)}
        if run_id is not None:
            body["run_id"] = run_id
        return self._request("POST", ("v1", "workflows", workflow_name, "runs"), body)

    def resume(
        self,
        workflow_name: str,
        run_id: str,
        *,
        resume_value: Any = None,
    ) -> Result[Dict[str, Any], Error]:
        """Resume a paused workflow run."""
        return self._request(
            "POST",
            ("v1", "workflows", workflow_name, "runs", run_id, "resume"),
            {"value": resume_value},
        )

    def inspect(self, workflow_name: str, run_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect a persisted workflow run."""
        return self._request("GET", ("v1", "workflows", workflow_name, "runs", run_id))

    def list_pending_human_input(
        self, limit: int = 100
    ) -> Result[Dict[str, Any], Error]:
        """List bounded pending human-input requests from the remote host."""
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 0 < limit <= _MAX_HUMAN_INPUT_LIMIT
        ):
            return Result.err(
                _error(
                    "HUMAN_INPUT_LIMIT_INVALID",
                    "Human input list limit is out of bounds.",
                )
            )
        return self._request("GET", ("v1", "interactions", "pending", str(limit)))

    def get_human_input(self, interaction_id: str) -> Result[Dict[str, Any], Error]:
        """Inspect one remote human-input request."""
        return self._request("GET", ("v1", "interactions", interaction_id))

    def respond_human_input(
        self,
        interaction_id: str,
        response: Any,
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Submit a schema-validated remote human-input response."""
        payload: Dict[str, Any] = {"response": response}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "respond"), payload
        )

    def reject_human_input(
        self,
        interaction_id: str,
        reason: str = "Operator rejected the request.",
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Reject a remote human-input request with a bounded reason."""
        payload: Dict[str, Any] = {"reason": reason}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "reject"), payload
        )

    def continue_human_input(
        self,
        interaction_id: str,
        prompt: str,
        input_schema: Mapping[str, Any],
        *,
        actor_id: Optional[str] = None,
    ) -> Result[Dict[str, Any], Error]:
        """Open the next bounded round for a remote human-input request."""
        if not isinstance(input_schema, Mapping):
            return Result.err(
                _error(
                    "REQUEST_BODY_INVALID",
                    "input_schema must be an object.",
                )
            )
        if actor_id is not None and not isinstance(actor_id, str):
            return Result.err(
                _error(
                    "HUMAN_INPUT_IDENTIFIER_INVALID",
                    "actor_id must be a string.",
                )
            )
        payload: Dict[str, Any] = {"prompt": prompt, "input_schema": dict(input_schema)}
        if actor_id is not None:
            payload["actor_id"] = actor_id
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "continue"), payload
        )

    def consume_human_input(self, interaction_id: str) -> Result[Dict[str, Any], Error]:
        """Consume a decided remote human-input request exactly once."""
        return self._request(
            "POST", ("v1", "interactions", interaction_id, "consume"), {}
        )

    def _request(
        self,
        method: str,
        segments: Tuple[str, ...],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Result[Dict[str, Any], Error]:
        if any(
            not isinstance(segment, str) or not segment or segment in {".", ".."}
            for segment in segments
        ):
            return Result.err(
                _error("INVALID_IDENTIFIER", "Path segments are invalid.")
            )
        path = "/".join(quote(segment, safe="") for segment in segments)
        url = f"{self.base_url}/{path}"
        if len(url.encode("utf-8")) > _MAX_PATH_BYTES:
            return Result.err(_error("PATH_TOO_LARGE", "Request path is too large."))
        data: Optional[bytes] = None
        headers = {"Accept": "application/json"}
        if self.auth_token is not None:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if payload is not None:
            try:
                data = json.dumps(
                    payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
                ).encode("utf-8")
            except (TypeError, ValueError):
                return Result.err(
                    _error(
                        "REQUEST_BODY_INVALID",
                        "Request payload is not JSON-compatible.",
                    )
                )
            if len(data) > self.max_body_bytes:
                return Result.err(
                    _error(
                        "REQUEST_TOO_LARGE",
                        "Request body exceeds the configured byte limit.",
                        max_bytes=self.max_body_bytes,
                    )
                )
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return self._decode_response(response, int(response.status))
        except HTTPError as exc:
            decoded = self._decode_response(exc, int(exc.code))
            if decoded.is_ok():
                body = decoded.unwrap()
                error = body.get("error")
                if isinstance(error, dict):
                    return Result.err(error)
                return Result.err(
                    _error(
                        "REMOTE_HTTP_ERROR",
                        "Remote service returned an error.",
                        status=exc.code,
                    )
                )
            return Result.err(decoded.unwrap_err())
        except (URLError, TimeoutError, OSError):
            return Result.err(
                _error(
                    "TRANSPORT_ERROR",
                    "The remote workflow service could not be reached.",
                )
            )

    def _decode_response(
        self, response: Any, status: int
    ) -> Result[Dict[str, Any], Error]:
        raw_length = response.headers.get("Content-Length")
        if raw_length is not None:
            try:
                declared_length = int(raw_length)
            except (TypeError, ValueError):
                return Result.err(
                    _error(
                        "REMOTE_RESPONSE_INVALID", "Remote response length is invalid."
                    )
                )
            if declared_length < 0 or declared_length > self.max_response_bytes:
                return Result.err(
                    _error(
                        "RESPONSE_TOO_LARGE",
                        "Remote response exceeds the configured byte limit.",
                    )
                )
        try:
            raw = response.read(self.max_response_bytes + 1)
        except (OSError, TimeoutError):
            return Result.err(
                _error("TRANSPORT_ERROR", "The remote response could not be read.")
            )
        if len(raw) > self.max_response_bytes:
            return Result.err(
                _error(
                    "RESPONSE_TOO_LARGE",
                    "Remote response exceeds the configured byte limit.",
                )
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Result.err(
                _error("REMOTE_RESPONSE_INVALID", "Remote response is not valid JSON.")
            )
        if not isinstance(decoded, dict):
            return Result.err(
                _error("REMOTE_RESPONSE_INVALID", "Remote response must be an object.")
            )
        if status >= 400 and not isinstance(decoded.get("error"), dict):
            return Result.err(
                _error(
                    "REMOTE_HTTP_ERROR",
                    "Remote service returned an error.",
                    status=status,
                )
            )
        return Result.ok(decoded)


__all__ = ["RunClient", "RunServer", "WorkflowRegistry"]
