"""A sweep keeps what it finds, as cards carrying their true origin.

CO-2, 2026-09-14. `dispatch.sweep.start` counted acquisition's results and kept
none of them, so "5 opportunity records" put nothing on a screen. And a sample
must never become live freight by being saved: CLAUDE.md section 6, *never
represent sample data as live data*.

D1: *"only API / MCP connected boards will be swept."* Nothing here reads a
board; acquisition reads its configured source and these tests stand in for it.
"""

from __future__ import annotations

import json

import pytest

from dispatch import sweep
from dispatch.db import set_db_path
from portal.models import opportunity_card, sandbox


def _load(load_id, origin=None, pickup="2099-03-02 06:00 - 10:00", **over):
    load = {"load_id": load_id, "title": "Dry Van - Jacksonville FL to Savannah GA",
            "origin": "Jacksonville, FL", "destination": "Savannah, GA",
            "distance_miles": 140, "rate": 625, "pickup_window": pickup,
            "delivery_window": "2099-03-02 14:00 - 18:00"}
    if origin:
        load["data_origin"] = origin
    load.update(over)
    return load


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield
    set_db_path(None)


class TestTheSweepSavesCards:
    def test_results_become_cards_with_their_origin(self):
        state = sweep.start(runner=lambda: [
            _load("L-LIVE", "LIVE"), _load("L-SAMPLE", "SIMULATED"), _load("L-NONE")])

        assert sandbox.get("SBX-DISPATCH-L-LIVE")["data_origin"] == "LIVE"
        assert sandbox.get("SBX-DISPATCH-L-SAMPLE")["data_origin"] == "SIMULATED"
        # No origin at all is never promoted to live.
        assert sandbox.get("SBX-DISPATCH-L-NONE")["data_origin"] == "SIMULATED"
        assert "3 saved as cards" in state["last_result"]
        assert "1 LIVE" in state["last_result"] and "2 SIMULATED" in state["last_result"]

    def test_a_sample_is_never_laundered_into_live_by_a_second_sweep(self):
        sweep.start(runner=lambda: [_load("L-1", "SIMULATED")])
        sweep.start(runner=lambda: [_load("L-1", "LIVE")])
        assert sandbox.get("SBX-DISPATCH-L-1")["data_origin"] == "SIMULATED"

    def test_a_load_whose_pickup_already_passed_is_not_kept(self):
        state = sweep.start(runner=lambda: [_load("L-OLD", "LIVE",
                                                  pickup="2026-07-30 06:00 - 10:00")])
        assert sandbox.get("SBX-DISPATCH-L-OLD") is None
        assert "pickup already passed" in state["last_result"]

    def test_a_committed_record_is_never_overwritten_by_the_board(self):
        sweep.start(runner=lambda: [_load("L-C", "LIVE", rate=625)])
        sandbox.mark_accepted("SBX-DISPATCH-L-C", 7)
        state = sweep.start(runner=lambda: [_load("L-C", "LIVE", rate=10)])
        assert sandbox.get("SBX-DISPATCH-L-C")["card_data"]["rate"] == 625
        assert "already committed" in state["last_result"]

    def test_cards_are_scored_by_the_engine(self):
        sweep.start(runner=lambda: [_load("L-S", "LIVE")])
        assert isinstance(sandbox.get("SBX-DISPATCH-L-S")["score"], int)

    def test_a_failed_sweep_saves_nothing(self):
        def broken():
            raise ConnectionError("connection timed out")

        before = dict(sandbox.get_all())
        state = sweep.start(runner=broken)
        assert state["state"] == "error"
        assert sandbox.get_all() == before


class TestThroughTheSweepButton:
    def test_the_button_runs_real_acquisition_and_saves_samples_as_simulated(
            self, tmp_path, monkeypatch):
        """The route the Sweep Control button posts to, over the real acquisition
        module reading a bundled-sample directory."""
        from dispatch import acquisition
        from portal.app import create_app

        samples = tmp_path / "samples"
        samples.mkdir()
        (samples / "one.json").write_text(json.dumps(_load("SAMPLE-9")), encoding="utf-8")
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", samples)
        monkeypatch.delenv("DISPATCH_LOAD_SOURCE", raising=False)
        monkeypatch.delenv("DISPATCH_LOAD_API_URL", raising=False)

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            data = client.post("/api/sweep/start").get_json()

        assert "1 saved as cards (1 SIMULATED)" in data["last_result"]
        entry = sandbox.get("SBX-DISPATCH-SAMPLE-9")
        assert entry["data_origin"] == "SIMULATED"
        assert entry["card_data"]["origin"] == "Jacksonville, FL"


class TestTheDispatchScreenUsesTheSamePath:
    def test_seeding_goes_through_from_acquired(self, monkeypatch):
        calls = []
        real = opportunity_card.from_acquired

        def spy(loads, **kw):
            calls.append(len(loads))
            return real(loads, **kw)

        monkeypatch.setattr(opportunity_card, "from_acquired", spy)
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as client:
            assert client.get("/dispatch").status_code == 200
        assert calls, "the Dispatch screen seeded cards by another path"
