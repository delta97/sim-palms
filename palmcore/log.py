"""Logging setup shared by all palmfix tools."""

from __future__ import annotations

import logging
import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TextIO

LOGGER_ROOT: Final = "palmfix"

_STREAM_FORMAT: Final = "%(levelname).1s %(name)s: %(message)s"
_FILE_FORMAT: Final = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MARK: Final = "_palmfix"


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``palmfix`` root."""
    if name == LOGGER_ROOT or name.startswith(LOGGER_ROOT + "."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def _level_for(verbosity: int) -> int:
    if verbosity <= -1:
        return logging.WARNING
    if verbosity == 0:
        return logging.INFO
    return logging.DEBUG


def _remove_palmfix_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _MARK, False):
            logger.removeHandler(handler)
            handler.close()


def setup_logging(
    verbosity: int = 0,
    *,
    log_file: Path | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure logging for ``palmfix.*``. Safe to call repeatedly."""
    root = logging.getLogger()
    logger = logging.getLogger(LOGGER_ROOT)
    _remove_palmfix_handlers(root)
    _remove_palmfix_handlers(logger)

    stream_handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    stream_handler.setFormatter(logging.Formatter(_STREAM_FORMAT))
    stream_handler.setLevel(_level_for(verbosity))
    setattr(stream_handler, _MARK, True)
    logger.addHandler(stream_handler)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(_FILE_FORMAT)
        file_formatter.converter = time.gmtime
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)
        setattr(file_handler, _MARK, True)
        logger.addHandler(file_handler)

    # The logger itself must pass DEBUG so the file handler sees it.
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if verbosity >= 2:
        root.setLevel(logging.DEBUG)


def new_run_id(now: datetime | None = None) -> str:
    """Return ``YYYYMMDDTHHMMSSZ-xxxxxx`` (UTC time plus 6 random hex chars)."""
    moment = now if now is not None else datetime.now(UTC)
    moment = moment.astimezone(UTC)
    return f"{moment:%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
