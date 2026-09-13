"""A momentary write collision waits, instead of becoming an error page.

`get_connection()` set `journal_mode=WAL` and `foreign_keys=ON` and stopped
there. SQLite's default `busy_timeout` is **0**: a second writer does not wait a
millisecond, it raises `database is locked` immediately.

That matters here because Dispatch is not a single process. The portal serves
the driver and the dispatcher, the launcher starts and stops it, `scripts/`
runs against the same file, and a scheduled backup reads it -- all against one
`dispatch.db`. WAL removes reader/writer contention; it does not serialise two
writers, and two writers is exactly what this program has.

The collisions being protected against last microseconds. Without a timeout,
one of them became an `OperationalError` on whatever the driver was doing at the
dock.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from dispatch import db
from dispatch.db import set_db_path


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    with db.get_connection():
        pass  # build the schema before any thread races for it
    try:
        yield tmp_path / "dispatch.db"
    finally:
        set_db_path(None)


class TestThePragmasEveryConnectionNeeds:
    def test_a_busy_timeout_is_set(self, database):
        with db.get_connection() as conn:
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS
        assert db.BUSY_TIMEOUT_MS > 0

    def test_it_is_set_on_every_connection_not_just_the_first(self, database):
        """SQLite resets it to 0 on each new handle. A pragma set once at
        startup protects nothing."""
        for _ in range(3):
            with db.get_connection() as conn:
                assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS

    def test_foreign_keys_are_still_on(self, database):
        """The pragma this one sits beside, unchanged."""
        with db.get_connection() as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_it_can_be_tuned_for_the_deployment(self, monkeypatch, tmp_path):
        """The right number on a network share is not the right number on a laptop."""
        monkeypatch.setenv("DISPATCH_SQLITE_BUSY_TIMEOUT_MS", "250")
        import importlib

        reloaded = importlib.reload(db)
        try:
            assert reloaded.BUSY_TIMEOUT_MS == 250
        finally:
            monkeypatch.delenv("DISPATCH_SQLITE_BUSY_TIMEOUT_MS")
            importlib.reload(db)


class TestAWriterWaitsInsteadOfFailing:
    def test_a_held_write_lock_is_waited_out(self, database):
        """With busy_timeout=0 this raises OperationalError immediately.

        A second connection takes an exclusive write lock and holds it for a
        quarter of a second -- shorter than the timeout, longer than the write
        being attempted. The write must succeed, not fail.
        """
        holder_ready = threading.Event()
        release = threading.Event()
        failures: list[BaseException] = []

        def holder():
            conn = sqlite3.connect(str(database), timeout=0)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO loads (load_id, created_at, updated_at)"
                " VALUES ('LOCK-HOLDER', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
            holder_ready.set()
            release.wait(timeout=5)
            conn.commit()
            conn.close()

        def writer():
            try:
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO loads (load_id, created_at, updated_at)"
                        " VALUES ('WAITER', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
                    )
            except BaseException as exc:  # noqa: BLE001 - reported, then asserted on
                failures.append(exc)

        lock_holder = threading.Thread(target=holder)
        lock_holder.start()
        assert holder_ready.wait(timeout=5)

        waiting_writer = threading.Thread(target=writer)
        waiting_writer.start()
        threading.Timer(0.25, release.set).start()
        waiting_writer.join(timeout=15)
        lock_holder.join(timeout=15)

        assert not failures, (
            f"a momentary write collision surfaced as {failures[0]!r} instead of waiting. "
            "Without busy_timeout the portal and the launcher cannot both write."
        )
        with db.get_connection() as conn:
            rows = {r[0] for r in conn.execute("SELECT load_id FROM loads").fetchall()}
        assert {"LOCK-HOLDER", "WAITER"} <= rows

    def test_a_lock_held_past_the_timeout_still_raises(self, database, monkeypatch):
        """The timeout is patience, not a guarantee. A genuinely stuck writer
        must still be reported rather than waited on forever."""
        monkeypatch.setattr(db, "BUSY_TIMEOUT_MS", 50)
        holder_ready = threading.Event()
        release = threading.Event()

        def holder():
            conn = sqlite3.connect(str(database), timeout=0)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO loads (load_id, created_at, updated_at)"
                " VALUES ('STUCK', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
            holder_ready.set()
            release.wait(timeout=5)
            conn.rollback()
            conn.close()

        lock_holder = threading.Thread(target=holder)
        lock_holder.start()
        assert holder_ready.wait(timeout=5)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO loads (load_id, created_at, updated_at)"
                        " VALUES ('X', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
                    )
        finally:
            release.set()
            lock_holder.join(timeout=15)


class _WatchingConnection:
    """A connection that records journal_mode *writes*.

    sqlite3.Connection is an immutable type, so its methods cannot be patched;
    wrapping it is the way to see what the code under test actually issues.
    """

    def __init__(self, wrapped, writes):
        self._wrapped = wrapped
        self._writes = writes

    def execute(self, sql, *args, **kwargs):
        if "journal_mode=" in sql.replace(" ", ""):
            self._writes.append(sql)
        return self._wrapped.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    def __setattr__(self, name, value):
        if name in ("_wrapped", "_writes"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._wrapped, name, value)


class _RefusingConnection:
    """Answers the journal_mode *read*, refuses every *write*."""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self.attempts = 0

    def execute(self, sql, *args, **kwargs):
        if "journal_mode=" in sql.replace(" ", ""):
            self.attempts += 1
            raise sqlite3.OperationalError("database is locked")
        return self._wrapped.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._wrapped, name)


class TestJournalModeIsAPropertyOfTheFile:
    """The statement no timeout can protect.

    `PRAGMA journal_mode` is the one setting here that does not honour
    `busy_timeout` -- SQLite returns SQLITE_BUSY immediately for a journal-mode
    change rather than invoking the busy handler. Setting it on every
    connection therefore put an unprotectable exclusive lock on the very first
    thing every connection did.

    CI found this: a pull_request run failed on a commit whose push run had
    just passed. Eight threads opening a fresh database reproduced it in 2 of
    40 attempts before the fix, and 0 of 150 after.
    """

    def test_a_fresh_database_ends_up_in_wal(self, tmp_path):
        set_db_path(tmp_path / "fresh.db")
        try:
            with db.get_connection() as conn:
                assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        finally:
            set_db_path(None)

    def test_a_later_connection_does_not_rewrite_the_header(self, tmp_path, monkeypatch):
        """The read is free; the write takes an exclusive lock. Only pay it once."""
        set_db_path(tmp_path / "already.db")
        try:
            with db.get_connection():
                pass  # first connection puts the file in WAL

            writes: list[str] = []
            real_connect = db.sqlite3.connect

            def watching_connect(*args, **kwargs):
                return _WatchingConnection(real_connect(*args, **kwargs), writes)

            monkeypatch.setattr(db.sqlite3, "connect", watching_connect)
            for _ in range(5):
                with db.get_connection() as conn:
                    conn.execute("SELECT 1").fetchone()

            assert writes == [], f"re-set journal_mode on an already-WAL database: {writes}"
        finally:
            set_db_path(None)

    def test_the_busy_timeout_is_set_before_anything_that_can_block(self, tmp_path):
        """Ordering, checked by behaviour: the timeout is live by the time the
        connection is handed over, so nothing after it runs unprotected."""
        set_db_path(tmp_path / "ordered.db")
        try:
            with db.get_connection() as conn:
                assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS
        finally:
            set_db_path(None)

    def test_concurrent_openers_do_not_collide_on_the_journal_mode(self, tmp_path):
        """Isolated to this PR's change: several connections to one brand-new
        database, all reaching _ensure_wal at once, none raising."""
        path = tmp_path / "contended.db"
        errors: list[BaseException] = []
        start = threading.Barrier(8)

        def worker():
            conn = sqlite3.connect(str(path))
            try:
                conn.execute(f"PRAGMA busy_timeout={db.BUSY_TIMEOUT_MS}")
                start.wait(timeout=5)
                db._ensure_wal(conn)
            except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                errors.append(exc)
            finally:
                conn.close()

        for trial in range(20):
            path = tmp_path / f"contended-{trial}.db"
            start = threading.Barrier(8)
            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            assert errors == [], f"trial {trial}: {errors}"

    def test_it_gives_up_rather_than_spinning_forever(self, tmp_path, monkeypatch):
        """The retry is bounded. A database that genuinely cannot be switched
        raises, rather than hanging a startup nobody can diagnose."""
        real = sqlite3.connect(str(tmp_path / "stuck.db"))
        refusing = _RefusingConnection(real)
        monkeypatch.setattr(db.time, "sleep", lambda _s: None)
        with pytest.raises(sqlite3.OperationalError):
            db._ensure_wal(refusing)
        assert refusing.attempts == db.WAL_ATTEMPTS, (
            f"retried {refusing.attempts} times against a bound of {db.WAL_ATTEMPTS}"
        )
        real.close()
