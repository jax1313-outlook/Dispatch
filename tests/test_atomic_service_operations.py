"""A service operation that writes twice either writes both or neither.

Before this, every `store.*` call opened, committed and closed its own
connection. `add_milestone()` wrote the milestone in one transaction, the load's
new status in a second and the visibility record in a third, so a crash, a lock
timeout, or a validation error partway through left a milestone recorded against
a load whose status never advanced -- with no rollback, no reconciliation pass,
and nothing on any screen to say the two disagreed.

The suite never saw it because the suite is single-threaded, writes to a local
temp file, and injects no failures. So these tests inject them: each one breaks a
store function that runs *after* the first successful write and then asserts the
first write is gone too.
"""

from __future__ import annotations

import sqlite3

import pytest

from dispatch import db, services, store
from dispatch.db import set_db_path


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        yield
    finally:
        set_db_path(None)


#: The milestone chain that legally reaches `delivered`. The status cascade is
#: gated by validate_status_transition(), so skipping one of these does not
#: advance the load and the delivery notification correctly never fires.
_TO_DELIVERY = (
    "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
    "departed_pickup", "in_transit", "arrived_delivery",
)


class Boom(RuntimeError):
    """An injected failure, distinguishable from a real one."""


def _break_after_first_call(monkeypatch, target_module, name):
    """Let `name` succeed once, then raise. Mimics a lock timeout mid-operation."""
    real = getattr(target_module, name)
    state = {"calls": 0}

    def flaky(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] > 1:
            raise Boom(f"injected failure in {name}")
        return real(*args, **kwargs)

    monkeypatch.setattr(target_module, name, flaky)
    return state


class TestAddMilestone:
    def test_a_failure_writing_visibility_takes_the_milestone_with_it(
        self, database, monkeypatch
    ):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        before = len(store.list_milestones(load_id))

        def exploding_upsert(*_a, **_k):
            raise Boom("injected failure in upsert_visibility")

        monkeypatch.setattr(store, "upsert_visibility", exploding_upsert)

        with pytest.raises(Boom):
            services.add_milestone(load_id, "dispatched", note="left the yard")

        assert len(store.list_milestones(load_id)) == before, (
            "the milestone survived a failed operation: the load now has an event "
            "recorded against a status that was never advanced"
        )
        assert store.get_load(load_id)["status"] == "created"

    def test_a_failure_updating_the_load_leaves_no_milestone_behind(
        self, database, monkeypatch
    ):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]

        def exploding_update(*_a, **_k):
            raise Boom("injected failure in update_load")

        monkeypatch.setattr(store, "update_load", exploding_update)

        with pytest.raises(Boom):
            services.add_milestone(load_id, "dispatched")

        assert store.list_milestones(load_id) == []

    def test_the_successful_path_still_writes_everything(self, database):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        services.add_milestone(load_id, "dispatched")

        assert len(store.list_milestones(load_id)) == 1
        assert store.get_load(load_id)["status"] == "dispatched"
        assert store.get_visibility(load_id)["current_status"] == "dispatched"


class TestCreateLoad:
    def test_a_failure_writing_visibility_leaves_no_orphan_load(self, database, monkeypatch):
        def exploding_upsert(*_a, **_k):
            raise Boom("injected failure in upsert_visibility")

        monkeypatch.setattr(store, "upsert_visibility", exploding_upsert)
        before = len(store.list_loads())

        with pytest.raises(Boom):
            services.create_load(customer="Orphan Freight")

        assert len(store.list_loads()) == before, (
            "a load exists with no visibility record: every surface that joins the "
            "two now has a row it cannot render"
        )


class TestExceptions:
    def test_a_failed_open_exception_writes_nothing(self, database, monkeypatch):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]

        monkeypatch.setattr(
            store, "upsert_visibility", lambda *a, **k: (_ for _ in ()).throw(Boom("x"))
        )
        with pytest.raises(Boom):
            services.open_exception(load_id, exception_type="delay", description="late")

        assert store.list_exceptions(load_id=load_id) == []

    def test_a_failed_resolve_leaves_the_exception_open(self, database, monkeypatch):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        exc = services.open_exception(load_id, exception_type="delay", description="late")

        assert store.get_visibility(load_id) is not None  # the write we break is reached
        monkeypatch.setattr(
            store, "upsert_visibility", lambda *a, **k: (_ for _ in ()).throw(Boom("x"))
        )
        with pytest.raises(Boom):
            services.resolve_exception(exc["exception_id"], resolution_note="cleared")

        assert [e for e in store.list_exceptions(load_id=load_id) if e["exception_id"] == exc["exception_id"]][0]["status"] == "open", (
            "the exception reads resolved while the visibility record still flags it open"
        )


class TestNotificationsAreNotSentForWorkThatRolledBack:
    """The worst failure this system can have is invisible: an email that went out
    for a delivery the database then discarded."""

    def test_a_rolled_back_delivery_sends_nothing(self, database, monkeypatch):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        for event in _TO_DELIVERY:
            services.add_milestone(load_id, event)

        sent = []
        monkeypatch.setattr(
            services.notifications, "notify_delivered",
            lambda *a, **k: sent.append(a) or "sent",
        )
        monkeypatch.setattr(
            store, "upsert_visibility", lambda *a, **k: (_ for _ in ()).throw(Boom("x"))
        )

        with pytest.raises(Boom):
            services.add_milestone(load_id, "delivered")

        assert sent == [], "a delivery notification went out for a transaction that rolled back"

    def test_a_committed_delivery_does_send(self, database, monkeypatch):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        for event in _TO_DELIVERY:
            services.add_milestone(load_id, event)

        sent = []
        monkeypatch.setattr(
            services.notifications, "notify_delivered",
            lambda *a, **k: sent.append(a) or "sent",
        )
        services.add_milestone(load_id, "delivered")
        assert len(sent) == 1

    def test_a_send_that_fails_does_not_undo_the_committed_work(self, database, monkeypatch):
        load = services.create_load(customer="Acme")
        load_id = load["load_id"]
        for event in _TO_DELIVERY:
            services.add_milestone(load_id, event)

        def exploding_send(*_a, **_k):
            raise Boom("SMTP is down")

        monkeypatch.setattr(services.notifications, "notify_delivered", exploding_send)
        services.add_milestone(load_id, "delivered")  # must not raise

        assert store.get_load(load_id)["status"] == "delivered"


class TestUnitOfWorkItself:
    def test_nested_units_commit_once_and_roll_back_together(self, database):
        load = services.create_load(customer="Acme")

        with pytest.raises(Boom):
            with db.unit_of_work():
                services.assign_driver_free_form = None  # noqa: B018 - no-op marker
                store.update_load(load["load_id"], customer="Changed")
                # an inner atomic operation joins rather than committing early
                services.add_milestone(load["load_id"], "dispatched")
                raise Boom("outer failure after an inner atomic operation succeeded")

        reread = store.get_load(load["load_id"])
        assert reread["customer"] == "Acme"
        assert store.list_milestones(load["load_id"]) == []

    def test_a_nested_get_connection_joins_rather_than_opening_a_second(self, database, monkeypatch):
        opened = {"n": 0}
        real = sqlite3.connect

        def counting(*a, **k):
            opened["n"] += 1
            return real(*a, **k)

        with db.unit_of_work():
            monkeypatch.setattr(db.sqlite3, "connect", counting)
            for _ in range(10):
                with db.get_connection() as conn:
                    conn.execute("SELECT 1").fetchone()

        assert opened["n"] == 0

    def test_after_commit_runs_immediately_outside_a_unit_of_work(self, database):
        ran = []
        db.after_commit(lambda: ran.append(1))
        assert ran == [1]

    def test_after_commit_does_not_leak_between_transactions(self, database):
        """A drained callback list left behind would silently swallow every later send."""
        with db.unit_of_work():
            db.after_commit(lambda: None)
        ran = []
        db.after_commit(lambda: ran.append(1))
        assert ran == [1], "a post-transaction callback was queued onto a list nobody drains"

    def test_in_unit_of_work_reports_honestly(self, database):
        assert db.in_unit_of_work() is False
        with db.unit_of_work():
            assert db.in_unit_of_work() is True
        assert db.in_unit_of_work() is False
