"""One Driver Cockpit.

Mike Zachary, 2026-09-14: "can we merge the two driver screens and leave them
sized for tablet full screen/laptop ... no need to alter visual", then "park one
and alter the other by writing the needed code for the 'Real' one needed".

The Driver Cockpit (/portal/mission/<id>) is the real one. The Driver Portal home
(/driver/home) is parked: a driver sign-in lands in the cockpit, and the Driver
Portal's actions are worked from the cockpit's Mission Actions column through
the same code (portal/driver_actions.py).
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from dispatch import commitment, services
from dispatch.db import set_db_path
from portal.models import sandbox
from tests.conftest import close_the_file


@pytest.fixture(autouse=True)
def _world(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app({"TESTING": True, "LOGIN_DISABLED": False})
    with app.test_client() as c:
        yield c


def as_driver(client):
    """A driver-PIN session, as the PIN window opens it."""
    with client.session_transaction() as s:
        s["driver_open"] = True
        s["role"] = "Driver"


def as_operations(client):
    with client.session_transaction() as s:
        s["user_id"] = "ops-test"
        s["role"] = "Operations"


def mission(*, with_load=True, status=None, number="L1-TEST01"):
    """A committed Mission Record, with its load row opened under its own id."""
    entry = sandbox.create_entry(source_type="dispatch", source_id=number, title="Cockpit probe",
                                 card_data={"origin": "Jacksonville, FL", "destination": "Savannah, GA"},
                                 summary="")
    data = sandbox._load()
    data[entry["id"]].update(commitment.commit(data[entry["id"]], when="2026-09-14T12:00:00+00:00"))
    sandbox._save(data)
    if with_load:
        services.create_load_with_id(entry["id"], customer="Southeast Freight Partners",
                                     pickup_location="Jacksonville, FL", delivery_location="Savannah, GA")
        for event in {"dispatched": ["dispatched"],
                      "en_route_pickup": ["dispatched", "en_route_pickup"],
                      "completed": ["dispatched", "en_route_pickup", "arrived_pickup", "loaded",
                                    "departed_pickup", "arrived_delivery", "delivered", "completed"],
                      }.get(status, []):
            services.add_milestone(entry["id"], event_type=event, source="driver", entered_by="test")
    return entry["id"]


def page(client, record_id, **params):
    return client.get(f"/portal/mission/{record_id}", query_string=params).get_data(as_text=True)


class TestDriversLandInTheCockpit:
    def test_a_driver_sign_in_opens_the_cockpit(self, client):
        as_driver(client)
        assert client.get("/portal", follow_redirects=True).status_code == 200

    def test_nobody_signed_in_is_sent_to_sign_in(self, client):
        assert client.get("/portal").status_code == 302

    # `/booking` is not on this list: the board was deleted on 2026-09-17.
    @pytest.mark.parametrize("path", ["/intake", "/loads", "/home"])
    def test_a_driver_sign_in_opens_nothing_else(self, client, path):
        as_driver(client)
        resp = client.get(path)
        assert resp.status_code == 302 and "/login" in resp.headers["Location"]

    def test_the_parked_home_still_renders(self, client):
        as_driver(client)
        assert client.get("/driver/home").status_code == 200

    def test_a_driver_signs_out_rather_than_going_to_dispatch(self, client):
        record_id = mission()
        as_driver(client)
        html = page(client, record_id)
        assert "Sign out" in html and "&larr; Dispatch" not in html

    def test_operations_keeps_its_way_back_to_dispatch(self, client):
        record_id = mission()
        as_operations(client)
        html = page(client, record_id)
        assert "&larr; Dispatch" in html and "Sign out" not in html


class TestTheDriverActionsAreOnTheCockpit:
    def test_the_actions_are_in_the_mission_actions_column(self, client):
        services.create_equipment(unit_number="T-1", equipment_type="other")
        record_id = mission()
        as_driver(client)
        html = page(client, record_id)
        # **His three photo names**, corrected 2026-09-17: the tiles carried the
        # old two-name list, so "LOAD SECUREMENT PHOTOS" was here and a Loaded
        # Vehicle photo could not be uploaded at all.
        for name in ("UPLOAD DOCUMENTS - PHOTOS", "DETENTION - REPORT A PROBLEM",
                     "FUEL RECEIPT", "ALL MILESTONES", "POD PHOTO",
                     "PHOTOS - LOADED VEHICLE", "PHOTOS - MID-ROUTE SECUREMENT",
                     "PHOTOS - FINAL CONDITION"):
            assert name in html
        assert "DRIVER COCKPIT" in html  # the same screen, not a new one
        # START RUN is the one act and it lives in the status area, not in this
        # column (Owner ruling, 2026-09-16). Two buttons for one act is two
        # things to decide between at a dock.
        assert "NEXT: START RUN" not in html
        assert "START RUN" in html

    def test_the_next_step_records_the_milestone(self, client):
        record_id = mission()
        as_driver(client)
        resp = client.post(f"/portal/mission/{record_id}/milestone",
                           data={"milestone_event": "dispatched", "view": "PICKUP"})
        assert resp.status_code == 302 and f"/portal/mission/{record_id}" in resp.headers["Location"]
        assert services.get_load(record_id)["status"] == "dispatched"
        assert "Dispatched recorded." in page(client, record_id)  # said in the JOE line

    def test_an_arrival_points_at_arrive(self, client):
        record_id = mission(status="en_route_pickup")
        as_driver(client)
        assert 'data-trigger="arrive"' in page(client, record_id)

    def test_a_mission_with_no_open_load_says_so(self, client):
        record_id = mission(with_load=False)
        as_driver(client)
        client.post(f"/portal/mission/{record_id}/milestone", data={"milestone_event": "dispatched"})
        # **Points at COMMIT, not Book Load** (BATCH 9). BOOK books the day;
        # COMMIT opens the operational load, so the old line named a button
        # that had stopped opening anything.
        said = page(client, record_id)
        assert "has not been committed yet" in said
        assert "Book Load" not in said

    def test_an_exception_is_logged_against_the_load(self, client):
        record_id = mission()
        as_driver(client)
        client.post(f"/portal/mission/{record_id}/exception", data={"exception_type": "detention"})
        assert len(services.get_load_bundle(record_id)["exceptions"]) == 1

    def test_a_pod_photo_joins_the_evidence(self, client):
        record_id = mission(status="dispatched")
        as_driver(client)
        # One attachment path (BATCH 8): the Mission Record, and what the
        # document is. Was `/pod`.
        client.post(f"/portal/mission/{record_id}/attach", content_type="multipart/form-data",
                    data={"classification": "pod",
                          "artifact": (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "pod.png")})
        kinds = [e["evidence_type"] for e in services.get_load_bundle(record_id)["evidence"]]
        assert kinds == ["pod"]

    def test_a_fuel_receipt_needs_its_photo_and_no_mission(self, client):
        truck = services.create_equipment(unit_number="T-1", equipment_type="other")
        as_driver(client)
        resp = client.post("/portal/fuel-receipt", data={"equipment_id": truck["equipment_id"]},
                           follow_redirects=True)
        assert "A photo of the receipt is required" in resp.get_data(as_text=True)

    def test_a_fuel_receipt_cannot_claim_someone_elses_load(self, client):
        truck = services.create_equipment(unit_number="T-1", equipment_type="other")
        shown, other = mission(), mission(number="L1-TEST02")
        as_driver(client)
        resp = client.post("/portal/fuel-receipt", follow_redirects=True, content_type="multipart/form-data",
                           data={"equipment_id": truck["equipment_id"], "record_id": shown, "load_id": other,
                                 "fuel_file": (io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "r.png")})
        assert "That load is not yours." in resp.get_data(as_text=True)

    def test_a_driver_cannot_act_on_an_archived_load(self, client):
        """**Changed 2026-09-16.** `completed` was in this set, so the moment a
        driver sent his POD and finished the run his own cockpit told him
        *"This mission has no open load yet. Operations opens it with Book
        Load."* — false, at the exact moment the work was done, and pointing at
        a door that is not his.

        A completed run stays readable. Nothing can be advanced from it:
        `NEXT_STEP` has no `completed` key and the transition gate refuses
        anything posted anyway."""
        record_id = mission(status="completed")
        # Operations closes the file before Archive retains it (2026-09-17).
        close_the_file(record_id, by="operations")
        services.archive_load(record_id)
        as_driver(client)

        client.post(f"/portal/mission/{record_id}/exception", data={"exception_type": "delay"})

        assert services.get_load_bundle(record_id)["exceptions"] == []

    def test_a_finished_run_is_still_the_drivers_to_read(self, client):
        record_id = mission(status="completed")
        as_driver(client)

        page = client.get(f"/portal/mission/{record_id}").get_data(as_text=True)

        assert "no open load yet" not in page


class TestArriveIsOneTap:
    def test_arrive_also_records_the_arrival_milestone(self, client, monkeypatch):
        from portal.routes import joe_portal

        class Mail:
            def send(self, to, subject, body, **kw):
                return {"ok": True, "sent": True}

            def draft(self, to, subject, body, **kw):
                return {"ok": True, "drafted": True}

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: Mail())
        record_id = mission(status="en_route_pickup")
        as_driver(client)
        resp = client.post(f"/portal/mission/{record_id}/arrive", data={"view": "PICKUP"})
        assert resp.status_code == 200
        assert "Arrived Pickup recorded." in resp.get_json()["note"]
        assert services.get_load(record_id)["status"] == "at_pickup"

    def test_arrive_without_an_open_load_records_no_milestone(self, client, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: None)
        record_id = mission(with_load=False)
        as_driver(client)
        resp = client.post(f"/portal/mission/{record_id}/arrive", data={"view": "PICKUP"})
        assert resp.status_code == 200 and "recorded." not in resp.get_json()["note"]


class TestTheCockpitCarriesItsCsrfToken:
    """The cockpit does not extend base.html, so it never had base.html's fetch
    wrapper: ARRIVE and the checklist ticks went out with no CSRF token and were
    refused outside TESTING. The cockpit now sends its own."""

    def test_the_page_carries_the_token(self, client):
        record_id = mission()
        as_driver(client)
        assert 'name="csrf-token"' in page(client, record_id)

    def test_every_fetch_sends_it(self):
        template = Path("portal/templates/joe_portal.html").read_text(encoding="utf-8")
        fetches = template.count("fetch(window.location")
        assert fetches and template.count("'X-CSRF-Token': CSRF_TOKEN") == fetches

    def test_arrive_without_the_token_is_refused(self, client, monkeypatch):
        from portal.routes import joe_portal

        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: None)
        record_id = mission(with_load=False)
        as_driver(client)
        raw = client.post(f"/portal/mission/{record_id}/arrive", data={"view": "PICKUP"}, csrf=False)
        assert raw.status_code == 403
