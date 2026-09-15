"""The Mission BRIEF: the whole record on one sheet, before the call.

    Show me the whole mission. Show me what is missing. Let me write it in.
    Let me print it.

This is the SAM Brief, rediscovered. It answers *should I run this mission and
what do I still need to ask*, which is a different question from the cockpit's
*how do I run it*, and it is asked at a desk with a phone in hand.

    Empty is not a negative. It is empty. Move on.

An empty field is pale red and nothing else happens: no score, no completeness
percentage, no required-field logic, no block. The colour exists so a man on
the phone can see what is still worth asking while he already has somebody on
the line.
"""

from __future__ import annotations

import pytest

from dispatch import mission_template as mt
from portal import brief
from portal.models import sandbox


RECORD = {
    "id": "SBX-BRIEF-1",
    "load_number": "ROC-2026-884471",
    "mission_number": 2,
    "customer": "Mayo Clinic",
    "card_data": {"load_id": "ROC-2026-884471", "broker": "XPO Logistics",
                  "origin": "XPO Logistics, Savannah, GA",
                  "destination": "Mayo Clinic, San Pablo Rd, Jacksonville, FL"},
    "load_control": {"control_name": "Mayo Clinic Dispatch",
                     "control_role": "CUSTOMER",
                     "control_phone": "904-956-3200",
                     "control_email": "dispatch@example.test"},
    "cargo_items": [{"description": "Surgical equipment", "pallets": 1,
                     "weight_each": 1800}],
    "stops": [{"number": 1, "label": "STOP 1", "facility": "Mayo Clinic",
               "window": "2026-09-02 12:00"}],
}


class TestItShowsTheWholeRecord:
    def test_it_is_built_from_the_mission_template(self):
        """A brief with its own field list drifts from intake by the second
        revision. **Exactly** the template since the one-page layout,
        2026-09-15: nothing added, nothing left out, in its order."""
        shown = [(f["key"], f["label"]) for s in brief.sections_of(RECORD)
                 for f in s["fields"]]
        assert shown == [(f.key, f.label) for f in mt.TEMPLATE]

    def test_the_sections_are_the_operators(self):
        titles = [s["title"] for s in brief.sections_of(RECORD)]
        assert titles == list(mt.SECTIONS)
        assert titles[0] == "IDENTITY"

    def test_stops_no_longer_show_load_control(self):
        """Stop 1 load control left the template on 2026-09-15, and with it the
        stop-level load control lines."""
        stops = brief.stops_of(RECORD)
        labels = [f["label"] for f in stops[0]["fields"]]
        assert labels == ["Facility", "Appointment", "Dock contact", "Dock phone",
                          "Access instructions", "SPECIAL INSTRUCTIONS"]


class TestItFindsValuesWhereverTheyLive:
    """The bug this class exists for.

    An earlier resolver mixed field keys and pre-resolved values in one list
    and told them apart by asking whether they were strings. A resolved value
    is a string too, so it looked up record["Mayo Clinic Dispatch"] and drew
    load control as empty on a record that had it -- which would send a man to
    ask a broker for a number already written down.
    """

    def _value(self, key):
        for section in brief.sections_of(RECORD):
            for field in section["fields"]:
                if field["key"] == key:
                    return field["value"]
        raise AssertionError("no field for %s" % key)

    def test_the_mission_number_is_read_from_the_record(self):
        assert self._value("mission_number") == "2"

    def test_the_load_control_pick_is_read_from_the_record(self):
        record = dict(RECORD, controlled_by="Customer")
        value = [f["value"] for s in brief.sections_of(record)
                 for f in s["fields"] if f["key"] == "controlled_by"]
        assert value == ["Customer"]

    def test_an_older_load_control_block_is_not_shown(self):
        """The stop-level detail an older record stored is not the two-choice
        pick, and is not dressed up as one."""
        assert self._value("controlled_by") == ""
        values = [f["value"] for s in brief.sections_of(RECORD) for f in s["fields"]]
        values += [f["value"] for st in brief.stops_of(RECORD) for f in st["fields"]]
        for stored in ("Mayo Clinic Dispatch", "904-956-3200", "dispatch@example.test"):
            assert stored not in values

    def test_an_email_a_paste_filed_on_the_card_is_their_email(self):
        record = dict(RECORD, card_data=dict(RECORD["card_data"],
                                             broker_email="ops@xpo.example"))
        value = [f["value"] for s in brief.sections_of(record)
                 for f in s["fields"] if f["key"] == "customer_email"]
        assert value == ["ops@xpo.example"]

    def test_the_card_is_read_when_the_flat_field_is_absent(self):
        assert self._value("pickup_location") == "XPO Logistics, Savannah, GA"

    def test_the_flat_field_wins_over_the_card(self):
        """Intake wrote the flat field. It is the more recent truth."""
        record = dict(RECORD, pickup_location="Corrected address")
        for section in brief.sections_of(record):
            for field in section["fields"]:
                if field["key"] == "pickup_location":
                    assert field["value"] == "Corrected address"

    def test_itemised_cargo_is_no_longer_shown(self):
        """Cargo items left the template on 2026-09-15."""
        card = brief.card_for(RECORD)
        assert "cargo" not in card
        assert all("Surgical equipment" not in f["value"]
                   for s in card["sections"] for f in s["fields"])

    def test_older_pallets_and_pieces_read_under_the_merged_field(self):
        """*"cargo: 1) Description 2) Pieces / Pallets/ 3) Weight"*. A record
        written with the two separate counts shows them together, unchanged."""
        record = dict(RECORD, card_data=dict(RECORD["card_data"], pallets=4,
                                             pieces=20))
        value = [f["value"] for s in brief.sections_of(record)
                 for f in s["fields"] if f["key"] == "pieces_pallets"]
        assert value == ["4 pallets / 20 pieces"]
        assert record["card_data"]["pallets"] == 4
        assert "pieces_pallets" not in record

    def test_the_merged_field_wins_once_written(self):
        record = dict(RECORD, pieces_pallets="6 skids", pallets=4)
        value = [f["value"] for s in brief.sections_of(record)
                 for f in s["fields"] if f["key"] == "pieces_pallets"]
        assert value == ["6 skids"]


class TestEmptyIsNotANegative:
    def test_an_empty_field_is_marked_and_nothing_else(self):
        field = [f for s in brief.sections_of(RECORD) for f in s["fields"]
                 if f["key"] == "pickup_phone"][0]
        assert field["empty"] is True
        assert field["value"] == ""

    def test_there_is_no_score_and_no_required_flag(self):
        card = brief.card_for(RECORD)
        assert "score" not in card
        assert "complete" not in card
        assert "required" not in card
        for section in card["sections"]:
            for field in section["fields"]:
                assert "required" not in field

    def test_the_count_includes_every_highlighted_field(self):
        """The headline counting fewer than the page shows is the kind of
        small lie that stops a man trusting the number."""
        card = brief.card_for(RECORD)
        shown = sum(1 for s in card["sections"] for f in s["fields"] if f["empty"])
        shown += sum(1 for st in card["stops"] for f in st["fields"] if f["empty"])
        assert card["empty_count"] == shown

    def test_a_full_record_counts_none(self):
        """Including the fields the card carries beyond the intake template --
        identity, and the addresses the template does not ask for."""
        filled = dict(RECORD, stops=[], status="ACCEPTED", intake_source="JOE",
                      intake_taken_by="Mike", customer_email="a@b.test")
        for field in mt.TEMPLATE:
            filled[field.key] = "x"
        card = brief.card_for(filled)
        still_empty = [f["label"] for s in card["sections"]
                       for f in s["fields"] if f["empty"]]
        assert still_empty == [], still_empty
        assert card["empty_count"] == 0


class TestBriefEditAndPrint:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        yield

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    @pytest.fixture()
    def mission(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="BRIEF-1", title="Brief probe",
            card_data={"load_id": "BRIEF-1"}, summary="")
        return entry["id"]

    def test_the_brief_renders(self, client, mission):
        html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        assert "MISSION BRIEF" in html
        assert "PRINT" in html and "EDIT" in html

    def test_edit_turns_fields_into_inputs(self, client, mission):
        plain = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        editing = client.get(f"/brief/mission/{mission}?edit=1").get_data(as_text=True)
        assert plain.count("<input") < editing.count("<input")

    def test_writing_in_what_the_broker_said(self, client, mission):
        client.post(f"/brief/mission/{mission}/save",
                    data={"customer_poc": "D. Reyes",
                          "customer_phone": "904-555-0199"})
        record = sandbox.get(mission)
        assert record["customer_poc"] == "D. Reyes"
        assert record["customer_phone"] == "904-555-0199"

    def test_load_control_is_written_as_the_pick(self, client, mission):
        client.post(f"/brief/mission/{mission}/save",
                    data={"controlled_by": "Level 1"})
        assert sandbox.get(mission)["controlled_by"] == "Level 1"

    def test_a_removed_load_control_field_is_no_longer_written(self, client, mission):
        """Load control name and phone left the template on 2026-09-15."""
        client.post(f"/brief/mission/{mission}/save",
                    data={"control_name": "Gulf Coast Paper",
                          "control_phone": "813-555-0177"})
        record = sandbox.get(mission)
        assert "control_name" not in record and "control_phone" not in record
        assert not (record.get("load_control") or {}).get("control_name")

    def test_the_mission_number_is_not_written_from_the_brief(self, client, mission):
        """Dispatch assigns it."""
        client.post(f"/brief/mission/{mission}/save", data={"mission_number": "999"})
        assert sandbox.get(mission).get("mission_number") != "999"

    def test_nothing_it_was_not_given_is_touched(self, client, mission):
        client.post(f"/brief/mission/{mission}/save", data={"customer_poc": "A"})
        client.post(f"/brief/mission/{mission}/save", data={"customer_phone": "B"})
        record = sandbox.get(mission)
        assert record["customer_poc"] == "A"
        assert record["customer_phone"] == "B"

    def test_it_does_not_validate_what_the_broker_said(self, client, mission):
        """A brief that argues with what a broker just said on the phone is a
        brief he stops using."""
        client.post(f"/brief/mission/{mission}/save",
                    data={"weight_lbs": "about five thousand"})
        assert sandbox.get(mission)["weight_lbs"] == "about five thousand"

    def test_the_load_number_is_not_editable(self, client, mission):
        """Changed after it has been quoted to a broker is how a payment goes
        missing."""
        assert "load_number" in brief.editable_keys({})
        html = client.get(f"/brief/mission/{mission}?edit=1").get_data(as_text=True)
        identity = html[html.index("<h2>IDENTITY</h2>"):html.index("<h2>MISSION SOURCE</h2>")]
        assert 'name="load_number"' not in identity
        assert 'name="mission_number"' not in identity
        # Service Type sits in IDENTITY now, and is still his to pick.
        assert '<select name="service">' in identity

    def test_an_unknown_mission_briefs_nothing(self, client):
        assert client.get("/brief/mission/NOPE").status_code == 302


class TestTheOnePageBriefThroughItsRoute:
    """The brief as the screen serves it, since the one-page layout of
    2026-09-15 -- *"go ahead with the one page template"*."""

    OLDER = {
        # A record written before the one-page layout, carrying every field
        # the layout removed.
        "load_number": "LOAD-20260729-001",
        "mission_number": 4,
        "status": "OPEN",
        "intake_source": "JOE",
        "intake_taken_by": "Mike",
        "customer": "Southeast Freight Partners",
        "customer_phone": "904-555-0142",
        "service": "Medical",
        "pickup_shipper": "Gulf Coast Paper Mill",
        "pickup_location": "Jacksonville, FL 32202",
        "pickup_window": "2026-07-30 06:00 - 10:00",
        "delivery_location": "Savannah, GA 31401",
        "delivery_window": "2026-07-30 14:00 - 18:00",
        "commodity": "Paper rolls",
        "weight_lbs": "38000",
        "load_control": {"control_name": "Regional Dispatch Desk",
                         "control_role": "BROKER",
                         "control_phone": "904-555-0111",
                         "control_email": "desk@example.test"},
        "cargo_items": [{"description": "Kraft liner", "pallets": 2,
                         "weight_each": 1900}],
        "stops": [{"number": 1, "label": "STOP 1", "facility": "Savannah, GA 31401",
                   "control_name": "Harbor Receiving Office",
                   "control_ref": "HRO-5521"}],
        "card_data": {"load_id": "LOAD-20260729-001", "pallets": 4, "pieces": 12},
    }

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        yield

    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def _store_older(self):
        import copy

        entry = sandbox.create_entry(
            source_type="dispatch", source_id="OLDER-1", title="Older record",
            card_data=copy.deepcopy(self.OLDER["card_data"]), summary="")
        data = sandbox._load()
        stored = data[entry["id"]]
        for key, value in copy.deepcopy(self.OLDER).items():
            if key != "card_data":
                stored[key] = value
        data[entry["id"]] = stored
        sandbox._save(data)
        return entry["id"]

    def test_the_brief_shows_no_status_intake_or_taken_by(self, client):
        mission = self._store_older()
        html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        assert "MISSION BRIEF" in html
        for gone in (">Status<", ">Intake<", ">Taken by<"):
            assert gone not in html, gone

    def test_the_brief_shows_no_removed_field(self, client):
        mission = self._store_older()
        for url in (f"/brief/mission/{mission}", f"/brief/mission/{mission}?edit=1"):
            html = client.get(url).get_data(as_text=True)
            for label in ("Load number (theirs)", "Load control is the",
                          "Load control phone", "Load control email",
                          ">Shipper<", "Stop 1 load control", "Cargo items",
                          "CARGO ITEMS", "Pallets (total)", ">Pieces<",
                          "Amount to collect", "Their reference"):
                assert label not in html, (url, label)
            for stored in ("Gulf Coast Paper Mill", "Regional Dispatch Desk",
                           "904-555-0111", "desk@example.test", "Kraft liner",
                           "Harbor Receiving Office", "HRO-5521", "Mike", "OPEN"):
                assert stored not in html, (url, stored)

    def test_the_brief_shows_exactly_the_twenty_nine_labels(self, client):
        import re

        mission = self._store_older()
        html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        body = html[html.index("<h2>IDENTITY</h2>"):html.index("<h2>STOPS</h2>")]
        labels = [re.sub(r"\s+", " ", l).strip()
                  for l in re.findall(r"<dt[^>]*>(.*?)</dt>", body, re.S)]
        assert labels == [f.label for f in mt.TEMPLATE]

    def test_an_older_record_loads_renders_and_keeps_every_stored_value(self, client):
        mission = self._store_older()
        before = sandbox.get(mission)

        brief_html = client.get(f"/brief/mission/{mission}").get_data(as_text=True)
        assert "Southeast Freight Partners" in brief_html
        assert "4 pallets / 12 pieces" in brief_html
        # An older service type outside LTL / Courier is shown as stored ...
        assert "Medical" in brief_html
        # ... and kept selected, not silently replaced, when the brief is edited.
        editing = client.get(f"/brief/mission/{mission}?edit=1").get_data(as_text=True)
        assert '<option value="Medical" selected>' in editing

        cockpit = client.get(f"/portal/mission/{mission}?view=DELIVERY")
        assert cockpit.status_code == 200
        cockpit_html = cockpit.get_data(as_text=True)
        assert "Savannah, GA 31401" in cockpit_html
        for stored in ("Regional Dispatch Desk", "Harbor Receiving Office", "HRO-5521"):
            assert stored not in cockpit_html, stored

        after = sandbox.get(mission)
        for key in ("status", "intake_source", "intake_taken_by", "pickup_shipper",
                    "load_control", "cargo_items", "stops", "service"):
            assert after[key] == before[key], key
        assert after["card_data"]["pallets"] == 4
        assert after["card_data"]["pieces"] == 12

    def test_saving_the_brief_leaves_removed_values_untouched(self, client):
        mission = self._store_older()
        client.post(f"/brief/mission/{mission}/save",
                    data={"customer_poc": "D. Reyes", "service": "Medical"})
        after = sandbox.get(mission)
        assert after["customer_poc"] == "D. Reyes"
        assert after["pickup_shipper"] == "Gulf Coast Paper Mill"
        assert after["load_control"] == self.OLDER["load_control"]
        assert after["cargo_items"] == self.OLDER["cargo_items"]
        assert after["intake_taken_by"] == "Mike"
        assert after["stops"][0]["control_ref"] == "HRO-5521"
