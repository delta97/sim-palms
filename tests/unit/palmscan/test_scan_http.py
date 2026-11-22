"""palmscan.http: retry logic with a faked ``requests.Session.request``. No sockets."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import requests

from palmscan import __version__
from palmscan.http import HttpClient, HttpError


class FakeResponse:
    def __init__(
        self,
        status: int = 200,
        body: bytes = b"{}",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status
        self.content = body
        self.headers = headers or {}
        self.closed = False

    def json(self) -> Any:
        return json.loads(self.content)

    @property
    def text(self) -> str:
        return self.content.decode()

    def iter_content(self, chunk_size: int = 1) -> Iterator[bytes]:
        for i in range(0, len(self.content), 4):
            yield self.content[i : i + 4]

    def close(self) -> None:
        self.closed = True


Step = FakeResponse | Exception


class Script:
    """Replacement for ``requests.Session.request``: plays back a list of outcomes."""

    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def request(self, session: requests.Session, method: str, url: str, **kw: Any) -> Any:
        self.calls.append({"method": method, "url": url, "headers": dict(session.headers), **kw})
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture
def play(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[Step]], Script]:
    def install(steps: list[Step]) -> Script:
        script = Script(steps)

        def fake(session: requests.Session, method: str, url: str, **kw: Any) -> Any:
            return script.request(session, method, url, **kw)

        monkeypatch.setattr(requests.Session, "request", fake)
        return script

    return install


def _client(sleeps: list[float], **kw: Any) -> HttpClient:
    return HttpClient(sleep=sleeps.append, **kw)


def test_get_json_sends_generic_user_agent_and_timeout(play: Callable[..., Script]) -> None:
    script = play([FakeResponse(200, b'{"a": 1}')])
    out = _client([]).get_json("https://x.test/q", {"f": "json"})
    assert out == {"a": 1}
    call = script.calls[0]
    assert call["headers"]["User-Agent"] == f"palmscan/{__version__}"
    assert call["timeout"] == 60
    assert call["params"] == {"f": "json"}
    assert call["method"] == "GET"


def test_user_agent_has_no_personal_details() -> None:
    ua = HttpClient().user_agent
    assert ua.startswith("palmscan/")
    assert "@" not in ua


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retries_then_succeeds_with_exponential_backoff(
    play: Callable[..., Script], status: int
) -> None:
    script = play([FakeResponse(status), FakeResponse(status), FakeResponse(200, b"[1]")])
    sleeps: list[float] = []
    assert _client(sleeps, backoff_s=2.0).get_json("https://x.test") == [1]
    assert sleeps == [2.0, 4.0]
    assert len(script.calls) == 3


def test_retry_after_header_is_honoured_and_capped(play: Callable[..., Script]) -> None:
    play(
        [
            FakeResponse(429, headers={"Retry-After": "7"}),
            FakeResponse(503, headers={"Retry-After": "99999"}),
            FakeResponse(503, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
            FakeResponse(200),
        ]
    )
    sleeps: list[float] = []
    _client(sleeps, backoff_s=1.0).get_json("https://x.test")
    assert sleeps == [7.0, 120.0, 4.0]


def test_gives_up_after_retries(play: Callable[..., Script]) -> None:
    script = play([FakeResponse(503)] * 4)
    sleeps: list[float] = []
    with pytest.raises(HttpError) as info:
        _client(sleeps, retries=3).get_json("https://x.test")
    assert info.value.status == 503
    assert info.value.url == "https://x.test"
    assert len(script.calls) == 4
    assert len(sleeps) == 3


def test_other_4xx_fails_at_once(play: Callable[..., Script]) -> None:
    script = play([FakeResponse(404)])
    sleeps: list[float] = []
    with pytest.raises(HttpError) as info:
        _client(sleeps).get_json("https://x.test")
    assert info.value.status == 404
    assert len(script.calls) == 1
    assert sleeps == []


def test_connection_errors_and_timeouts_are_retried(play: Callable[..., Script]) -> None:
    play([requests.ConnectionError("reset"), requests.Timeout("slow"), FakeResponse(200, b"{}")])
    sleeps: list[float] = []
    assert _client(sleeps).get_json("https://x.test") == {}
    assert sleeps == [2.0, 4.0]


def test_connection_error_exhausted_raises_http_error(play: Callable[..., Script]) -> None:
    play([requests.ConnectionError("down")] * 2)
    with pytest.raises(HttpError) as info:
        _client([], retries=1).get_json("https://x.test")
    assert info.value.status is None


def test_non_json_body_is_http_error(play: Callable[..., Script]) -> None:
    play([FakeResponse(200, b"<html>")])
    with pytest.raises(HttpError, match="JSON"):
        _client([]).get_json("https://x.test")


def test_post_text(play: Callable[..., Script]) -> None:
    script = play([FakeResponse(200, b"ok text")])
    assert _client([]).post_text("https://x.test", {"data": "q"}) == "ok text"
    assert script.calls[0]["method"] == "POST"
    assert script.calls[0]["data"] == {"data": "q"}


def test_download_streams_to_file(play: Callable[..., Script], tmp_path: Path) -> None:
    script = play([FakeResponse(200, b"0123456789abcdef")])
    dest = tmp_path / "sub" / "f.bin"
    _client([]).download("https://x.test/f", dest)
    assert dest.read_bytes() == b"0123456789abcdef"
    assert script.calls[0]["stream"] is True
    assert [p.name for p in dest.parent.iterdir()] == ["f.bin"]


def test_download_failure_leaves_no_file(play: Callable[..., Script], tmp_path: Path) -> None:
    play([FakeResponse(500)] * 2)
    dest = tmp_path / "f.bin"
    with pytest.raises(HttpError):
        _client([], retries=1).download("https://x.test/f", dest)
    assert not dest.exists()
    assert list(tmp_path.iterdir()) == []
