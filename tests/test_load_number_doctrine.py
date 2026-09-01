"""Every Mission Record has a Load Number. No exceptions. No orphans.

The Load Number is the retrieval key for the mission, the archive, the library,
document linkage, communication linkage and COMI processing. A record without
one exists and cannot be found again, which is the definition of an orphan.

Two origins, one field:

    Supplied     847261, CVS-44912, ABC123 -- stored byte for byte
    Generated    L1-0001 -- when nobody else numbered the work

A generated number is not pretending to be a broker number. It is a legitimate
Dispatch Load Number, and the record says which of the two it is -- because
"did they give us this, or did we" decides who it can be quoted to.
"""

from __future__ import annotations

import pytest

from dispatch import load_number as ln, mission, mission_template as mt
from portal.models import sandbox


MINIMUM = {
    "customer": "Baptist Health Logistics",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-02 06:00 - 10:00",
    "delivery_location": "Gainesville, FL 32608",
    "delivery_window": "2026-09-02 12:00 - 14:00",
    "commodity": "Medical specimens",
}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    yield


class TestNoMissionRecordWithoutOne:
    def test_work_with_no_external_number_is_still_accepted(self):
        """The old code refused this outright. A direct customer, a phone call
        and a courier run all arrive without anybody else's number."""
        assert mt.validate(MINIMUM) == []
        record = mt.to_record(MINIMUM, source=mt.SOURCE_PHONE, taken_by="Mike")
        assert record["load_number"]

    def test_the_generated_number_is_ours_and_says_so(self):
        record = mt.to_record(MINIMUM, source=mt.SOURCE_PHONE, taken_by="Mike")
        assert record["load_number"].startswith("L1-")
        assert record["load_number_origin"] == ln.GENERATED

    def test_a_generated_number_never_poses_as_a_broker_reference(self):
        """Our number in the broker's field is how a payment goes missing."""
        record = mt.to_record(MINIMUM, source=mt.SOURCE_PHONE, taken_by="Mike")
        assert record["card_data"]["load_id"] == ""
        assert mission.external_load_number(record) == ""

    def test_every_source_produces_a_numbered_record(self):
        for source in mt.INTAKE_SOURCES:
            record = mt.to_record(MINIMUM, source=source, taken_by="Mike")
            assert record["load_number"], f"{source} produced an orphan"


class TestASuppliedNumberIsUsedExactly:
    @pytest.mark.parametrize("supplied", ["847261", "CVS-44912", "ABC123",
                                          "l1-lookalike", "  0042  "])
    def test_stored_byte_for_byte(self, supplied):
        """No case folding, no stripping dashes, no tidying. A number we
        cleaned up no longer matches theirs on an invoice."""
        values = dict(MINIMUM, load_number=supplied)
        record = mt.to_record(values, source=mt.SOURCE_EMAIL, taken_by="Mike")
        assert record["load_number"] == supplied.strip()
        assert record["load_number_origin"] == ln.SUPPLIED

    def test_a_supplied_number_stays_the_brokers_reference(self):
        values = dict(MINIMUM, load_number="847261")
        record = mt.to_record(values, source=mt.SOURCE_EMAIL, taken_by="Mike")
        assert record["card_data"]["load_id"] == "847261"
        assert mission.external_load_number(record) == "847261"


class TestGeneratedNumbersDoNotCollide:
    def test_it_fills_gaps_rather_than_marching_upward(self):
        assert ln.next_generated(["L1-0001", "L1-0003"]) == "L1-0002"

    def test_supplied_numbers_do_not_consume_the_sequence(self):
        assert ln.next_generated(["847261", "CVS-44912"]) == "L1-0001"

    def test_two_missions_created_in_a_row_get_different_numbers(self):
        first = mt.create_mission(MINIMUM, source=mt.SOURCE_PHONE,
                                  taken_by="Mike", sandbox_module=sandbox,
                                  mission_module=mission)
        second = mt.create_mission(MINIMUM, source=mt.SOURCE_PHONE,
                                   taken_by="Mike", sandbox_module=sandbox,
                                   mission_module=mission)
        assert first["load_number"] != second["load_number"]
        assert {first["load_number"], second["load_number"]} == {"L1-0001", "L1-0002"}

    def test_the_record_is_retrievable_by_its_load_number(self):
        """The whole point of the doctrine."""
        created = mt.create_mission(MINIMUM, source=mt.SOURCE_COURIER,
                                    taken_by="Mike", sandbox_module=sandbox,
                                    mission_module=mission)
        stored = [r for r in sandbox.get_all().values()
                  if r.get("load_number") == created["load_number"]]
        assert len(stored) == 1


class TestComiRecognisesMissionIntake:
    @pytest.mark.parametrize("subject", ["L1-0001", "L1-0042 Re: template",
                                         "l1-0007", "  L1-0009  "])
    def test_an_l1_subject_is_mission_intake(self, subject):
        assert ln.is_mission_intake(subject)

    @pytest.mark.parametrize("subject", ["RE: rate confirmation", "Load 847261",
                                         "", "Invoice 4471", "FW: detention"])
    def test_anything_else_is_not(self, subject):
        """Not a general communication, not a broker message, not a customer
        message -- the prefix is the whole rule, so it has to be tight."""
        assert not ln.is_mission_intake(subject)

    def test_the_number_is_recovered_from_the_subject(self):
        assert ln.from_subject("L1-0042 Re: Mission Template") == "L1-0042"
        assert ln.from_subject("RE: rate confirmation") == ""

    def test_the_template_carries_the_number_the_driver_replies_with(self):
        opened = mt.open_template()
        body = mt.render_email(load_number=opened["load_number"])
        assert opened["subject"] == opened["load_number"]
        assert opened["load_number"] in body
        assert ln.is_mission_intake(opened["subject"])


class TestTheNumberIsIssuedBeforeTheTemplateIsFilled:
    def test_opening_a_template_assigns_immediately(self):
        """JOE hands out the number when the driver asks for the template, not
        when it comes back. Otherwise it cannot be the subject line."""
        opened = mt.open_template()
        assert opened["load_number"] == "L1-0001"
        assert opened["values"] == mt.blank_template()

    def test_a_known_customer_number_can_be_supplied_at_the_start(self):
        opened = mt.open_template(supplied="CVS-44912")
        assert opened["load_number"] == "CVS-44912"
        assert opened["origin"] == ln.SUPPLIED


class TestOneTemplateForEveryKindOfWork:
    def test_there_is_no_courier_or_medical_variant(self):
        """No specialty templates. Service type is a field, not a template."""
        assert "service" in mt.TEMPLATE_KEYS
        for source in mt.INTAKE_SOURCES:
            record = mt.to_record(dict(MINIMUM, service="Medical"),
                                  source=source, taken_by="Mike")
            assert record["service"] == "Medical"

    def test_the_six_sections_are_the_operators(self):
        assert mt.SECTIONS == ("MISSION SOURCE", "LOAD CONTROL", "PICKUP",
                               "DELIVERY", "CARGO", "NOTES")

    def test_every_field_belongs_to_one_of_them(self):
        for field in mt.TEMPLATE:
            assert field.section in mt.SECTIONS, field.key

    def test_all_seven_sources_are_supported(self):
        assert set(mt.INTAKE_SOURCES) == {
            "SWEEP", "EMAIL", "JOE", "CUSTOMER", "PHONE", "COURIER", "API"}


class TestMultiStopWorkNeedsNoSecondTemplate:
    def test_additional_stops_become_the_stop_list_the_cockpit_reads(self):
        values = dict(MINIMUM, additional_stops=(
            "Publix DC Lakeland | 2026-09-02 14:00 | Dock 7 | 863-555-0114\n"
            "Winn-Dixie Orlando | 2026-09-02 17:00 | Dock 2 | 407-555-0198"))
        record = mt.to_record(values, source=mt.SOURCE_JOE, taken_by="Mike")
        assert record["stop_total"] == 3
        assert record["stops"][2]["facility"] == "Winn-Dixie Orlando"
        assert record["stops"][2]["phone"] == "407-555-0198"

    def test_no_extra_stops_is_the_normal_case_not_an_error(self):
        record = mt.to_record(MINIMUM, source=mt.SOURCE_JOE, taken_by="Mike")
        assert record["stop_total"] == 1
        assert record["stops"][0]["facility"] == "Gainesville, FL 32608"

    def test_eight_stops_is_within_reach(self):
        """The operator's stated maximum in a day."""
        extra = "\n".join(f"Stop {i} | 2026-09-02 1{i}:00 | Dock {i} | 904-555-010{i}"
                          for i in range(2, 9))
        record = mt.to_record(dict(MINIMUM, additional_stops=extra),
                              source=mt.SOURCE_JOE, taken_by="Mike")
        assert record["stop_total"] == 8
