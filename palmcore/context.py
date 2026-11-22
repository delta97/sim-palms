"""Per-run context shared by the palmfix, palmscan and palmgen command lines."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from palmcore.config import RegionConfig
from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmcore.paths import Paths


@dataclass(frozen=True)
class RunContext:
    """Everything a command needs: tool name, resolved paths, run id and optional region."""

    tool: str
    paths: Paths
    run_id: str
    started_at: datetime
    log_file: Path | None
    region: RegionConfig | None = None

    @property
    def log(self) -> logging.Logger:
        return get_logger(self.tool)

    def require_region(self) -> RegionConfig:
        if self.region is None:
            raise ConfigError("this command needs a region: pass --region NAME or PATH")
        return self.region
