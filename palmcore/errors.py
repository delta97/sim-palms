"""Shared error hierarchy and process exit codes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Final

EXIT_OK: Final = 0
EXIT_UNEXPECTED: Final = 1
EXIT_CONFIG: Final = 2
EXIT_CONTRACT: Final = 3
EXIT_SOURCE: Final = 4
EXIT_CACHE_MISS: Final = 5
EXIT_EXTERNAL_TOOL: Final = 6
EXIT_INTERRUPTED: Final = 130


class PalmfixError(Exception):
    """Base class for expected palmfix failures."""

    exit_code: ClassVar[int] = EXIT_UNEXPECTED


class ConfigError(PalmfixError):
    """Bad region YAML, bad path or bad flag value."""

    exit_code: ClassVar[int] = EXIT_CONFIG


class ContractError(PalmfixError):
    """palms.geojson is invalid or has an unsupported version."""

    exit_code: ClassVar[int] = EXIT_CONTRACT

    def __init__(self, message: str, issues: Sequence[Any] = ()) -> None:
        super().__init__(message)
        self.issues: list[Any] = list(issues)


class SourceError(PalmfixError):
    """Fetching or parsing a data source failed."""

    exit_code: ClassVar[int] = EXIT_SOURCE


class CacheMiss(SourceError):
    """Offline mode was requested and no cached copy exists."""

    exit_code: ClassVar[int] = EXIT_CACHE_MISS


class ExternalToolError(PalmfixError):
    """An external tool (PDAL CLI, fspackagetool) failed."""

    exit_code: ClassVar[int] = EXIT_EXTERNAL_TOOL
