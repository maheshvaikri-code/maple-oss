"""Dependency-free loopback HTTP access to registered MAPLE workflows."""

from __future__ import annotations

import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.parse import unquote, urlsplit

from ..core.result import Result
from .workflow import Workflow, WorkflowRun

Error = Dict[str, Any]
_MAX_PATH_BYTES = 4_096
_MAX_WORKFLOWS = 64
_DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024
_DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _error(error_type: str, message: str, **details: Any) -> Error:
    result: Error = {"errorType": error_type, "message": message}
    if details:
        result["details"] = details
    return result


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
    if error_type in {"RUN_ID_EXISTS", "CHECKPOINT_CONFLICT"}:
        return 409
    if error_type in {
        "INVALID_STATE",
        "INVALID_IDENTIFIER",
        "INVALID_WORKFLOW",
        "INVALID_JSON",
        "REQUEST_BODY_INVALID",
        "WORKFLOW_MISMATCH",
    }:
        return 400
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
            path = self._path_segments()
            if path is None:
                return
            if method == "GET" and path == ("healthz",):
                self._write_json(200, {"status": "ok", "service": "maple-run-server"})
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

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
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
        self.registry = registry
        self.host = host
        self.port = port
        self.max_body_bytes = max_body_bytes
        self.max_response_bytes = max_response_bytes
        self._server: Optional[_MAPLEHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

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


__all__ = ["RunServer", "WorkflowRegistry"]
