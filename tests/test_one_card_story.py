"""One card story: PASS and an expired pickup take the card and its capture together.

Owner ruling D12, 2026-09-14: *"program only processes committed loads. due to
the life span of only hours to minuties it makes no sense to keep any uncommitted
load information."* Discard on PASS and when the pickup window expires
uncommitted. Never discard a committed record.

Reached the way the screens reach it: captures through the seventh contract,
PASS through the card action, expiry on the next capture.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from dispatch import clock, opportunity
from dispatch.db import set_db_path
from portal.models import opportunity_card, sandbox

HEADERS = {"Authorization": "Bearer test-token", "X-Driver": "mike"}


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


def _capture(client, **over):
    payload = {"origin": "Jacksonville FL", "destination": "Savannah GA", "rate": 1150}
    payload.update(over)
    data = client.post("/api/joe/opportunity", json=payload, headers=HEADERS).get_json()
    assert data["ok"] and data["carded"], data
    return data["opportunity_id"], "SBX-DISPATCH-%s" % data["opportunity_id"]


def _audit_actions():
    from dispatch import audit

    return [e["action"] for e in audit.entries()]


class TestPass:
    def test_pass_takes_the_card_and_the_capture(self, client):
        opp_id, sid = _capture(client)
        resp = client.post("/api/action", json={"sandbox_id": sid, "action": "pass"})
        data = resp.get_json()
        assert data["status"] == "ok" and data["discarded"] is True
        assert sandbox.get(sid) is None
        assert opportunity.get(opp_id) is None
        assert "opportunity-discard" in _audit_actions()

    def test_a_committed_card_is_never_discarded(self, client):
        opp_id, sid = _capture(client)
        client.post(f"/brief/mission/{sid}/commit")
        assert sandbox.get(sid).get("committed_at")

        outcome = opportunity_card.discard(sid, reason="PASS", driver="mike")
        assert outcome["discarded"] is False
        client.post("/api/action", json={"sandbox_id": sid, "action": "pass"})
        assert sandbox.get(sid) is not None
        assert opportunity.get(opp_id) is not None

    def test_reject_on_the_loads_screen_is_the_same_pass(self, client):
        opp_id, sid = _capture(client)
        client.post(f"/brief/mission/{sid}/reject")
        assert sandbox.get(sid) is None
        assert opportunity.get(opp_id) is None


class TestExpiry:
    def test_the_loads_screen_shows_and_clears_a_load_whose_pickup_went_by(self, client):
        old_opp, old_sid = _capture(client, pickup_date="2026-09-01",
                                    destination="Tampa FL")
        new_opp, new_sid = _capture(client, pickup_date="2099-01-05")

        page = client.get("/loads").get_data(as_text=True)
        assert "PICKUP PASSED" in page
        assert "1 load" in page and "past pickup and not committed" in page

        client.post("/loads/clear-expired")
        assert sandbox.get(old_sid) is None
        assert opportunity.get(old_opp) is None
        assert sandbox.get(new_sid) is not None
        assert "Cleared 1 load whose pickup had passed." in client.get("/loads").get_data(as_text=True)

    def test_a_paste_clears_expired_loads_too(self, client):
        old_opp, old_sid = _capture(client, pickup_date="2026-09-01")
        client.post("/loads/paste", data={"pasted": "Tampa, FL to Miami, FL $900"})
        assert sandbox.get(old_sid) is None

    def test_a_committed_load_past_its_pickup_stays(self, client):
        opp_id, sid = _capture(client, pickup_date="2026-09-01")
        client.post(f"/brief/mission/{sid}/commit")
        client.post("/loads/clear-expired")
        assert sandbox.get(sid) is not None
        assert opportunity.get(opp_id) is not None

    def test_looking_at_a_screen_never_discards(self, client):
        """D9: retrieval is not modification."""
        _, sid = _capture(client, pickup_date="2026-09-01")
        client.get("/loads")
        client.get("/booking")
        client.get("/home")
        assert sandbox.get(sid) is not None

    def test_the_capture_contract_itself_discards_nothing(self, client):
        """A side effect on the seventh contract is the Owner's to add."""
        _, sid = _capture(client, pickup_date="2026-09-01")
        _capture(client, destination="Orlando FL")
        assert sandbox.get(sid) is not None

    def test_words_nothing_can_read_never_expire(self):
        record = opportunity.capture(
            {"origin": "Ocala FL", "destination": "Macon GA", "rate": 900,
             "pickup_date": "whenever it is ready"}, driver="mike")
        sid = opportunity_card.from_capture(record)["id"]
        opportunity_card.discard_expired(now=datetime(2099, 1, 1, tzinfo=clock.home_zone()))
        assert sandbox.get(sid) is not None

    def test_a_capture_without_a_card_still_expires(self):
        record = opportunity.capture(
            {"origin": "Ocala FL", "destination": "Macon GA", "rate": 900,
             "pickup_date": "2026-09-01"}, driver="mike")
        gone = opportunity_card.discard_expired(
            now=datetime(2026, 9, 2, 8, 0, tzinfo=clock.home_zone()))
        assert record["opportunity_id"] in gone
        assert opportunity.get(record["opportunity_id"]) is None


class TestTheDeadline:
    def test_a_window_with_an_end_time_goes_by_at_its_end(self):
        deadline = opportunity_card.pickup_deadline("2026-09-15 06:00 - 10:00")
        assert (deadline.hour, deadline.minute) == (10, 0)
        assert deadline.date().isoformat() == "2026-09-15"

    def test_a_day_goes_by_when_the_day_ends(self):
        deadline = opportunity_card.pickup_deadline("2026-09-15 06:00")
        assert (deadline.hour, deadline.minute) == (23, 59)

    def test_words_have_no_deadline(self):
        assert opportunity_card.pickup_deadline("asap") is None
        assert opportunity_card.pickup_deadline("") is None
