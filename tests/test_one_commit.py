"""COMMIT opens the load (CO-1, Deterministic Close-Out).

Mike Zachary, 2026-09-14 (D5): COMMIT "creates the conversion from opportunity
idea to actual accepted load/mission. the creation of the classified card and the
beginning of the deterministic workflow."

Before this, COMMIT set the timestamp, held the calendar and sent portal access,
but opened no load row -- so the Driver Cockpit's actions, the driver's
milestones and the load calendar had nothing to run on until someone also
pressed BOOK. The load now opens under the Mission Record's own id.
"""

from __future__ import annotations

import pytest

from dispatch import commitment, services
from dispatch.db import set_db_path
from portal.models import sandbox


@pytest.fixture(autouse=True)
def _world(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    from dispatch import scheduling

    # COMMIT asks Outlook to hold the time. No test may reach a real calendar.
    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def candidate(number="L1-COMMIT1", **card):
    card = {"origin": "Jacksonville, FL", "destination": "Savannah, GA", "broker": "Southeast Freight Partners",
            "pickup_window": "2026-09-18 06:00 - 10:00", "delivery_window": "2026-09-18 14:00 - 18:00",
            **card}
    return sandbox.create_entry(source_type="dispatch", source_id=number, title="Commit probe",
                                card_data=card, summary="")["id"]


class TestCommitOpensTheLoad:
    def test_the_load_opens_under_the_records_own_id(self, client):
        record_id = candidate()
        client.post(f"/brief/mission/{record_id}/commit")
        load = services.get_load(record_id)
        assert load is not None
        assert (load["pickup_location"], load["delivery_location"]) == ("Jacksonville, FL", "Savannah, GA")
        assert load["customer"] == "Southeast Freight Partners"
        assert load["pickup_datetime"].startswith("2026-09-18") and load["delivery_datetime"].startswith("2026-09-18")
        assert sandbox.get(record_id)["operational_load"]["opened"] is True

    def test_no_second_record_is_made(self, client):
        record_id = candidate()
        before = set(sandbox.get_all())
        client.post(f"/brief/mission/{record_id}/commit")
        assert set(sandbox.get_all()) == before
        assert [l["load_id"] for l in services.list_loads()] == [record_id]

    def test_a_load_already_open_is_left_alone(self, client):
        record_id = candidate()
        services.create_load_with_id(record_id, customer="Booked first")
        client.post(f"/brief/mission/{record_id}/commit")
        assert services.get_load(record_id)["customer"] == "Booked first"
        assert sandbox.get(record_id)["operational_load"] == {"opened": False, "note": "The load was already open."}
        assert commitment.is_committed(sandbox.get(record_id))

    def test_a_window_nothing_could_read_stays_in_words(self, client):
        record_id = candidate(pickup_window="whenever the dock opens")
        client.post(f"/brief/mission/{record_id}/commit")
        load = services.get_load(record_id)
        assert load["pickup_datetime"] == ""
        assert "Pickup as dictated, not read as a date: whenever the dock opens" in load["notes"]

    def test_the_driver_can_work_the_committed_load_straight_away(self, client):
        record_id = candidate()
        client.post(f"/brief/mission/{record_id}/commit")
        client.post(f"/portal/mission/{record_id}/milestone", data={"milestone_event": "dispatched"})
        assert services.get_load(record_id)["status"] == "dispatched"
        html = client.get(f"/portal/mission/{record_id}").get_data(as_text=True)
        assert "no open load yet" not in html and "NEXT: ON MY WAY TO PICKUP" in html


class TestSampleLoadsAreNotLive:
    def test_the_dispatch_screen_marks_bundled_samples_simulated(self, client):
        assert client.get("/dispatch").status_code == 200
        seeded = [e for e in sandbox.get_all().values() if e["source_type"] == "dispatch"]
        assert seeded and all(e["data_origin"] == "SIMULATED" for e in seeded)
