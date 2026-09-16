"""JOE takes the message. Publisher makes the change.

    Mike -> JOE -> Publisher -> Dispatch -> Mission Record

The temptation was `Mike -> JOE -> Mission Record`, which quietly makes JOE the
owner of mission data. He is a co-driver and a communication layer: he hears
what was said, works out which field it belongs to, and hands it over.
Publisher is the production clerk and performs the change; Dispatch owns the
record.

The tests that matter are the ones about who is allowed to write, because that
is the boundary that erodes first.
"""

from __future__ import annotations

import pytest

from dispatch import joe_update as joe
from portal.models import publisher, sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def mission():
    entry = sandbox.create_entry(
        source_type="dispatch", source_id="JOE-1", title="JOE probe",
        card_data={"load_id": "JOE-1"}, summary="")
    return entry["id"]


class TestJoeHasNoPen:
    """The boundary that erodes first."""

    def test_joe_cannot_reach_a_store(self):
        source = open("dispatch/joe_update.py", encoding="utf-8").read()
        for forbidden in ("sandbox", "_save", "_load(", "open("):
            assert forbidden not in source, forbidden

    def test_understanding_changes_nothing(self, mission):
        before = dict(sandbox.get(mission))
        joe.understand("broker email is sally@xpo.example")
        assert sandbox.get(mission) == before

    def test_publisher_is_the_one_that_writes(self):
        source = open("portal/models/publisher.py", encoding="utf-8").read()
        assert "def apply_mission_update(" in source
        assert "sandbox_module._save" in source


class TestWhatJoeHears:
    @pytest.mark.parametrize("said,field,value", [
        ("Joe, broker email is sally@xpo.example", "customer_email",
         "sally@xpo.example"),
        ("update pickup contact Fred Jones", "pickup_contact", "Fred Jones"),
        ("rate 950", "rate", "950"),
        ("broker phone 904-555-0199", "customer_phone", "904-555-0199"),
        ("load control is level 1", "controlled_by", "Level 1"),
        ("pallets 4 pallets / 20 pieces", "pieces_pallets", "4 pallets / 20 pieces"),
        ("shipper Southeast Freight", "customer", "Southeast Freight"),
        ("delivery appointment 2026-09-08 11:00", "delivery_window",
         "2026-09-08 11:00"),
        ("set cargo to Aviation parts", "commodity", "Aviation parts"),
    ])
    def test_it_places_what_a_driver_actually_says(self, said, field, value):
        heard = joe.understand(said)
        assert heard["understood"] is True
        assert heard["field"] == field
        assert heard["value"] == value

    def test_the_longer_phrase_wins(self):
        """'broker email' must not be read as 'broker'."""
        assert joe.understand("broker email a@b.test")["field"] == "customer_email"
        assert joe.understand("broker Southeast Freight")["field"] == "customer"

    def test_it_says_so_rather_than_guessing(self):
        """Writing a broker's email into the customer name because the
        sentence was ambiguous is worse than asking him to say it again."""
        heard = joe.understand("the weather is nice")
        assert heard["understood"] is False
        assert heard["field"] == ""
        assert heard["note"]

    def test_a_field_with_no_value_is_not_an_update(self):
        heard = joe.understand("broker email")
        assert heard["understood"] is False
        assert "no value" in heard["note"]

    def test_every_template_field_is_addressable(self):
        """**Since the labels were shortened, 2026-09-16:** a label used once is
        said on its own; one used in two or three places is said with its
        section in front of it -- "delivery phone", not "phone". The page has a
        heading above the field and speech has nothing, and writing a delivery
        phone into the pickup because the sentence was ambiguous is exactly what
        this module exists not to do."""
        from collections import Counter

        from dispatch import mission_template as mt

        shared = {label for label, n in
                  Counter(f.label.lower() for f in mt.TEMPLATE).items() if n > 1}
        prefix = {"MISSION SOURCE": "customer", "PICKUP": "pickup",
                  "DELIVERY": "delivery"}

        for field in mt.TEMPLATE:
            name = field.label
            if field.label.lower() in shared:
                name = "%s %s" % (prefix[field.section], field.label)
            said = "%s %s" % (name, field.choices[0] if field.choices
                              else "something")
            assert joe.understand(said)["field"] == field.key, name

    def test_a_shared_label_alone_is_not_guessed_at(self):
        """"Phone 904-555-0100" names three fields. JOE says so rather than
        picking one."""
        heard = joe.understand("phone 904-555-0100")
        assert heard["understood"] is False
        assert heard["field"] == ""

    def test_a_pick_list_field_takes_only_its_picks(self):
        """Load control is the Customer or Level 1 (2026-09-15). "Load control
        phone 904-956-3200" -- a field that left the template -- is not written
        into the pick as though it were one."""
        heard = joe.understand("load control phone 904-956-3200")
        assert heard["understood"] is False
        assert "Customer or Level 1" in heard["note"]
        assert joe.understand("service type courier")["value"] == "Courier"


class TestPublisherAppliesIt:
    def test_the_change_lands_on_the_record(self, mission):
        result = publisher.apply_mission_update(
            mission, "customer_phone", "904-555-0199",
            requested_by="Mike", sandbox_module=sandbox)
        assert result["applied"] is True
        assert sandbox.get(mission)["customer_phone"] == "904-555-0199"

    def test_load_control_is_written_as_the_pick(self, mission):
        """Where the brief and the cockpit read it since 2026-09-15."""
        publisher.apply_mission_update(
            mission, "controlled_by", "Customer",
            requested_by="Mike", sandbox_module=sandbox)
        assert sandbox.get(mission)["controlled_by"] == "Customer"

    def test_a_removed_load_control_field_is_refused(self, mission):
        """Load control phone and email left the template on 2026-09-15."""
        for field in ("control_phone", "control_email", "control_name"):
            result = publisher.apply_mission_update(
                mission, field, "904-956-3200",
                requested_by="Mike", sandbox_module=sandbox)
            assert result["applied"] is False, field
        assert "load_control" not in sandbox.get(mission)

    def test_the_mission_number_is_still_refused(self, mission):
        """It is on the template now, and still Dispatch's to assign."""
        result = publisher.apply_mission_update(
            mission, "mission_number", "999",
            requested_by="Mike", sandbox_module=sandbox)
        assert result["applied"] is False

    def test_it_keeps_what_was_there_before(self, mission):
        """A number corrected on a call is sometimes corrected wrongly, and the
        previous value is the cheapest way back."""
        publisher.apply_mission_update(mission, "rate", "950",
                                       requested_by="Mike", sandbox_module=sandbox)
        result = publisher.apply_mission_update(mission, "rate", "1050",
                                                requested_by="Mike",
                                                sandbox_module=sandbox)
        assert result["previous"] == "950"
        events = [e for e in sandbox.get(mission)["events"]
                  if e.get("action") == "field_updated"]
        assert events[-1]["from"] == "950" and events[-1]["to"] == "1050"

    def test_it_records_who_asked(self, mission):
        publisher.apply_mission_update(mission, "rate", "950",
                                       requested_by="Mike", sandbox_module=sandbox)
        event = [e for e in sandbox.get(mission)["events"]
                 if e.get("action") == "field_updated"][-1]
        assert event["requested_by"] == "Mike"
        assert event["via"] == "JOE"

    def test_it_will_not_change_without_knowing_whose_word(self, mission):
        result = publisher.apply_mission_update(
            mission, "rate", "950", requested_by="", sandbox_module=sandbox)
        assert result["applied"] is False

    @pytest.mark.parametrize("field", ["load_number", "mission_number",
                                       "committed_at", "id", "card_data"])
    def test_identity_and_the_gate_are_not_movable_by_a_sentence(self, mission,
                                                                 field):
        result = publisher.apply_mission_update(
            mission, field, "anything", requested_by="Mike",
            sandbox_module=sandbox)
        assert result["applied"] is False
        assert "not mine to change" in result["note"]

    def test_an_unknown_field_is_refused(self, mission):
        result = publisher.apply_mission_update(
            mission, "favourite_colour", "blue", requested_by="Mike",
            sandbox_module=sandbox)
        assert result["applied"] is False


class TestTheWholeHandover:
    def test_telling_joe_changes_the_record(self, client, mission):
        response = client.post(f"/joe/update/{mission}",
                               data={"said": "broker email is sally@xpo.example",
                                     "by": "Mike"})
        assert response.status_code == 200
        assert response.get_json()["applied"] is True
        assert sandbox.get(mission)["customer_email"] == "sally@xpo.example"

    def test_joe_says_back_what_changed_and_what_is_left(self, client, mission):
        """The gap count rides along because it is why he is doing this."""
        body = client.post(f"/joe/update/{mission}",
                           data={"said": "rate 950"}).get_json()
        assert "updated" in body["note"]
        assert "no entry" in body["note"]
        assert body["gaps"] > 0

    def test_something_he_could_not_place_changes_nothing(self, client, mission):
        before = dict(sandbox.get(mission))
        response = client.post(f"/joe/update/{mission}",
                               data={"said": "the weather is nice"})
        assert response.status_code == 400
        assert response.get_json()["applied"] is False
        assert sandbox.get(mission) == before

    def test_a_protected_field_is_refused_through_the_route_too(self, client,
                                                                mission):
        response = client.post(f"/joe/update/{mission}",
                               data={"said": "load number CVS-99999"})
        assert response.status_code == 400
        assert sandbox.get(mission).get("load_number") != "CVS-99999"

    def test_an_unknown_mission_changes_nothing(self, client):
        response = client.post("/joe/update/NOPE", data={"said": "rate 950"})
        assert response.status_code == 400
        assert sandbox.get("NOPE") is None

    def test_the_answer_is_in_the_drivers_words(self, client, mission):
        from portal import joe_voice

        body = client.post(f"/joe/update/{mission}",
                           data={"said": "rate 950"}).get_json()
        assert joe_voice.is_driver_safe(body["note"]) == []
