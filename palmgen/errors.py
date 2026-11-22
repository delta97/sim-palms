"""palmgen exceptions and their process exit codes."""

from __future__ import annotations

from typing import ClassVar

from palmcore.errors import PalmfixError


class PalmgenError(PalmfixError):
    """Base class for expected palmgen failures; ``exit_code`` is the process exit code."""

    exit_code: ClassVar[int] = 1


class InputError(PalmgenError):
    """Bad flag, missing or invalid input, schema failure, duplicate ``palm_id``."""

    exit_code: ClassVar[int] = 2


class GenerationError(PalmgenError):
    """Geometry or template failure, or an empty result without ``--allow-empty``."""

    exit_code: ClassVar[int] = 3


class CompileError(PalmgenError):
    """``fspackagetool`` exited non-zero or timed out."""

    exit_code: ClassVar[int] = 4


class OutputCheckError(PalmgenError):
    """Compiled, but an output check failed (missing BGL, count mismatch)."""

    exit_code: ClassVar[int] = 5


class SimRunningError(PalmgenError):
    """The sim is running and builds cannot run alongside it."""

    exit_code: ClassVar[int] = 6


class ToolUnavailableError(PalmgenError):
    """``fspackagetool`` not found, or not on Windows without ``--skip-compile``."""

    exit_code: ClassVar[int] = 7
