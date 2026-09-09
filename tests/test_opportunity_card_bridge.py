"""The bridge from a captured Opportunity to the card the portal renders.

Before this existed, a voice capture stopped in a store no screen read. These
tests hold the seam shut: a capture becomes a card, a re-capture updates the
same card rather than making a second, a sparse capture still produces one, and
a card that cannot be made never costs us the capture.
"""

from __future__ import annotations

import pytest

from dispatch import opportunity
from dispatch.db import set_db_path
from portal.models import opportunity_card, sandbox


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _capture(**over):
    payload = {
        "origin": "Jacksonville FL",
        "destination": "Savannah GA",
        "rate": 1150,
        "equipment": "Dry Van",
        "contact": "Southeast Freight Partners",
        "pickup_date": "Thursday",
    }
    payload.update(over)
    return opportunity.capture(payload, driver="mike", channel="VOICE")


# ── The bridge itself ────────────────────────────────────────────────


class TestTheCardIsMadeAtCaptureTime:
    def test_a_capture_becomes_a_card(self):
        record = _capture()
        entry = opportunity_card.from_capture(record)

        assert entry["source_id"] == record["opportunity_id"]
        assert entry["status"] == "OPEN"
        assert entry["title"] == "Dry Van - Jacksonville FL to Savannah GA"

        card = entry["card_data"]
        assert card["origin"] == "Jacksonville FL"
        assert card["destination"] == "Savannah GA"
        assert card["rate"] == 1150
        assert card["broker"] == "Southeast Freight Partners"
        assert card["equipment_required"] == "Dry Van"
        assert card["pickup_window"] == "Thursday"

    def test_the_card_is_the_one_the_dispatch_tab_reads(self):
        record = _capture()
        opportunity_card.from_capture(record)

        entries = sandbox.get_all()
        dispatch_entries = [
            e for e in entries.values() if e["source_type"] == "dispatch"
        ]
        assert len(dispatch_entries) == 1
        assert dispatch_entries[0]["source_id"] == record["opportunity_id"]

    def test_a_sparse_capture_still_makes_a_card(self):
        """Board, lane and rate are all the contract requires. A capture with
        gaps beats a listing lost to the next screen, and that has to hold all
        the way to the card."""
        record = opportunity.capture(
            {"origin": "Ocala FL", "destination": "Macon GA", "rate": 900},
            driver="mike", channel="VOICE",
        )
        entry = opportunity_card.from_capture(record)

        assert entry["title"] == "Ocala FL to Macon GA"
        card = entry["card_data"]
        assert card["origin"] == "Ocala FL"
        assert card["rate"] == 900
        # Absent, not empty. A card does not invent a broker nobody named.
        assert "broker" not in card
        assert "equipment_required" not in card

    def test_nothing_the_capture_carries_is_lost(self):
        """Freeform pieces and weight has no numeric home on the card, so it
        travels on the entry rather than being dropped or forced into a field
        that formats it as a number."""
        record = _capture(pieces_weight="two pallets, about 4000")
        entry = opportunity_card.from_capture(record)

        card = entry["card_data"]
        assert card["pieces_weight"] == "two pallets, about 4000"
        assert card["captured_via"] == "VOICE"
        assert card["opportunity_id"] == record["opportunity_id"]

    def test_a_recapture_updates_one_card_rather_than_making_two(self):
        first = _capture()
        opportunity_card.from_capture(first)

        again = _capture(contact="Southeast Freight Partners", notes="reposted")
        opportunity_card.from_capture(again)

        dispatch_entries = [
            e for e in sandbox.get_all().values() if e["source_type"] == "dispatch"
        ]
        assert len(dispatch_entries) == 1


# ── Through the endpoint, which is where it actually happens ─────────


class TestCaptureEndpointMakesTheCard:
    def test_the_response_says_a_card_was_made(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_JOE_TOKEN", "test-token")
        resp = client.post(
            "/api/joe/opportunity",
            json={"origin": "Tampa FL", "destination": "Atlanta GA", "rate": 1400},
            headers={"Authorization": "Bearer test-token", "X-Driver": "mike"},
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert data["ok"] is True
        assert data["carded"] is True
        assert data["card_note"] == ""

        entries = [
            e for e in sandbox.get_all().values()
            if e["source_id"] == data["opportunity_id"]
        ]
        assert len(entries) == 1

    def test_a_refused_capture_makes_no_card(self, client, monkeypatch):
        monkeypatch.setenv("DISPATCH_JOE_TOKEN", "test-token")
        before = len(sandbox.get_all())
        resp = client.post(
            "/api/joe/opportunity",
            json={"origin": "Tampa FL"},
            headers={"Authorization": "Bearer test-token", "X-Driver": "mike"},
        )
        assert resp.status_code == 400
        assert len(sandbox.get_all()) == before

    def test_a_card_that_cannot_be_made_never_costs_the_capture(self, client, monkeypatch):
        """The capture is the record that must survive. If carding fails the
        response says so rather than implying a card exists."""
        monkeypatch.setenv("DISPATCH_JOE_TOKEN", "test-token")

        def _boom(record):
            raise RuntimeError("store unavailable")

        monkeypatch.setattr(opportunity_card, "from_capture", _boom)

        resp = client.post(
            "/api/joe/opportunity",
            json={"origin": "Ocala FL", "destination": "Valdosta GA", "rate": 800},
            headers={"Authorization": "Bearer test-token", "X-Driver": "mike"},
        )
        data = resp.get_json()
        assert data["ok"] is True
        assert data["carded"] is False
        assert "store unavailable" in data["card_note"]
        assert opportunity.get(data["opportunity_id"]) is not None


class TestTheCardIsScored:
    def test_a_capture_carries_the_engine_score(self):
        """The score is `dispatch.scoring`'s, not the bridge's. Running the
        deterministic engine at capture time is a screen asking the engine that
        owns the question, not a screen deciding anything."""
        record = _capture()
        entry = opportunity_card.from_capture(record)

        assert entry["score"] is not None
        assert isinstance(entry["score"], int)

    def test_a_sparse_capture_scores_on_what_it_has(self):
        """Unknowns where the lane or the windows were not said. That is the
        honest answer and it shows on the card as such."""
        record = opportunity.capture(
            {"origin": "Ocala FL", "destination": "Macon GA", "rate": 900},
            driver="mike", channel="VOICE",
        )
        entry = opportunity_card.from_capture(record)

        assert entry["score"] is not None
        assert entry.get("position_impact")

    def test_scoring_never_costs_the_card(self, monkeypatch):
        """A capture that reached a screen beats a capture held back for want
        of a number."""
        import dispatch.scoring as scoring

        monkeypatch.setattr(
            scoring, "score_load",
            lambda load, **kw: (_ for _ in ()).throw(RuntimeError("engine down")))

        record = _capture()
        entry = opportunity_card.from_capture(record)

        assert entry is not None
        assert entry["score"] is None
