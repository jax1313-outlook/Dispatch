"""The PID file: which process is the Dispatch server, and how to prove it.

A PID on its own is not an identity. PIDs are reused, sometimes within minutes on
a busy Windows box, and a PID file survives the crash that orphaned the process
it names. A launcher that trusts a bare number in a file will eventually send a
termination request to whatever now holds that number.

So the record written here carries three things that together make the claim
checkable:

    pid              the number, which is what the operating system needs
    command_line     what that process was running when we started it
    created_token    the operating system's own creation stamp for that process

`control.inspect_pidfile()` re-reads all three from the live process and refuses
to act on any mismatch. A recycled PID fails on both the command line and the
creation stamp; a process the launcher never started fails on the command line.

The file is JSON, human-readable on purpose: recovering from a wedged state is
something Mike may have to do at 5am from a text editor, and a binary or
positional format would make that harder for no gain.

Writes are atomic (temp file in the same directory, then `os.replace`), matching
`portal.models.atomic_write_json`. A half-written PID file is a launcher that
cannot stop its own server.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from dispatch_launcher import locations


@dataclass(frozen=True)
class PidRecord:
    """What the launcher recorded when it started the server."""

    pid: int
    recorded_at: str
    command: list[str]
    command_line: str | None = None
    created_token: str | None = None
    host: str = ""
    port: int | None = None
    log_path: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PidRecord | None":
        """Rebuild a record, or return None when the file is not one.

        A file that cannot be understood is treated exactly like a missing file
        by every caller: the launcher will not guess what a corrupt record meant.
        """
        try:
            pid = int(data["pid"])
        except (KeyError, TypeError, ValueError):
            return None
        known = {f for f in cls.__dataclass_fields__}
        payload = {k: v for k, v in data.items() if k in known}
        payload["pid"] = pid
        payload.setdefault("recorded_at", "")
        payload.setdefault("command", [])
        return cls(**payload)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_record(path: Path | None = None) -> PidRecord | None:
    path = path or locations.pid_file()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return PidRecord.from_dict(data)


def write_record(record: PidRecord, path: Path | None = None) -> Path:
    path = path or locations.pid_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record.to_dict(), handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def clear_record(path: Path | None = None) -> bool:
    """Remove the PID file. True when one was actually removed."""
    path = path or locations.pid_file()
    try:
        path.unlink()
        return True
    except OSError:
        return False
