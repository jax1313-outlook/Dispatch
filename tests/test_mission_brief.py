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
        revision."""
        labels = {f["label"] for s in brief.sections_of(RECORD)
                  for f in s["fields"]}
        for field in mt.TEMPLATE:
            assert field.label in labels, field.key

    def test_the_sections_are_the_operators(self):
        titles = [s["title"] for s in brief.sections_of(RECORD)]
        assert titles == ["IDENTITY"] + list(mt.SECTIONS)

    def test_stops_carry_their_own_load_control(self):
        stops = brief.stops_of(RECORD)
        labels = {f["label"] for f in stops[0]["fields"]}
        assert "Load control" in labels
        assert "SPECIAL INSTRUCTIONS" in labels


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

    def test_load_control_is_read_from_its_own_block(self):
        assert self._value("control_name") == "Mayo Clinic Dispatch"
        assert self._value("control_phone") == "904-956-3200"

    def test_the_card_is_read_when_the_flat_field_is_absent(self):
        assert self._value("pickup_location") == "XPO Logistics, Savannah, GA"

    def test_the_flat_field_wins_over_the_card(self):
        """Intake wrote the flat field. It is the more recent truth."""
        record = dict(RECORD, pickup_location="Corrected address")
        for section in brief.sections_of(record):
            for field in section["fields"]:
                if field["key"] == "pickup_location":
                    assert field["value"] == "Corrected address"

    def test_itemised_cargo_appears(self):
        assert "Surgical equipment" in self._value("cargo_lines")


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

    def test_load_control_is_written_back_to_its_block(self, client, mission):
        client.post(f"/brief/mission/{mission}/save",
                    data={"control_name": "Gulf Coast Paper",
                          "control_phone": "813-555-0177"})
        control = sandbox.get(mission)["load_control"]
        assert control["control_name"] == "Gulf Coast Paper"
        assert control["control_phone"] == "813-555-0177"

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
        identity = html[html.index("IDENTITY"):html.index("MISSION SOURCE")]
        assert "<input" not in identity

    def test_an_unknown_mission_briefs_nothing(self, client):
        assert client.get("/brief/mission/NOPE").status_code == 302
