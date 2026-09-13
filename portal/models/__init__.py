"""Portal data models — local JSON storage."""

import json
import contextlib
import functools
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

    On its own this does NOT make concurrent writes safe: two processes doing
    read-modify-write against the same store still lose one update, because the
    last `os.replace` wins. `guarded()` below closes that, by holding a lock
    across the read *and* the write rather than only making the write atomic.
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


# ── concurrent read-modify-write ─────────────────────────────────────────
#
# `atomic_write_json` guarantees a reader never sees half a file. It cannot
# guarantee that two writers do not overwrite each other, because the damage is
# done before either write starts:
#
#     process A: data = _load()        # {"x": 1}
#     process B: data = _load()        # {"x": 1}
#     process A: data["a"] = 1; _save(data)
#     process B: data["b"] = 2; _save(data)   # A's change is gone
#
# Nothing is corrupt afterwards. A record simply is not there, and nothing
# anywhere says so -- which is the same shape as the PIN-lockout defect, minus
# the security consequence. Dispatch runs the portal and the launcher as two
# processes against one folder, so this is reachable rather than theoretical.
#
# The fix is a lock held across the whole read-modify-write. It has to work on
# Windows, because that is where Dispatch runs, and on POSIX, because that is
# where the suite runs.

try:  # pragma: no cover - platform branch, both sides exercised by tests
    import fcntl

    def _lock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    def _unlock_file(handle) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

except ImportError:  # pragma: no cover - Windows
    import msvcrt

    def _lock_file(handle) -> None:
        handle.seek(0)
        # One byte is enough: every writer locks the same byte of the same file,
        # so the range they contend on is identical. msvcrt blocks until it is
        # free, which is the behaviour we want -- a writer waits rather than
        # losing its update.
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(handle) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def lock_path_for(path: Path) -> Path:
    """The lock file beside a store.

    A separate `.lock` file rather than the store itself, for two reasons. The
    store is replaced by `os.replace()` on every write, so a lock held on its
    inode stops describing the file that is there. And a store that does not
    exist yet still needs a lock -- the first two writers race hardest.
    """
    return path.parent / f".{path.name}.lock"


@contextlib.contextmanager
def store_lock(path: Path):
    """Hold an exclusive cross-process lock on one JSON store.

    Blocking, deliberately: a writer that waits a millisecond is doing the right
    thing, and a writer that gives up loses the record this exists to protect.
    """
    lock_file = lock_path_for(path)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+b")
    try:
        _lock_file(handle)
        try:
            yield
        finally:
            _unlock_file(handle)
    finally:
        handle.close()


def guarded(path_getter):
    """Run a whole read-modify-write under the store's lock.

    Used as a decorator on the functions that mutate a store, so the body does
    not have to change:

        @guarded(_publisher_path)
        def enqueue(entry):
            data = _load()
            data.append(entry)
            _save(data)

    `path_getter` is the module's own path function, called at invocation time
    rather than import time, because every store resolves its path from
    `PORTAL_DATA_DIR` and the tests move it.

    Reentrant within a thread: an operation that calls another guarded
    operation on the same store does not deadlock against itself. Across
    processes it is a real exclusive lock.
    """
    def decorate(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            path = Path(path_getter())
            held = getattr(_HELD, "paths", None)
            if held is None:
                held = set()
                _HELD.paths = held
            key = str(path.resolve() if path.exists() else path)
            if key in held:
                return fn(*args, **kwargs)
            with store_lock(path):
                held.add(key)
                try:
                    return fn(*args, **kwargs)
                finally:
                    held.discard(key)
        return wrapper
    return decorate


import threading as _threading

#: Which store locks this thread already holds. See `guarded`.
_HELD = _threading.local()
