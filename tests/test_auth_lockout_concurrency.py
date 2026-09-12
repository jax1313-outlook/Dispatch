"""Concurrent PIN guesses count, and the lockout holds.

The defect: `failed_attempt_count` lived in a JSON store, and every store in
`portal/models` does read-modify-write on the whole file. Its own helper says so
-- "Two processes doing read-modify-write against the same store still lose one
update; the last os.replace wins". That was accepted for durability. It was never
re-examined when a lockout counter moved into one of those files, and a lost
update on a lockout counter is not cosmetic:

    five concurrent attempts, each reading count=0, each writing count=1
    -> the counter reads 1, not 5, and MAX_FAILED_ATTEMPTS is never reached.

An attacker controls the one variable that defeats it: how many requests to send
at once. Nothing in the registry, the audit log or any screen would show it.

`test_concurrent_failures_are_all_counted` fails on the old implementation and
passes on the current one, which is the only reason to write it.

SQLite contention is tested in the same module because it is the same story from
the other side: the database had no busy_timeout, so the default of 0 turned a
momentary collision between the portal and the launcher into an immediate
"database is locked" rather than a wait of a few milliseconds.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from dispatch import authcounters, db
from dispatch.db import set_db_path

KIND = authcounters.KIND_DRIVER


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    with db.get_connection():
        pass  # build the schema before any thread races for it
    try:
        yield tmp_path / "dispatch.db"
    finally:
        set_db_path(None)


def _run_concurrently(fn, count: int):
    """Start every worker at the same instant, so they genuinely overlap."""
    start = threading.Barrier(count)
    errors: list[BaseException] = []

    def worker(index: int):
        try:
            start.wait(timeout=10)
            fn(index)
        except BaseException as exc:  # noqa: BLE001 - reported, then re-raised in the test
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return errors


class TestTheLockoutCannotBeOutrun:
    def test_concurrent_failures_are_all_counted(self, database):
        attempts = 12

        def attempt(_i):
            authcounters.record_failure(
                KIND, "DRV-1", max_attempts=5, lockout_minutes=15
            )

        errors = _run_concurrently(attempt, attempts)
        assert not errors, f"a concurrent attempt raised: {errors[0]!r}"

        state = authcounters.get_state(KIND, "DRV-1")
        assert state["failed_attempt_count"] == attempts, (
            f"{attempts} concurrent failed attempts were recorded as "
            f"{state['failed_attempt_count']}. Lost updates on this counter mean "
            "the lockout is defeated by sending the guesses at the same time."
        )

    def test_the_lockout_engages_under_concurrency(self, database):
        def attempt(_i):
            authcounters.record_failure(KIND, "DRV-2", max_attempts=5, lockout_minutes=15)

        assert not _run_concurrently(attempt, 8)
        assert authcounters.is_locked(KIND, "DRV-2") is True

    def test_a_locked_subject_stays_locked_until_the_window_passes(self, database):
        now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        for _ in range(5):
            authcounters.record_failure(
                KIND, "DRV-3", max_attempts=5, lockout_minutes=15, now=now
            )
        assert authcounters.is_locked(KIND, "DRV-3", now=now + timedelta(minutes=14)) is True
        assert authcounters.is_locked(KIND, "DRV-3", now=now + timedelta(minutes=16)) is False

    def test_further_failures_during_a_lockout_do_not_shorten_it(self, database):
        now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        for _ in range(5):
            authcounters.record_failure(KIND, "DRV-4", max_attempts=5, lockout_minutes=15, now=now)
        first = authcounters.get_state(KIND, "DRV-4")["locked_until"]
        authcounters.record_failure(
            KIND, "DRV-4", max_attempts=5, lockout_minutes=15, now=now + timedelta(minutes=1)
        )
        assert authcounters.get_state(KIND, "DRV-4")["locked_until"] == first

    def test_success_clears_the_count_and_the_lockout(self, database):
        for _ in range(5):
            authcounters.record_failure(KIND, "DRV-5", max_attempts=5, lockout_minutes=15)
        authcounters.record_success(KIND, "DRV-5")
        state = authcounters.get_state(KIND, "DRV-5")
        assert state["failed_attempt_count"] == 0
        assert state["locked_until"] is None

    def test_two_subjects_do_not_share_a_lockout(self, database):
        for _ in range(6):
            authcounters.record_failure(KIND, "DRV-6", max_attempts=5, lockout_minutes=15)
        assert authcounters.is_locked(KIND, "DRV-6") is True
        assert authcounters.is_locked(KIND, "DRV-7") is False

    def test_a_driver_and_an_authority_with_the_same_id_are_separate(self, database):
        for _ in range(6):
            authcounters.record_failure(
                authcounters.KIND_DRIVER, "SAME", max_attempts=5, lockout_minutes=15
            )
        assert authcounters.is_locked(authcounters.KIND_DRIVER, "SAME") is True
        assert authcounters.is_locked(authcounters.KIND_AUTHORITY, "SAME") is False


class TestThroughTheDriverRegistry:
    """The same proof one layer up, through the function the login route calls."""

    @pytest.fixture
    def carded_driver(self, database, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
        from dispatch import services
        from portal.models import driver_pin_registry

        driver = services.create_driver(name="Ray", phone="555-0100")
        driver_pin_registry.create_pin_card(
            driver["driver_id"], pin="4821", recovery_word="redwood", created_by="Mike"
        )
        return driver, driver_pin_registry

    def test_concurrent_wrong_pins_lock_the_card(self, carded_driver):
        driver, registry = carded_driver

        def attempt(_i):
            assert registry.verify_login("555-0100", "0000") is None

        errors = _run_concurrently(attempt, 10)
        assert not errors, f"a concurrent login raised: {errors[0]!r}"

        card = registry.get_pin_card(driver["driver_id"])
        assert card["failed_attempt_count"] >= 5
        assert card["locked_until"] is not None
        assert registry.verify_login("555-0100", "4821") is None, (
            "the correct PIN was accepted while the card should be locked"
        )

    def test_the_right_pin_still_works_and_clears_the_count(self, carded_driver):
        driver, registry = carded_driver
        registry.verify_login("555-0100", "0000")
        registry.verify_login("555-0100", "0000")
        assert registry.get_pin_card(driver["driver_id"])["failed_attempt_count"] == 2

        assert registry.verify_login("555-0100", "4821") is not None
        assert registry.get_pin_card(driver["driver_id"])["failed_attempt_count"] == 0

    def test_an_authority_reset_clears_a_lockout(self, carded_driver):
        driver, registry = carded_driver
        for _ in range(6):
            registry.verify_login("555-0100", "0000")
        assert registry.get_pin_card(driver["driver_id"])["locked_until"] is not None

        registry.reset_pin(driver["driver_id"], "9999", reset_by="Mike")
        card = registry.get_pin_card(driver["driver_id"])
        assert card["locked_until"] is None
        assert card["failed_attempt_count"] == 0
        assert registry.verify_login("555-0100", "9999") is not None


class TestSQLiteContention:
    def test_a_busy_timeout_is_set_on_every_connection(self, database):
        with db.get_connection() as conn:
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == db.BUSY_TIMEOUT_MS

    def test_foreign_keys_are_on_for_every_connection(self, database):
        """SQLite resets this per handle; a missed pragma silently drops referential integrity."""
        for _ in range(3):
            with db.get_connection() as conn:
                assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_the_file_is_in_wal(self, database):
        with db.get_connection() as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"

    def test_a_writer_waits_for_another_writer_instead_of_erroring(self, database, monkeypatch):
        """With busy_timeout=0 this raises OperationalError immediately."""
        holder_ready = threading.Event()
        release = threading.Event()
        failures: list[BaseException] = []

        def holder():
            conn = sqlite3.connect(str(database), timeout=0)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO auth_attempt_state (subject_kind, subject_id,"
                " failed_attempt_count, updated_at) VALUES ('driver','HOLD',0,'now')"
            )
            holder_ready.set()
            release.wait(timeout=5)
            conn.commit()
            conn.close()

        t = threading.Thread(target=holder)
        t.start()
        assert holder_ready.wait(timeout=5)

        def writer():
            try:
                authcounters.record_failure(
                    KIND, "WAITER", max_attempts=5, lockout_minutes=15
                )
            except BaseException as exc:  # noqa: BLE001
                failures.append(exc)

        w = threading.Thread(target=writer)
        w.start()
        threading.Timer(0.25, release.set).start()
        w.join(timeout=15)
        t.join(timeout=15)

        assert not failures, (
            f"a momentary write collision surfaced as {failures[0]!r} instead of waiting. "
            "Without busy_timeout the portal and the launcher cannot both write."
        )
        assert authcounters.get_state(KIND, "WAITER")["failed_attempt_count"] == 1
