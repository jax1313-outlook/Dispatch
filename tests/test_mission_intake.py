"""One Mission Template, many intake methods, one Mission Record.

The temptation with manual entry is always a lighter path -- a quicker form,
fewer fields, "it is only a phone load". What that produces is two kinds of
load, two sets of rules, and a record that means different things depending on
how it arrived.

So the tests that matter here are equivalence tests: a load emailed in and a
load read to JOE must produce the same record, numbered the same way, as a load
SWEEP found.
"""

from __future__ import annotations

import pytest

from dispatch import mission, mission_template as mt
from portal.models import sandbox


COMPLETE = {
    "broker": "Southeast Freight Partners",
    "load_number": "847261",
    "broker_poc": "D. Reyes",
    "broker_phone": "904-555-0199",
    "rate": "1150",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-02 06:00 - 10:00",
    "pickup_contact": "Gate 2 - T. Alvarez",
    "pickup_phone": "904-555-0188",
    "pickup_notes": "Check in at guard shack",
    "delivery_location": "Atlanta, GA 30336",
    "delivery_window": "2026-09-02 15:00 - 17:00",
    "delivery_contact": "Dock 4 - K. Mills",
    "delivery_phone": "770-555-0142",
    "delivery_notes": "Dock 4 after 06:00",
    "commodity": "Aviation parts",
    "pallets": "4",
    "pieces": "4",
    "weight_lbs": "8400",
}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    yield


class TestOneTemplate:
    def test_both_methods_read_the_same_template(self):
        """Not two forms that drift apart at the second revision."""
        email_keys = set(mt.parse_email(mt.render_email()))
        voice_keys = {p["key"] for p in mt.voice_script()}
        assert email_keys == voice_keys == set(mt.TEMPLATE_KEYS)

    def test_the_template_matches_what_the_cockpit_shows(self):
        """Intake and display agree, or a phoned-in load renders with holes a
        swept one does not have."""
        for key in ("broker", "pickup_location", "pickup_window", "pickup_contact",
                    "pickup_phone", "pickup_notes", "delivery_location",
                    "delivery_window", "delivery_contact", "delivery_phone",
                    "delivery_notes", "commodity"):
            assert key in mt.TEMPLATE_KEYS, key

    def test_the_voice_script_asks_in_words(self):
        """A template read aloud badly is a template nobody finishes."""
        for prompt in mt.voice_script():
            assert prompt["prompt"].endswith("?")


class TestTheEmailRoundTrip:
    def test_a_completed_template_parses_back(self):
        parsed = mt.parse_email(mt.render_email(COMPLETE))
        assert parsed["broker"] == COMPLETE["broker"]
        assert parsed["load_number"] == "847261"
        assert mt.validate(parsed) == []

    def test_it_survives_what_a_phone_does_to_an_email(self):
        """Reply markers and stray blank lines are normal, not an error."""
        body = "\n".join("> " + line for line in mt.render_email(COMPLETE).splitlines())
        parsed = mt.parse_email(body + "\n\n\nSent from my phone\n")
        assert parsed["load_number"] == "847261"
        assert mt.validate(parsed) == []

    def test_it_invents_nothing_it_could_not_find(self):
        parsed = mt.parse_email("Broker: Someone\n")
        assert parsed["commodity"] == ""
        assert parsed["pickup_location"] == ""

    def test_the_subject_token_is_on_the_template(self):
        """It is what COMI watches for."""
        assert mt.INTAKE_SUBJECT_TOKEN in mt.render_email()
        assert mt.INTAKE_MAILBOX in mt.render_email()


class TestItRefusesAnIncompleteLoad:
    def test_every_problem_is_reported_not_the_first(self):
        problems = mt.validate({"broker": "Someone"})
        assert len(problems) >= 4

    def test_a_non_numeric_weight_is_refused(self):
        values = dict(COMPLETE, weight_lbs="heavy")
        assert any("weight" in p for p in mt.validate(values))

    def test_an_incomplete_template_creates_nothing(self):
        with pytest.raises(mt.TemplateError):
            mt.to_record({"broker": "Someone"}, source=mt.SOURCE_EMAIL)


class TestTheRecordIsTheSameWhateverBroughtItIn:
    def _create(self, source):
        return mt.create_mission(COMPLETE, source=source, taken_by="Mike",
                                 sandbox_module=sandbox, mission_module=mission)

    def test_email_and_voice_produce_the_same_freight(self):
        """The load is the load. Only how it arrived may differ."""
        by_email = self._create(mt.SOURCE_EMAIL)
        by_voice = self._create(mt.SOURCE_VOICE)

        provenance = {"id", "created_at", "updated_at", "events", "source_id",
                      "mission_number", "intake_source", "summary"}
        assert ({k: v for k, v in by_email.items() if k not in provenance}
                != {}) # sanity: there is something to compare

        email_card = {k: v for k, v in by_email["card_data"].items() if k != "source"}
        voice_card = {k: v for k, v in by_voice["card_data"].items() if k != "source"}
        assert email_card == voice_card

        rest = provenance | {"card_data"}
        assert ({k: v for k, v in by_email.items() if k not in rest}
                == {k: v for k, v in by_voice.items() if k not in rest})

    def test_only_the_provenance_differs(self):
        """And it differs on purpose: who told us about this load matters."""
        by_email = self._create(mt.SOURCE_EMAIL)
        by_voice = self._create(mt.SOURCE_VOICE)
        assert by_email["card_data"]["source"] == "email"
        assert by_voice["card_data"]["source"] == "voice"

    def test_the_brokers_load_number_is_preserved_exactly(self):
        record = self._create(mt.SOURCE_VOICE)
        assert record["card_data"]["load_id"] == "847261"

    def test_dispatch_assigns_the_mission_number(self):
        """Same numbering as a swept mission. Not a second scheme."""
        record = self._create(mt.SOURCE_EMAIL)
        assert record["mission_number"] == 1
        second = self._create(mt.SOURCE_VOICE)
        assert second["mission_number"] == 2

    def test_the_record_says_how_it_arrived(self):
        """Who told us about this load is a real question later."""
        assert self._create(mt.SOURCE_VOICE)["intake_source"] == "VOICE"

    def test_it_records_who_took_it(self):
        assert self._create(mt.SOURCE_EMAIL)["intake_taken_by"] == "Mike"

    def test_it_refuses_to_create_without_who_took_it(self):
        """A mission arrives on somebody's word. The record says whose."""
        with pytest.raises(mt.TemplateError, match="who took it"):
            mt.create_mission(COMPLETE, source=mt.SOURCE_VOICE, taken_by="",
                              sandbox_module=sandbox, mission_module=mission)

    def test_an_unknown_source_is_refused(self):
        with pytest.raises(mt.TemplateError, match="Unknown intake source"):
            mt.to_record(COMPLETE, source="TELEPATHY")


class TestTheCockpitCanReadWhatIntakeWrote:
    """The proof that the two halves agree."""

    def test_a_manually_created_mission_renders(self):
        from portal import cockpit

        record = mt.create_mission(COMPLETE, source=mt.SOURCE_VOICE, taken_by="Mike",
                                   sandbox_module=sandbox, mission_module=mission)
        record["numbers"] = mission.display_numbers(record)
        context = cockpit.cockpit_context(record, cockpit.MODE_PICKUP)

        assert context["ends"]["pickup"]["place"] == "Jacksonville, FL 32202"
        assert context["ends"]["delivery"]["place"] == "Atlanta, GA 30336"
        assert "Aviation parts" in context["cargo"]["description"]
        assert context["broker"]["name"] == "Southeast Freight Partners"

    def test_the_pickup_panel_has_no_holes(self):
        from portal import cockpit

        record = mt.create_mission(COMPLETE, source=mt.SOURCE_EMAIL, taken_by="Mike",
                                   sandbox_module=sandbox, mission_module=mission)
        record["numbers"] = mission.display_numbers(record)
        detail = cockpit.end_detail(record, "pickup")
        for field in ("address", "poc", "phone", "appointment", "instructions"):
            assert detail[field] != "—", field
