"""Basic logging wrapper for CIN-Hybrid."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str = "cin_hybrid", level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger, attaching a stream handler once per name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


_default = get_logger()


def log(message: str, level: int = logging.INFO) -> None:
    """Module-level convenience logger used across CIN-Hybrid."""
    _default.log(level, message)
