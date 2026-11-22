"""HTTP client with retries, backoff and a generic User-Agent."""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Final

import requests

from palmcore.errors import SourceError
from palmcore.log import get_logger
from palmscan import __version__

__all__ = ["HttpClient", "HttpError"]

_log = get_logger(__name__)

RETRY_STATUS: Final = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_S: Final = 120.0
_CHUNK: Final = 1 << 20


class HttpError(SourceError):
    """A request failed for good; ``status`` is None for connection errors."""

    def __init__(self, message: str, *, url: str, status: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status = status


def _retry_after(response: Any) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:  # an HTTP date: fall back to the backoff schedule
        return None
    return min(max(seconds, 0.0), MAX_RETRY_AFTER_S)


class HttpClient:
    """Small ``requests`` wrapper.

    A User-Agent is always sent (Overpass answers 406 without one). It is generic,
    ``palmscan/<version>``; never put a name or email in it. ``retries`` is the number of
    extra attempts; the wait before retry ``n`` (from 0) is ``backoff_s * 2**n`` unless the
    server sends ``Retry-After``. ``sleep`` is injectable so tests do not wait.
    """

    def __init__(
        self,
        user_agent: str = f"palmscan/{__version__}",
        timeout_s: float = 60,
        retries: int = 3,
        backoff_s: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_s = backoff_s
        self._sleep = sleep
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent

    def _request(self, method: str, url: str, *, stream: bool = False, **kwargs: Any) -> Any:
        """Send with retries; return a response with status < 400 (the caller closes it)."""
        attempt = 0
        while True:
            wait: float | None = None
            try:
                response = self._session.request(
                    method, url, timeout=self.timeout_s, stream=stream, **kwargs
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt >= self.retries:
                    raise HttpError(f"{method} {url} failed: {exc}", url=url) from exc
                reason = type(exc).__name__
            else:
                status = int(response.status_code)
                if status < 400:
                    return response
                retry = status in RETRY_STATUS and attempt < self.retries
                if retry:
                    wait = _retry_after(response)
                response.close()
                if not retry:
                    raise HttpError(
                        f"{method} {url} returned HTTP {status}", url=url, status=status
                    )
                reason = f"HTTP {status}"
            if wait is None:
                wait = self.backoff_s * 2**attempt
            _log.warning(
                "%s %s: %s, retry %d/%d in %.1fs",
                method,
                url,
                reason,
                attempt + 1,
                self.retries,
                wait,
            )
            self._sleep(wait)
            attempt += 1

    def get_json(self, url: str, params: Mapping[str, Any] | None = None) -> Any:
        response = self._request("GET", url, params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise HttpError(f"GET {url} did not return JSON", url=url) from exc
        finally:
            response.close()

    def post_text(self, url: str, data: Mapping[str, Any]) -> str:
        response = self._request("POST", url, data=data)
        try:
            return str(response.text)
        finally:
            response.close()

    def download(self, url: str, dest: Path) -> None:
        """Stream ``url`` into ``dest`` in chunks (via a temp file, replaced on success)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + f".dl-{os.getpid()}")
        response = self._request("GET", url, stream=True)
        try:
            with open(tmp, "wb") as handle:
                for chunk in response.iter_content(chunk_size=_CHUNK):
                    handle.write(chunk)
            os.replace(tmp, dest)
        except requests.RequestException as exc:
            raise HttpError(f"GET {url} failed while streaming: {exc}", url=url) from exc
        finally:
            response.close()
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
