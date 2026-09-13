"""The schema is built once per process, not once per connection.

`_init_db` is idempotent, so running it on every connection was never
*wrong*. It was just several hundred DDL statements between opening a
connection and asking it anything -- paid again on every connection, and
Dispatch opens a great many of them per page.

These tests hold the guard to both halves of its bargain: the schema stops
being rebuilt, and it is still there when anything needs it -- including
after the database file is replaced underneath a running process, which is
exactly what a restore does.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from dispatch import db


@pytest.fixture()
def fresh_db(tmp_path):
    db.set_db_path(tmp_path / "dispatch.db")
    yield tmp_path / "dispatch.db"
    db.set_db_path(None)


def _count_init_calls(monkeypatch):
    calls = []
    real = db._init_db

    def counting(conn):
        calls.append(conn)
        return real(conn)

    monkeypatch.setattr(db, "_init_db", counting)
    return calls


class TestTheSchemaIsBuiltOnce:
    def test_a_second_connection_does_not_rebuild_the_schema(self, fresh_db, monkeypatch):
        with db.get_connection():
            pass
        calls = _count_init_calls(monkeypatch)

        for _ in range(10):
            with db.get_connection():
                pass

        assert calls == [], "the schema was rebuilt on a connection that did not need it"

    def test_the_first_connection_does_build_it(self, fresh_db, monkeypatch):
        calls = _count_init_calls(monkeypatch)

        with db.get_connection():
            pass

        assert len(calls) == 1

    def test_the_tables_are_actually_there_afterwards(self, fresh_db):
        with db.get_connection() as conn:
            pass
        with db.get_connection() as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }

        # A few from each of the schemas _init_db is responsible for: the core
        # tables, the Spine, connectors, tokens.
        assert {"loads", "visibility", "milestones", "evidence"} <= names
        assert {"work_items", "portal_cards"} <= names, "Spine schema missing"
        assert {"operational_tokens", "token_audit"} <= names, "token schema missing"
        assert "connector_audit" in names, "connector schema missing"

    def test_writes_still_work_through_the_second_connection(self, fresh_db):
        from dispatch import services

        load = services.create_load(customer="Guarded Co")
        assert services.get_load(load["load_id"])["customer"] == "Guarded Co"


class TestTheMemoDoesNotOutliveTheDatabase:
    def test_a_different_path_gets_its_own_schema(self, tmp_path, monkeypatch):
        db.set_db_path(tmp_path / "one.db")
        with db.get_connection():
            pass

        calls = _count_init_calls(monkeypatch)
        db.set_db_path(tmp_path / "two.db")
        with db.get_connection() as conn:
            assert conn.execute("SELECT count(*) FROM loads").fetchone()[0] == 0

        assert len(calls) == 1, "the second database was never given a schema"
        db.set_db_path(None)

    def test_a_deleted_database_is_rebuilt(self, fresh_db, monkeypatch):
        with db.get_connection():
            pass

        # What a restore looks like from in here: the file this process has
        # already built a schema for is simply gone.
        fresh_db.unlink()
        for stray in fresh_db.parent.glob("dispatch.db-*"):
            stray.unlink()

        calls = _count_init_calls(monkeypatch)
        with db.get_connection() as conn:
            assert conn.execute("SELECT count(*) FROM loads").fetchone()[0] == 0

        assert len(calls) == 1, "the schema was not rebuilt after the file was replaced"

    def test_forgetting_the_memo_rebuilds_on_the_next_connection(self, fresh_db, monkeypatch):
        with db.get_connection():
            pass

        calls = _count_init_calls(monkeypatch)
        db.forget_initialised_schemas()
        with db.get_connection():
            pass
        with db.get_connection():
            pass

        assert len(calls) == 1, "forgetting should cost exactly one rebuild, not none and not two"


class TestConcurrentFirstConnections:
    def test_threads_racing_the_first_connection_all_get_a_schema(self, tmp_path):
        """Repeated, because a single pass proves nothing about a race.

        The first version of this test ran one trial and passed locally every
        time. CI failed it, once, on a pull_request run whose push run on the
        identical commit had gone green -- which is what a race looks like from
        the outside. The cause was real: the busy timeout was being set after
        `PRAGMA journal_mode`, so the statement most likely to collide ran
        unprotected. Reproducing it took eight threads and forty attempts, so
        one attempt here would only have hidden it again.
        """
        errors: list[BaseException] = []

        def worker(start):
            try:
                start.wait(timeout=5)
                with db.get_connection() as conn:
                    conn.execute("SELECT count(*) FROM loads").fetchone()
            except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
                errors.append(exc)

        for trial in range(15):
            db.set_db_path(tmp_path / f"race-{trial}.db")
            start = threading.Barrier(8)
            threads = [threading.Thread(target=worker, args=(start,)) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            assert not any(t.is_alive() for t in threads), f"trial {trial}: a thread never finished"
            assert errors == [], f"trial {trial}: {errors}"
        db.set_db_path(None)
