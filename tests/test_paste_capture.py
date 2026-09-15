"""Paste a load: a board listing or a broker's offer email becomes a card.

CO-2, 2026-09-14. The Owner's must-have: *"A rapid way to capture load
information for later decision making."* These hold three things shut:

  * the reader is deterministic, reads only what was pasted, and invents nothing;
  * a paste reaches a card through the capture contract's own function, the way
    the Loads screen does it (THE TEST REALITY RULE);
  * a paste the contract cannot log is refused with what was read, and stores
    nothing.
"""

from __future__ import annotations

import pathlib

import pytest

from dispatch import listing, mission_template as mt, opportunity
from dispatch.db import set_db_path
from portal.models import sandbox

BOARD_ROW = """Jacksonville, FL 32218  ->  Atlanta, GA 30301
09/15 08:00   09/16 14:00
Dry Van  53'   42,000 lbs   345 mi
$1,250   ($3.62/mi)
Southeast Freight Partners  (904) 555-0142
Ref: SFP-88213"""

LABELLED = """Origin: Savannah, GA
Destination: Charlotte, NC
Pickup Date: Thursday 6am
Rate: $980
Equipment: Reefer
Weight: 38000
Load #: 55123"""

OFFER_EMAIL = """From: Dana Ruiz <dana@example-logistics.com>
To: ops@example.com
Subject: Load offer Tampa, FL to Orlando, FL

Hi Mike, we have 12 pallets, 9,800 lbs ready 9/18, deliver 9/18 by 3pm.
Paying $650 flat. Call me at 813-555-0199.
"""


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
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


class TestTheReader:
    def test_a_board_row_without_labels(self):
        read = listing.parse_listing(BOARD_ROW)
        assert read["fields"]["origin"] == "Jacksonville, FL"
        assert read["fields"]["destination"] == "Atlanta, GA"
        assert read["fields"]["rate"] == 1250.0
        assert read["fields"]["equipment"] == "Dry Van"
        assert read["fields"]["pickup_date"] == "09/15 08:00"
        assert read["fields"]["delivery_date"] == "09/16 14:00"
        extras = read["card_extras"]
        assert extras["distance_miles"] == 345.0
        assert extras["weight_lbs"] == 42000
        assert extras["rpm"] == 3.62
        # D8: the customer's own number travels to the card.
        assert extras["load_id"] == "SFP-88213"
        assert read["key_missing"] == [] and read["nothing_read"] is False

    def test_a_per_mile_figure_is_never_the_rate(self):
        read = listing.parse_listing("Tampa, FL to Miami, FL\nRate: $2.75/mi\n280 miles")
        assert "rate" not in read["fields"]
        assert read["card_extras"]["rpm"] == 2.75
        # Reported for the card, no longer a reason to refuse (Owner ruling 2026-09-15).
        assert read["key_missing"] == ["rate"] and read["nothing_read"] is False

    def test_text_with_nothing_in_it_is_nothing_read(self):
        read = listing.parse_listing("Hello, call me when you can.")
        assert read["fields"] == {} and read["nothing_read"] is True

    def test_labelled_fields(self):
        read = listing.parse_listing(LABELLED)
        assert read["fields"]["origin"] == "Savannah, GA"
        assert read["fields"]["destination"] == "Charlotte, NC"
        assert read["fields"]["pickup_date"] == "Thursday 6am"
        assert read["fields"]["equipment"] == "Reefer"
        assert read["card_extras"]["weight_lbs"] == 38000
        assert read["card_extras"]["load_id"] == "55123"
        assert "delivery date" in read["missing"]
        assert "miles" in read["missing"]

    def test_nothing_is_invented(self):
        """A load number is only ever taken from a labelled field. A number the
        reader guessed would be neither the customer's nor Publisher's (D8)."""
        read = listing.parse_listing("Ocala, FL to Macon, GA $900 order 4471")
        assert "load_id" not in read["card_extras"]
        assert "pickup_date" not in read["fields"]
        assert "customer" in read["missing"]

    def test_email_headers_are_not_a_lane(self):
        read = listing.parse_listing(OFFER_EMAIL)
        assert read["fields"]["origin"] == "Tampa, FL"
        assert read["fields"]["destination"] == "Orlando, FL"
        assert read["fields"]["rate"] == 650.0
        assert read["card_extras"]["broker_email"] == "dana@example-logistics.com"
        assert read["card_extras"]["broker_phone"] == "813-555-0199"

    def test_it_reads_the_clipboard_and_nothing_else(self):
        """D1: no scraping or session tooling of any kind. The reader imports
        nothing that could reach a network."""
        source = pathlib.Path("dispatch/listing.py").read_text(encoding="utf-8")
        for module in ("urllib", "requests", "socket", "http.client", "selenium",
                       "imaplib", "poplib"):
            assert "import %s" % module not in source
            assert "from %s" % module not in source


class TestOfferEmail:
    def test_a_reply_on_the_mission_template_is_read_by_the_template(self):
        values = dict(mt.blank_template(), customer="Coastal Brokerage",
                      pickup_location="Jacksonville, FL", pickup_window="9/21 07:00",
                      delivery_location="Valdosta, GA", delivery_window="9/21 13:00",
                      rate="$720", load_number="CB-5521", commodity="Paper goods")
        body = mt.render_email(values) + "\n" + mt.render_stop_block(
            2, {"facility": "Tifton, GA", "window": "9/21 15:00"})
        read = listing.parse_offer_email(body)
        assert read["fields"]["origin"] == "Jacksonville, FL"
        assert read["fields"]["destination"] == "Valdosta, GA"
        assert read["fields"]["rate"] == 720.0
        assert read["fields"]["contact"] == "Coastal Brokerage"
        assert read["card_extras"]["load_id"] == "CB-5521"
        assert "Stop 2: Tifton, GA" in read["fields"]["notes"]

    def test_a_plain_email_falls_back_to_the_listing_reader(self):
        read = listing.parse_offer_email(OFFER_EMAIL)
        assert read["fields"]["rate"] == 650.0
        assert read["fields"]["pieces_weight"].startswith("12 pallets")


class TestThroughTheLoadsScreen:
    def test_a_pasted_listing_becomes_a_card(self, client):
        resp = client.post("/loads/paste", data={"pasted": BOARD_ROW, "kind": "listing"})
        assert resp.status_code == 302

        cards = [e for e in sandbox.get_all().values() if e["source_type"] == "dispatch"]
        assert len(cards) == 1
        card = cards[0]["card_data"]
        assert card["origin"] == "Jacksonville, FL"
        assert card["distance_miles"] == 345.0
        assert card["load_id"] == "SFP-88213"
        assert card["captured_via"] == "MISSIONSCREEN"

        # The contract's own store holds the capture, as a voice capture would.
        rows = opportunity.all_open()
        assert len(rows) == 1 and rows[0]["captured_via"] == "MISSIONSCREEN"

        page = client.get("/loads").get_data(as_text=True)
        assert "Card made: Jacksonville, FL to Atlanta, GA" in page
        assert "Still missing: customer" in page
        assert "SFP-88213" in page

    def test_the_same_listing_pasted_twice_is_one_card(self, client):
        client.post("/loads/paste", data={"pasted": BOARD_ROW})
        client.post("/loads/paste", data={"pasted": BOARD_ROW})
        cards = [e for e in sandbox.get_all().values() if e["source_type"] == "dispatch"]
        assert len(cards) == 1

    def test_a_paste_without_a_rate_is_logged_with_the_rate_pending(self, client):
        """Was: stores nothing and asks for the rate. **Owner ruling, 2026-09-15:**
        *"holding a load with out a rate will need an astric or blank is not
        negative."* The card is made, the rate shows "*", and the score is read
        against the maximum without the rate."""
        resp = client.post("/loads/paste",
                           data={"pasted": "Tampa, FL to Miami, FL\n280 miles"})
        assert resp.status_code == 302
        cards = [e for e in sandbox.get_all().values() if e["source_type"] == "dispatch"]
        assert len(cards) == 1
        card = cards[0]["card_data"]
        assert card["origin"] == "Tampa, FL" and "rate" not in card
        assert card["rate_pending"] is True
        assert opportunity.all_open()[0]["rate"] is None
        page = client.get("/loads").get_data(as_text=True)
        assert "Card made: Tampa, FL to Miami, FL, * rate pending." in page
        assert "* Rate pending" in page
        assert "Needs rate" not in page

    def test_a_paste_without_a_lane_is_logged_with_what_was_read(self, client):
        """Ruling "1a": no city, and what was read is still saved."""
        resp = client.post("/loads/paste", data={"pasted": "Rate: $1,400\nEquipment: Reefer"})
        assert resp.status_code == 302
        record = opportunity.all_open()[0]
        assert record["rate"] == 1400.0 and record["origin"] == "" and record["destination"] == ""
        assert "Card made: no city read, $1400." in client.get("/loads").get_data(as_text=True)

    def test_a_paste_with_nothing_readable_stores_nothing(self, client):
        resp = client.post("/loads/paste", data={"pasted": "Hello, call me when you can."})
        assert resp.status_code == 400
        assert "Nothing readable" in resp.get_data(as_text=True)
        assert sandbox.get_all() == {}
        assert opportunity.all_open() == []

    def test_what_he_types_wins_and_logs_it(self, client):
        resp = client.post("/loads/paste", data={
            "pasted": "Tampa, FL to Miami, FL\n280 miles", "rate": "900",
            "distance_miles": "281"})
        assert resp.status_code == 302
        card = next(iter(sandbox.get_all().values()))["card_data"]
        assert card["rate"] == 900.0
        assert card["distance_miles"] == 281.0

    def test_an_offer_email_becomes_a_card(self, client):
        resp = client.post("/loads/paste", data={"pasted": OFFER_EMAIL, "kind": "email"})
        assert resp.status_code == 302
        card = next(iter(sandbox.get_all().values()))["card_data"]
        assert card["origin"] == "Tampa, FL"
        assert card["broker_email"] == "dana@example-logistics.com"

    def test_an_empty_paste_says_so(self, client):
        resp = client.post("/loads/paste", data={"pasted": "  "})
        assert resp.status_code == 302
        assert "Nothing was pasted." in client.get("/loads").get_data(as_text=True)
