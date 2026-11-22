from __future__ import annotations

import io
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from palmcore.log import LOGGER_ROOT, get_logger, new_run_id, setup_logging


def _palmfix_handlers() -> list[logging.Handler]:
    found: list[logging.Handler] = []
    for lg in (logging.getLogger(), logging.getLogger(LOGGER_ROOT)):
        found += [h for h in lg.handlers if getattr(h, "_palmfix", False)]
    return found


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    for lg in (logging.getLogger(), logging.getLogger(LOGGER_ROOT)):
        for h in list(lg.handlers):
            if getattr(h, "_palmfix", False):
                lg.removeHandler(h)
                h.close()
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger(LOGGER_ROOT).setLevel(logging.NOTSET)


def test_get_logger_prefixes() -> None:
    assert get_logger("palmscan.x").name == "palmfix.palmscan.x"
    assert get_logger("palmfix.palmgen").name == "palmfix.palmgen"
    assert get_logger("palmfix").name == "palmfix"


@pytest.mark.parametrize(
    ("verbosity", "level"),
    [(-1, logging.WARNING), (0, logging.INFO), (1, logging.DEBUG), (2, logging.DEBUG)],
)
def test_verbosity_levels(verbosity: int, level: int) -> None:
    setup_logging(verbosity, stream=io.StringIO())
    (handler,) = _palmfix_handlers()
    assert handler.level == level
    assert logging.getLogger(LOGGER_ROOT).getEffectiveLevel() <= level
    assert (logging.getLogger().level == logging.DEBUG) == (verbosity >= 2)


def test_repeat_setup_keeps_one_stream_handler() -> None:
    setup_logging(0, stream=io.StringIO())
    setup_logging(1, stream=io.StringIO())
    assert len(_palmfix_handlers()) == 1


def test_file_gets_debug_stream_gets_info(tmp_path: Path) -> None:
    stream = io.StringIO()
    log_file = tmp_path / "logs" / "run.log"
    setup_logging(0, log_file=log_file, stream=stream)
    log = get_logger("palmscan.test")
    log.debug("dbg-line")
    log.info("info-line")
    for h in _palmfix_handlers():
        h.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "DEBUG palmfix.palmscan.test: dbg-line" in text
    assert "INFO palmfix.palmscan.test: info-line" in text
    assert "dbg-line" not in stream.getvalue()
    assert "I palmfix.palmscan.test: info-line" in stream.getvalue()


def test_new_run_id_format() -> None:
    run_id = new_run_id(datetime(2026, 11, 21, 18, 4, tzinfo=UTC))
    assert run_id.startswith("20261121T180400Z-")
    assert re.fullmatch(r"[0-9a-f]{6}", run_id.split("-", 1)[1])
