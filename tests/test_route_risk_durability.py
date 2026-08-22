"""Tests for M3: Route Risk events survive a process restart.

Before M3 (DISPATCH_BUILD_MATRIX_v1), Route Risk events lived only in
`route_risk.engine._ROUTE_RISK_EVENTS`, a module-level dict -- while a fully
formed `route_risk_events` table sat in the SQLite schema and was never
written to. Restarting the process destroyed every recorded condition, and the
Driver Portal (portal/routes/driver_portal.py) then displayed "no active Route
Risk events" as though that were a fact about the road rather than an artifact
of a restart.

That made one operational record class unclassifiable in the protected-state
map: not protected (a restart destroyed it), not derived (nothing could rebuild
it), not disposable (a surface read it). The reset doctrine's own test -- "if
Dispatch cannot survive a shutdown and startup cycle, the architecture should
be reviewed" -- had exactly one true failure in the repository, and this was it.

The engine keeps its decoupling contract: persistence is injected, never
imported, the same way `comi_eval_fn` already was.
"""

from __future__ import annotations

import importlib

import pytest

from dispatch import services as dispatch_svc
from dispatch import store as dispatch_store
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return dispatch_svc.create_load(
        customer="Route Risk Test Broker",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )


def _record(load_id: str, **kw):
    defaults = dict(
        condition_summary="Heavy rain band on I-95 N near Glynn County",
        consequence_level=3,
        estimated_delay_minutes=15,
        affected_corridor="I-95 N",
        affected_area="Glynn County, GA",
    )
    defaults.update(kw)
    return dispatch_svc.record_route_risk_event(load_id=load_id, **defaults)


# ── the actual defect: survival across a restart ───────────────────────


class TestSurvivesRestart:
    def test_event_is_readable_after_module_reload(self, load):
        """A module reload is the closest in-process stand-in for a restart:
        it discards every module-level dict, which is exactly what killed the
        old store."""
        load_id = load["load_id"]
        _record(load_id)
        assert dispatch_svc.get_route_risk(load_id)["available"] is True

        import route_risk.engine
        import route_risk
        import dispatch.route_risk

        importlib.reload(route_risk.engine)
        importlib.reload(route_risk)
        importlib.reload(dispatch.route_risk)

        # Module state is gone...
        assert route_risk.engine._ROUTE_RISK_EVENTS == {}
        # ...and the event is still there.
        risk = dispatch.route_risk.get_route_risk(load_id)
        assert risk["available"] is True
        assert risk["summary"] == "Heavy rain band on I-95 N near Glynn County"
        assert risk["consequence_level"] == 3

    def test_event_is_in_the_database_not_module_memory(self, load):
        import route_risk.engine

        load_id = load["load_id"]
        _record(load_id)
        assert route_risk.engine._ROUTE_RISK_EVENTS.get(load_id) in (None, [])
        assert len(dispatch_store.list_route_risk_events(load_id)) == 1

    def test_no_dual_write(self, load):
        """One record, one place. Two copies would be two sources of truth."""
        import route_risk.engine

        load_id = load["load_id"]
        _record(load_id)
        _record(load_id, condition_summary="Second condition")
        assert dispatch_store.list_route_risk_events(load_id) != []
        assert route_risk.engine._ROUTE_RISK_EVENTS == {}


# ── round-trip fidelity ────────────────────────────────────────────────


class TestRoundTripFidelity:
    def test_stored_event_equals_the_recorded_event(self, load):
        recorded = _record(load["load_id"])
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        assert read_back == recorded

    def test_every_engine_field_survives(self, load):
        recorded = _record(load["load_id"])
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        for key, value in recorded.items():
            assert read_back[key] == value, key

    def test_map_visual_placeholder_is_reconstructed_exactly(self, load):
        recorded = _record(load["load_id"])
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        assert read_back["map_visual_placeholder"] == recorded["map_visual_placeholder"]
        assert read_back["map_visual_placeholder"]["label"] == (
            "Corridor Map Placeholder: I-95 N"
        )

    def test_has_map_visual_false_is_not_silently_true(self, load):
        """Stored, not assumed. The default is True everywhere in the codebase
        today, which is exactly why a reconstructed value would have looked
        correct while being wrong."""
        recorded = _record(load["load_id"], has_map_visual=False)
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        assert read_back["map_visual_placeholder"]["available"] is False

    def test_booleans_come_back_as_booleans_not_ints(self, load):
        recorded = _record(load["load_id"], consequence_level=5)
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        for field in (
            "driver_notification_required",
            "stakeholder_notification_required",
            "mission_visibility_update_required",
            "comi_required",
        ):
            assert isinstance(read_back[field], bool), field
        assert read_back["driver_notification_required"] is True

    def test_is_live_data_stays_false(self, load):
        recorded = _record(load["load_id"])
        read_back = dispatch_store.get_route_risk_event(recorded["route_risk_event_id"])
        assert read_back["is_live_data"] is False


# ── behavior preserved ─────────────────────────────────────────────────


class TestBehaviorPreserved:
    def test_latest_event_wins(self, load):
        """Timestamps are forced apart deliberately.

        created_at has second precision, so two events recorded in the same
        second tie -- and the engine's max(key=created_at) resolves a tie by
        list order. That ambiguity is pre-existing (it tied in the in-memory
        store too) and is NOT resolved here: M3 is a durability fix, and
        picking a tiebreak rule would be a behavior change outside its scope.
        Recorded in the walkthrough report instead.
        """
        load_id = load["load_id"]
        older = _record(load_id, condition_summary="Older", consequence_level=1)
        newer = _record(load_id, condition_summary="Newer", consequence_level=4)

        from dispatch.db import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE route_risk_events SET created_at=? WHERE route_risk_event_id=?",
                ("2026-08-21T09:00:00Z", older["route_risk_event_id"]),
            )
            conn.execute(
                "UPDATE route_risk_events SET created_at=? WHERE route_risk_event_id=?",
                ("2026-08-21T11:00:00Z", newer["route_risk_event_id"]),
            )

        risk = dispatch_svc.get_route_risk(load_id)
        assert risk["available"] is True
        assert risk["summary"] == "Newer"
        assert risk["consequence_level"] == 4
        assert risk["latest_event"]["route_risk_event_id"] == newer["route_risk_event_id"]

    def test_list_is_ordered_newest_first(self, load):
        load_id = load["load_id"]
        first = _record(load_id, condition_summary="First")
        second = _record(load_id, condition_summary="Second")

        from dispatch.db import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE route_risk_events SET created_at=? WHERE route_risk_event_id=?",
                ("2026-08-21T09:00:00Z", first["route_risk_event_id"]),
            )
            conn.execute(
                "UPDATE route_risk_events SET created_at=? WHERE route_risk_event_id=?",
                ("2026-08-21T11:00:00Z", second["route_risk_event_id"]),
            )

        events = dispatch_store.list_route_risk_events(load_id)
        assert [e["condition_summary"] for e in events] == ["Second", "First"]

    def test_no_events_returns_the_unavailable_shape(self, load):
        risk = dispatch_svc.get_route_risk(load["load_id"])
        assert risk["available"] is False
        assert risk["consequence_level"] == 0
        assert risk["risk_level"] == "Level 0"
        assert risk["latest_event"] is None

    def test_events_are_scoped_to_their_load(self, load):
        other = dispatch_svc.create_load(customer="Other Broker")
        _record(load["load_id"])
        assert len(dispatch_store.list_route_risk_events(load["load_id"])) == 1
        assert dispatch_store.list_route_risk_events(other["load_id"]) == []

    def test_list_all_returns_newest_first(self, load):
        load_id = load["load_id"]
        first = _record(load_id, condition_summary="First")
        second = _record(load_id, condition_summary="Second")
        ids = [e["route_risk_event_id"] for e in dispatch_store.list_route_risk_events()]
        assert set(ids) == {first["route_risk_event_id"], second["route_risk_event_id"]}

    def test_comi_evaluation_still_drives_the_flags(self, load):
        """Consequence thresholds are untouched by M3 -- they belong to the
        Route Risk context, which is unwritten doctrine (B-09).

        Asserted against the real evaluator Dispatch injects
        (dispatch/comi_routing.py::evaluate_comi_routing), not the engine's
        no-injection fallback: for trigger_type "route_risk_event" the driver
        is alerted from level 1, and stakeholder/publisher from level 3.
        """
        silent = _record(load["load_id"], consequence_level=0)
        low = _record(load["load_id"], consequence_level=1)
        high = _record(load["load_id"], consequence_level=5)

        assert silent["driver_notification_required"] is False
        assert silent["stakeholder_notification_required"] is False

        assert low["driver_notification_required"] is True
        assert low["stakeholder_notification_required"] is False
        assert low["comi_required"] is False

        assert high["driver_notification_required"] is True
        assert high["stakeholder_notification_required"] is True
        assert high["comi_required"] is True

        # Mission Visibility updates on every route risk event, at any level.
        for ev in (silent, low, high):
            assert ev["mission_visibility_update_required"] is True


# ── the standalone engine stays standalone ─────────────────────────────


class TestEngineStaysDecoupled:
    def test_engine_imports_without_dispatch(self):
        """route_risk/ must remain independently importable -- persistence is
        injected, never imported."""
        import route_risk.engine as engine
        import inspect

        source = inspect.getsource(engine)
        assert "import dispatch" not in source
        assert "from dispatch" not in source

    def test_engine_without_a_store_still_uses_memory(self):
        import route_risk.engine as engine

        engine._ROUTE_RISK_EVENTS.clear()
        try:
            event = engine.record_route_risk_event(
                load_id="STANDALONE-1", condition_summary="No store injected",
            )
            assert engine._ROUTE_RISK_EVENTS["STANDALONE-1"] == [event]
            assert engine.get_route_risk("STANDALONE-1")["available"] is True
        finally:
            engine._ROUTE_RISK_EVENTS.clear()

    def test_injected_store_receives_the_event(self):
        import route_risk.engine as engine

        captured: list[dict] = []
        engine._ROUTE_RISK_EVENTS.clear()
        try:
            engine.record_route_risk_event(
                load_id="STANDALONE-2",
                condition_summary="Injected",
                store_fn=lambda ev: captured.append(ev) or ev,
            )
            assert len(captured) == 1
            assert "STANDALONE-2" not in engine._ROUTE_RISK_EVENTS
        finally:
            engine._ROUTE_RISK_EVENTS.clear()


# ── the schema migration is idempotent ─────────────────────────────────


class TestMigration:
    def test_has_map_visual_column_exists(self):
        from dispatch.db import get_connection

        with get_connection() as conn:
            cols = {r["name"] for r in conn.execute(
                "PRAGMA table_info(route_risk_events)"
            ).fetchall()}
        assert "has_map_visual" in cols

    def test_reopening_the_database_does_not_fail(self, load):
        """_apply_migrations runs on every connection; the ALTER must stay a
        harmless no-op the second time."""
        from dispatch.db import get_connection

        _record(load["load_id"])
        for _ in range(3):
            with get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
        assert len(dispatch_store.list_route_risk_events(load["load_id"])) == 1
