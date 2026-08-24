"""Where the launcher keeps its own files.

The launcher owns exactly four paths, and none of them holds freight data:

    dispatch-portal.pid          which process is the server, and how to prove it
    dispatch-portal.log          the portal's own stdout/stderr from the last start
    dispatch-launcher.log        what the launcher did, and when
    dispatch-last-failure.json   the plain-language reason the last start failed

All four live in one directory, resolved the same way the rest of Dispatch
resolves its storage: an explicit environment variable wins, then the D:\\ drive
operations root that `setup_dispatch_folders.ps1` already creates a `Logs` folder
inside, then a repository-local fallback so a checkout works with no environment
at all.

That last fallback is `<repo>/logs/`, which `.gitignore` already excludes -- the
mission requires launcher logs to stay outside version control, and the existing
`logs/` rule (added because a Werkzeug log can carry a debugger PIN) covers it
without this task editing `.gitignore`.
"""

from __future__ import annotations

import os
from pathlib import Path

PID_FILE_NAME = "dispatch-portal.pid"
SERVER_LOG_NAME = "dispatch-portal.log"
LAUNCHER_LOG_NAME = "dispatch-launcher.log"
FAILURE_FILE_NAME = "dispatch-last-failure.json"

#: Overrides the log directory outright. Exists so the test suite can point the
#: whole launcher at a tmp_path without going anywhere near a real install.
LOG_DIR_ENV = "DISPATCH_LAUNCHER_LOG_DIR"


def repo_root() -> Path:
    """The Dispatch checkout this launcher belongs to.

    The package sits at the repository root, next to `portal/` and `dispatch/`,
    so the parent of this file's directory is the root. Resolved rather than
    assumed, because the .bat wrapper may be double-clicked from anywhere and
    Windows will hand the process an unrelated working directory.
    """
    return Path(__file__).resolve().parent.parent


def logs_dir() -> Path:
    explicit = os.environ.get(LOG_DIR_ENV)
    if explicit:
        return Path(explicit)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Logs"
    return repo_root() / "logs"


def ensure_logs_dir() -> Path:
    """Create the log directory on demand and return it.

    Called only from the write paths. Status must never create anything, so it
    calls `logs_dir()` and tolerates a directory that does not exist yet.
    """
    path = logs_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def pid_file() -> Path:
    return logs_dir() / PID_FILE_NAME


def server_log() -> Path:
    return logs_dir() / SERVER_LOG_NAME


def launcher_log() -> Path:
    return logs_dir() / LAUNCHER_LOG_NAME


def failure_file() -> Path:
    return logs_dir() / FAILURE_FILE_NAME
