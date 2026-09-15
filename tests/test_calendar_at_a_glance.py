"""Calendar at a glance. CO-4, 2026-09-14.

The Owner's must-have: *"Calendar is required. I must be able to see gaps in
days at a glance in order to make decision of accepting loads. Assistance with
pickup and delivery times."*

  * a captured candidate with a date appears on the board as a candidate and
    never counts against capacity (Reality and Possibility never merge);
  * a committed load marks every day from pickup through delivery, transit
    days included;
  * the earliest legal delivery is worked out and an appointment that cannot be
    made is flagged.

Outlook calendar writing is untouched; no test here reaches it.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from dispatch import booking, clock
from dispatch.db import set_db_path
from portal.models import sandbox

MONDAY = date(2026, 9, 21)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("DISPATCH_JOE_TOKEN", "test-token")
    from dispatch import scheduling

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


def _committed(pickup, delivery, load="L1-SPAN"):
    return {"id": "SBX-SPAN", "load_number": load, "committed_at": "2026-09-14T10:00:00Z",
            "card_data": {"origin": "Jacksonville, FL", "destination": "Dallas, TX",
                          "pickup_window": pickup, "delivery_window": delivery}}


class TestTransitDaysAreBooked:
    def test_every_day_from_pickup_to_delivery_is_marked(self):
        book = booking.build({"a": _committed("2026-09-21 06:00", "2026-09-23 14:00")},
                             {}, today=MONDAY)
        days = {d["iso"]: d for d in book["board"]}
        assert [l["phase"] for l in days["2026-09-21"]["loads"]] == ["Pickup"]
        assert [l["phase"] for l in days["2026-09-22"]["loads"]] == ["Transit"]
        assert [l["phase"] for l in days["2026-09-23"]["loads"]] == ["Delivery"]
        assert all(days[d]["state"] == booking.BOOKED
                   for d in ("2026-09-21", "2026-09-22", "2026-09-23"))
        # Mon-Wed of week one are all taken; only Saturday and next week remain.
        assert book["unsold_count"] == 5

    def test_a_same_day_load_has_both_ends_on_one_day(self):
        book = booking.build({"a": _committed("2026-09-21 06:00", "2026-09-21 14:00")},
                             {}, today=MONDAY)
        assert [l["phase"] for l in book["board"][0]["loads"]] == ["Pickup", "Delivery"]

    def test_a_backwards_window_is_not_stretched_into_a_span(self):
        book = booking.build({"a": _committed("2026-09-23", "2026-09-21")}, {}, today=MONDAY)
        assert book["board"][1]["state"] == booking.OPEN


class TestCandidatesAppearAndNeverCount:
    def test_a_dictated_weekday_capture_is_a_candidate_chip_on_the_board(
            self, client, monkeypatch):
        """Through the seventh contract, the way the Owner's voice reaches it.
        The card resolves "Wednesday" at capture, so the board can place it."""
        from portal.models import opportunity_card

        monkeypatch.setattr(opportunity_card, "capture_day", lambda record: MONDAY)
        data = client.post("/api/joe/opportunity", json={
            "origin": "Jacksonville FL", "destination": "Savannah GA", "rate": 1150,
            "pickup_date": "Wednesday 8am"},
            headers={"Authorization": "Bearer test-token", "X-Driver": "mike"}).get_json()
        assert data["carded"]

        record_id = "SBX-DISPATCH-%s" % data["opportunity_id"]
        book = booking.build(sandbox.get_all(), {}, today=MONDAY)
        wednesday = next(d for d in book["board"] if d["iso"] == "2026-09-23")
        assert [c["record_id"] for c in wednesday["candidates"]] == [record_id]
        assert wednesday["state"] == booking.OPEN
        assert book["unsold_count"] == book["sellable_count"]

    def test_the_booking_screen_draws_the_chip(self, client, monkeypatch):
        monkeypatch.setattr(clock, "home_date", lambda: MONDAY)
        sandbox.create_entry(source_type="dispatch", source_id="CAND-1", title="Candidate",
                             card_data={"origin": "Tampa, FL", "destination": "Miami, FL",
                                        "pickup_window": "%s 08:00" % MONDAY.isoformat()})
        html = client.get("/booking").get_data(as_text=True)
        assert "candidate" in html and "Tampa, FL" in html


class TestTimeHelp:
    def test_the_card_carries_the_earliest_legal_delivery(self, client):
        client.post("/loads/paste", data={"pasted": (
            "Jacksonville, FL to Atlanta, GA\nPickup: 2099-09-22 06:00\n"
            "Delivery: 2099-09-22 10:00\nRate: $1,200")})
        card = next(iter(sandbox.get_all().values()))["card_data"]
        # 345 table miles at 50 mph is 6.9 h: 12:54, after a 10:00 appointment.
        assert "Earliest legal delivery Tue 22 Sep 12:54" in card["delivery_timing"]
        assert "cannot be made" in card["delivery_timing"]

    def test_a_makeable_appointment_is_not_flagged(self, client):
        client.post("/loads/paste", data={"pasted": (
            "Jacksonville, FL to Atlanta, GA\nPickup: 2099-09-22 06:00\n"
            "Delivery: 2099-09-22 16:00\nRate: $1,200")})
        card = next(iter(sandbox.get_all().values()))["card_data"]
        assert "cannot be made" not in card["delivery_timing"]
        assert "CANNOT_MAKE_DELIVERY" not in [w["code"] for w in card["warnings"]]
