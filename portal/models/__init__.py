"""Portal data models — local JSON storage."""

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, data) -> None:
    """Write *data* to *path* as JSON so a crash cannot leave a truncated store.

    Every store in this package does read-modify-write: `_load()` reads the whole
    file, the caller mutates it, `_save()` writes the whole thing back. A plain
    `path.write_text()` truncates the file first and then writes -- so a power
    cut, an OOM kill, or a full disk mid-write leaves a half-written JSON file
    that `_load()` then fails to parse. The record set is gone, not corrupted in
    some recoverable way: `json.loads` raises and every read of that store dies.

    Writing to a temporary file in the *same directory* and then `os.replace()`
    -ing it into place makes the swap atomic on both POSIX and Windows: a reader
    sees either the complete old file or the complete new one, never a partial
    write. Same directory matters -- `os.replace` is only atomic within one
    filesystem.

    This does NOT make concurrent writes safe. Two processes doing
    read-modify-write against the same store still lose one update; the last
    `os.replace` wins. Locking is a separate, larger question and is deliberately
    not attempted here (M-A, DISPATCH_BUILD_MATRIX_v1).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        # Never leave the scratch file behind on any failure path, including
        # KeyboardInterrupt -- these live in the same directory the store is
        # read from.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def get_data_dir() -> Path:
    explicit = os.environ.get("PORTAL_DATA_DIR")
    if explicit:
        return Path(explicit)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Current Workspace" / "PortalData"
    return Path(__file__).resolve().parent.parent / "data"


def get_memory_dir() -> Path:
    explicit = os.environ.get("DISPATCH_MEMORY_ROOT")
    if explicit:
        return Path(explicit)
    return get_data_dir()


def get_archive_dir() -> Path:
    explicit = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if explicit:
        return Path(explicit)
    return get_data_dir()
