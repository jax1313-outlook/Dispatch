"""Saving the brief writes it down. It does not score the card again.

**Owner ruling, 2026-09-16:** *"why would i rescore if i saved a amount i agreed
to with broker. that would not make sense. just save and move on."*

This file exists to stop the fix that was briefly built and taken back out. The
argument for re-scoring sounded good -- a rate typed during a call is new
information, so read it -- and it was wrong about what the score is for. The
score ranks loads **he has not decided about yet**. By the time a rate is agreed
with a broker the decision is made; that card is going to COMMIT. Re-ranking a
load already taken is arithmetic nobody reads.

So: the sheet is where a call lands, and the engine is not consulted again.
"""

from __future__ import annotations

import pytest

from portal.models import opportunity_card as oc
from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _card(number: str, **extra) -> dict:
    capture = {
        "opportunity_id": number,
        "origin": "Jacksonville, FL",
        "destination": "Savannah, GA",
        "broker": "Probe Freight",
        "commodity": "Pallets",
        "pickup_window": "2026-10-01 08:00",
        "delivery_window": "2026-10-01 15:00",
    }
    capture.update(extra)
    return oc.from_capture(capture)


class TestEditAndSaveChangesTheCard:
    """The Owner's own workflow, asked as a question and answered by building it:
    *"i can open the LOADS screen move to the Load I just finished negociating
    and EDIIT and save this changes the card - Correct?"* Until 2026-09-16 the
    answer was no -- the rate went onto the record and the card kept reading what
    capture wrote, so Dispatch and Home still showed `Rate: *` on a load whose
    rate was agreed."""

    def test_the_rate_reaches_the_card(self, client):
        record = _card("CARD-1")
        assert not (sandbox.get(record["id"])["card_data"] or {}).get("rate")

        client.post("/brief/mission/%s/save" % record["id"], data={"rate": "1150"})

        assert sandbox.get(record["id"])["card_data"]["rate"] == "1150"

    def test_the_rate_pending_line_goes_with_it(self, client):
        """A card showing a rate and "* Rate pending" together tells a man two
        things at once."""
        record = _card("CARD-2")
        assert sandbox.get(record["id"])["card_data"]["rate_pending"] is True

        client.post("/brief/mission/%s/save" % record["id"], data={"rate": "1150"})

        card = sandbox.get(record["id"])["card_data"]
        assert card["rate_pending"] is False
        assert "rate_line" not in card

    def test_typed_miles_clear_the_miles_line(self, client):
        record = _card("CARD-3", origin="Ocala, FL", destination="Macon, GA")
        assert sandbox.get(record["id"])["card_data"]["miles_line"]

        client.post("/brief/mission/%s/save" % record["id"],
                    data={"distance_miles": "210"})

        assert "miles_line" not in sandbox.get(record["id"])["card_data"]

    def test_a_delivery_that_rolled_reaches_the_card(self, client):
        """Rolling is typing a new delivery appointment over the old one. The
        calendar and the cockpit read the card, so it has to land there."""
        record = _card("CARD-4")

        client.post("/brief/mission/%s/save" % record["id"],
                    data={"delivery_window": "2026-10-08 15:00"})

        assert (sandbox.get(record["id"])["card_data"]["delivery_window"]
                == "2026-10-08 15:00")


class TestTheSheetIsWrittenAndNothingIsRecomputed:
    def test_the_rate_is_stored_exactly_as_typed(self, client):
        """*"Values are stored exactly as typed and nothing is validated: a brief
        that argues with what a broker just said on the phone is a brief he stops
        using."*"""
        record = _card("SAVE-1")

        client.post("/brief/mission/%s/save" % record["id"], data={"rate": "1150"})

        assert sandbox.get(record["id"])["rate"] == "1150"

    def test_the_score_does_not_move(self, client):
        """The ruling. A load with an agreed rate is taken, not ranked."""
        record = _card("SAVE-2")
        before = sandbox.get(record["id"])["score"]

        client.post("/brief/mission/%s/save" % record["id"], data={"rate": "1150"})

        assert sandbox.get(record["id"])["score"] == before

    def test_nothing_re_scores_on_save(self):
        """Held by name as well as by behaviour, so the helper that was removed
        is not quietly reintroduced by a later pass over this route."""
        assert not hasattr(oc, "rescore_stored")

    def test_the_miles_a_card_was_scored_on_are_not_disturbed(self, client):
        """Writing the sheet through to the card must not become scoring by the
        back door: the engine's own inputs are left where it put them."""
        record = _card("SAVE-3")
        before = dict(sandbox.get(record["id"])["card_data"])

        client.post("/brief/mission/%s/save" % record["id"], data={"rate": "1150"})

        after = sandbox.get(record["id"])["card_data"]
        assert after["distance_miles"] == before["distance_miles"]
        assert after["origin"] == before["origin"]
