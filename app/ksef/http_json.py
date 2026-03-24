"""Proste wywołania HTTP JSON do API KSeF (urllib + ssl)."""
from __future__ import annotations

import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class KsefHttpError(Exception):
    def __init__(self, message: str, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def _ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def request_json(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    timeout: float = 120.0,
) -> tuple[int, Any]:
    data: bytes | None = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    req = Request(url, method=method, data=data, headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=_ctx()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        raise KsefHttpError(
            f"HTTP {e.code} {method} {url}\n{raw[:4000]}",
            status=e.code,
            body=raw,
        ) from e
    except URLError as e:
        raise KsefHttpError(f"Brak połączenia: {url}: {e.reason!s}") from e

    if not raw.strip():
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError as ex:
        raise KsefHttpError(f"Odpowiedź nie jest JSON ({status}): {raw[:500]}", status=status) from ex


def request_bytes(
    method: str,
    url: str,
    *,
    bearer_token: str | None = None,
    accept: str = "*/*",
    timeout: float = 120.0,
) -> tuple[int, bytes, str | None]:
    """Żądanie HTTP zwracające surowe bajty (np. GET application/xml)."""
    headers: dict[str, str] = {"Accept": accept}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    req = Request(url, method=method, headers=headers)
    try:
        with urlopen(req, timeout=timeout, context=_ctx()) as resp:
            raw = resp.read()
            status = resp.status
            ct = resp.headers.get("Content-Type")
            return status, raw, ct
    except HTTPError as e:
        body = e.read()
        txt = body.decode("utf-8", errors="replace")
        raise KsefHttpError(
            f"HTTP {e.code} {method} {url}\n{txt[:4000]}",
            status=e.code,
            body=txt,
        ) from e
    except URLError as e:
        raise KsefHttpError(f"Brak połączenia: {url}: {e.reason!s}") from e
