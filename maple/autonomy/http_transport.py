# Copyright (C) 2025 Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)
#
# This file is part of MAPLE - Multi Agent Protocol Language Engine.
#
# MAPLE - Multi Agent Protocol Language Engine is free software: you can
# redistribute it and/or modify it under the terms of the GNU Affero General
# Public License as published by the Free Software Foundation, either version
# 3 of the License, or (at your option) any later version.
#
# MAPLE - Multi Agent Protocol Language Engine is distributed in the hope that
# it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero
# General Public License for more details. You should have received a copy of
# the GNU Affero General Public License along with MAPLE - Multi Agent Protocol
# Language Engine. If not, see <https://www.gnu.org/licenses/>.

"""Restricted stdlib HTTP opening for host-owned MAPLE transports."""

from __future__ import annotations

from typing import Any, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPDefaultErrorHandler,
    HTTPErrorProcessor,
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    OpenerDirector,
    ProxyHandler,
    Request,
)


def _endpoint_parts(url: str) -> Tuple[str, str, Optional[int]]:
    """Return the validated scheme, hostname, and port for one URL."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except (AttributeError, TypeError, ValueError) as exc:
        raise URLError("HTTP endpoint is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise URLError("HTTP endpoint must use an absolute HTTP(S) URL")
    return parsed.scheme.lower(), hostname.lower(), port


class _SameOriginRedirectHandler(HTTPRedirectHandler):
    """Allow only bounded HTTP(S) redirects on the original origin."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Optional[Request]:
        source_scheme, source_host, source_port = _endpoint_parts(req.full_url)
        target_scheme, target_host, target_port = _endpoint_parts(newurl)
        if target_host != source_host or target_port != source_port:
            raise URLError("HTTP redirects must remain on the original origin")
        if source_scheme == "https" and target_scheme != "https":
            raise URLError("HTTPS HTTP transports must not downgrade redirects")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener() -> OpenerDirector:
    """Build an opener with HTTP(S) handlers and no file/custom schemes."""
    opener = OpenerDirector()
    for handler in (
        ProxyHandler(),
        HTTPDefaultErrorHandler(),
        _SameOriginRedirectHandler(),
        HTTPHandler(),
        HTTPSHandler(),
        HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


_HTTP_OPENER = _build_opener()


def open_http_request(request: Request, *, timeout: float) -> Any:
    """Open a validated HTTP(S) request without file/custom URL handlers."""
    if not isinstance(request, Request):
        raise TypeError("request must be an urllib.request.Request")
    _endpoint_parts(request.full_url)
    return _HTTP_OPENER.open(request, timeout=timeout)


__all__ = ["open_http_request"]
