"""Small JSON client with a couple of retries for public market APIs."""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import requests

from ai_crypto_signals.config import USER_AGENT

Transport = Callable[..., tuple[int, Any]]


class HttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


def default_transport(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    timeout: float = 30,
) -> tuple[int, Any]:
    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=json_body,
        timeout=timeout,
    )
    text = response.text
    try:
        body: Any = response.json() if text else None
    except json.JSONDecodeError:
        body = {"_non_json": text[:4000]}
    return response.status_code, body


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    timeout: float = 30,
    retries: int = 2,
    transport: Transport | None = None,
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> tuple[int, Any]:
    """Return ``(status, body)``. Retries are for idempotent market reads.

    LLM calls should pass ``retries=0`` so a paid request is not repeated
    after a timeout that may have succeeded.
    """
    call = transport or default_transport
    merged = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if headers:
        merged.update(headers)
    last_status: int | None = None
    last_body: Any = None
    attempts = retries + 1
    for attempt in range(attempts):
        status, body = call(
            method,
            url,
            headers=merged,
            params=params,
            json_body=json_body,
            timeout=timeout,
        )
        last_status, last_body = status, body
        if status not in retry_statuses or attempt == attempts - 1:
            return status, body
        time.sleep(min(2**attempt, 8))
    return int(last_status or 0), last_body
