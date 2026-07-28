"""Centralized loguru configuration with rotating file handler.

Call ``configure()`` once at application startup (e.g. in ``run.main()``)
to set up console and file sinks. Tests skip this — they route loguru
through stdlib so pytest's ``caplog`` fixture keeps working.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_configured = False


def configure(
    *,
    log_dir: str | Path = "logs",
    rotation: str = "10 MB",
    retention: str = "30 days",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
) -> None:
    """Set up console + rotating-file sinks.

    Safe to call more than once — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stderr,
        level=console_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
    )

    logger.add(
        log_path / "cin_lite.log",
        level=file_level,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
            "{name}:{function}:{line} | {message}"
        ),
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    _configured = True
