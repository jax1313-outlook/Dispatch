"""Structured logging with a bounded file, for a program that only had print().

Across `dispatch/`, `portal/` and `cin_lite/` there were 80 `print()` calls and
zero uses of `logging`. The launcher redirects the portal's stdout and stderr
into `server.log`, opened in append mode, with no rotation and no size cap
anywhere -- `docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md` says so plainly:
"Nothing rotates them automatically."

That combination has one specific consequence, and it is the reason this module
exists rather than being a tidiness exercise. `services._notify_safe()` catches
every exception from every notification send -- twelve call sites -- and writes
one line to stderr. So a broker notification that fails authentication produces:
no database record, no screen indicator, no counter, no retry, and one line in an
unbounded text file on a laptop. Mike sees Submit succeed, because the load *was*
invoiced. Only the email died.

`dispatch/delivery.py` fixes the record. This module fixes the trail:

**One event per line, parseable.** `key=value` pairs after a fixed prefix, so
`findstr` on a Windows console and a script both work on it. Not JSON: the
primary reader is a person with a text editor on a laptop, and a wall of
`{"levelname":` is worse for them than it is better for the script that could
parse either.

**A bounded file.** RotatingFileHandler, 5 MB x 5, so the log cannot fill the
disk the database is on. A log that consumed the last of the disk would take
Dispatch down to record that something went wrong.

**stderr as well, always.** The launcher's capture keeps working exactly as it
did, so nothing that used to reach `server.log` stops reaching it.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

LOGGER_ROOT = "dispatch"

#: 5 MB x 5 files. Enough to hold weeks of a single operator's activity and
#: small enough that it can never be the reason a disk fills.
MAX_BYTES = int(os.environ.get("DISPATCH_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
BACKUP_COUNT = int(os.environ.get("DISPATCH_LOG_BACKUP_COUNT", "5"))

_configured = False


class KeyValueFormatter(logging.Formatter):
    """`2026-09-12T19:40:11Z WARNING dispatch.delivery send failed kind=... id=...`

    Structured fields are passed as `extra={"fields": {...}}` and appended in a
    stable order. A value containing a space is quoted; nothing else is escaped,
    because the alternative is a format nobody can read at the moment they need
    to read it.
    """

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = None

    def formatTime(self, record, datefmt=None):  # noqa: N802 - stdlib signature
        import time

        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created))

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record)} {record.levelname} {record.name} {record.getMessage()}"
        fields = getattr(record, "fields", None)
        if fields:
            parts = []
            for key in sorted(fields):
                value = str(fields[key])
                parts.append(f'{key}="{value}"' if " " in value else f"{key}={value}")
            base = f"{base} {' '.join(parts)}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def log_dir() -> Path:
    """Where the log goes. The launcher's own directory when there is one."""
    explicit = os.environ.get("DISPATCH_LOG_DIR")
    if explicit:
        return Path(explicit)
    try:
        from dispatch_launcher import locations

        return Path(locations.logs_dir())
    except Exception:  # noqa: BLE001 - the launcher is optional by doctrine
        return Path.cwd() / "logs"


def configure(*, force: bool = False) -> logging.Logger:
    """Attach the handlers once. Safe to call from anywhere, any number of times."""
    global _configured
    logger = logging.getLogger(LOGGER_ROOT)
    if _configured and not force:
        return logger

    logger.setLevel(os.environ.get("DISPATCH_LOG_LEVEL", "INFO").upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = KeyValueFormatter()

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    try:
        directory = log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            directory / "dispatch.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        rotating.setFormatter(formatter)
        logger.addHandler(rotating)
    except OSError:
        # A read-only or missing log directory must never stop Dispatch. stderr
        # still carries everything, and the launcher captures stderr.
        logger.warning(
            "log file unavailable; stderr only",
            extra={"fields": {"log_dir": str(log_dir())}},
        )

    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """`get_logger(__name__)`. Configures the root handlers on first use."""
    configure()
    if name.startswith(LOGGER_ROOT):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_ROOT}.{name}")


def event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    """Log one structured event. `event(log, logging.WARNING, "send failed", kind=...)`"""
    logger.log(level, message, extra={"fields": fields})
