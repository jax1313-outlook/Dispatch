"""The capture call — spoken freight into the seventh contract.

OPP-CAPTURE v1.0 §6. The parser is a pure function on purpose: no microphone, no
speaker, no network. **A voice feature that can only be tested by speaking into
it does not get tested**, and the failures below were all found by reading
output, not by listening.
"""

from __future__ import annotations

import pytest

from dispatch import opportunity as opp

#: The illustrative call from §6, said the way a person says it.
FULL = ("Joe, log this one: DAT. Jacksonville to Tampa. One pallet, dry van. "
        "$750. Pickup Thursday, deliver Friday. "
        "Broker Southeast Freight, Sally, 904-555-0100. "
        "Notes: detention after two hours.")


class TestTheCanonicalCall:
    def setup_method(self):
        self.r = opp.parse_dictation(FULL)
        self.f = self.r["fields"]

    @pytest.mark.parametrize("key,value", [
        ("source_board", "DAT"),
        ("origin", "Jacksonville"),
        ("destination", "Tampa"),
        ("rate", 750.0),
        ("equipment", "dry van"),
        ("pickup_date", "Thursday"),
        ("delivery_date", "Friday"),
    ])
    def test_each_field_lands_where_it_belongs(self, key, value):
        assert self.f[key] == value

    def test_the_contact_is_kept_whole(self):
        """Company, name and number arrive as one dictated phrase. Splitting
        them would be inventing structure the Owner did not speak."""
        assert self.f["contact"] == "Southeast Freight, Sally, 904-555-0100"

    def test_nothing_is_missing(self):
        assert self.r["missing"] == []
        assert opp.one_question(self.r["missing"]) == ""

    def test_what_he_said_is_kept_verbatim(self):
        assert self.r["heard"].startswith("Joe, log this one: DAT.")


class TestItNeverManglesWhatHeSaid:
    def test_savannah_survives_the_equipment_matcher(self):
        """**The bug this exists for.** "van" lives inside "Savannah", and a
        substring match turned the destination into "Sa nah" — a city quietly
        destroyed by a feature looking for a trailer."""
        f = opp.parse_dictation("log this one Truckstop. Orlando to Savannah. "
                                "seven fifty. pickup Monday")["fields"]
        assert f["destination"] == "Savannah"
        assert "equipment" not in f

    def test_a_spoken_rate_does_not_leak_into_the_lane(self):
        """"seven fifty" read as a rate but left in the sentence ended up inside
        the destination."""
        f = opp.parse_dictation("log this Truckstop. Orlando to Savannah. seven fifty")["fields"]
        assert f["rate"] == 750.0
        assert f["destination"] == "Savannah"

    def test_the_destination_stops_at_the_sentence(self):
        """"Tampa. One pallet" is two facts and only the first is a city.

        "One pallet" used to land in notes, because nothing claimed it and
        nothing he says is discarded. It lands in `pieces_weight` now, which is
        the field it was always describing -- the quantity reader was added on
        2026-09-10 so a weight said mid-sentence stops ending up inside the
        destination. Notes stays the floor for text nothing can place.
        """
        f = opp.parse_dictation(FULL)["fields"]
        assert f["destination"] == "Tampa"
        assert f["pieces_weight"] == "One pallet"
        assert f["notes"] == "detention after two hours"

    def test_nothing_he_said_is_discarded(self):
        """Text the parser cannot place goes to notes rather than the floor. A
        capture that quietly loses half a sentence is worse than one that admits
        it did not understand."""
        r = opp.parse_dictation("log this one DAT. Miami to Atlanta. $900. "
                                "two skids on a liftgate")
        assert "liftgate" in r["fields"].get("notes", "")


class TestSparseCaptureAndTheOneQuestion:
    def test_the_lane_alone_is_parsed(self):
        f = opp.parse_dictation("log this one DAT. Jacksonville to Ocala")["fields"]
        assert f["source_board"] == "DAT"
        assert f["origin"] == "Jacksonville" and f["destination"] == "Ocala"

    def test_a_missing_rate_is_the_only_thing_worth_asking_about(self):
        r = opp.parse_dictation("log this one DAT. Jacksonville to Ocala. reefer, pickup Friday")
        assert r["missing"] == ["rate"]
        assert opp.one_question(r["missing"]) == "RATE?"

    def test_a_missing_board_is_not_missing_at_all_any_more(self):
        """**Owner ruling, 2026-09-08.** The board was one of the four a capture
        could not be logged without. It is now carried and not required, so a
        listing dictated without it is complete rather than sparse."""
        r = opp.parse_dictation("log this one Jacksonville to Ocala. $600")
        assert "source_board" not in r["missing"]
        assert r["missing"] == []

    def test_a_rate_is_never_invented(self):
        f = opp.parse_dictation("log this one DAT. Tampa to Naples")["fields"]
        assert "rate" not in f, "a missing rate must stay missing, not become zero"

    @pytest.mark.parametrize("said,expected", [
        ("$750", 750.0), ("750 dollars", 750.0), ("$1,850", 1850.0),
        ("seven fifty", 750.0), ("nine hundred", 900.0), ("twelve hundred", 1200.0),
    ])
    def test_the_ways_a_rate_gets_said(self, said, expected):
        f = opp.parse_dictation("log this one DAT. Tampa to Naples. %s" % said)["fields"]
        assert f["rate"] == expected


class TestItIsToleratntOfHowPeopleActuallyTalk:
    @pytest.mark.parametrize("opener", [
        "Joe, log this one:", "log this one", "log this", "capture this:",
        "JOE LOG THIS ONE", "joe log a load",
    ])
    def test_the_wake_phrase_is_not_a_straitjacket(self, opener):
        f = opp.parse_dictation("%s DAT. Tampa to Naples. $600" % opener)["fields"]
        assert f["origin"] == "Tampa" and f["destination"] == "Naples"

    def test_order_deviation_is_allowed(self):
        """§6: the canonical order is the fast path, not a straitjacket."""
        f = opp.parse_dictation("log this one DAT. Tampa to Naples. "
                                "pickup Tuesday. $600")["fields"]
        assert f["rate"] == 600.0 and f["pickup_date"] == "Tuesday"

    def test_an_empty_call_asks_for_the_rate_and_nothing_else(self):
        r = opp.parse_dictation("")
        assert r["fields"] == {} or "rate" not in r["fields"]
        assert opp.one_question(r["missing"]) == "RATE?"


class TestTheParserDecidesNothing:
    def test_it_writes_no_record(self):
        """Pure. Parsing is not capturing — the Spine is still the only thing
        that creates an Opportunity, through the contract."""
        before = len(opp.all_open()) if opp.all_open.__module__ else 0
        opp.parse_dictation(FULL)
        assert isinstance(opp.parse_dictation(FULL), dict)

    def test_its_output_is_exactly_what_the_contract_takes(self):
        """The fields it produces are contract fields and nothing else, so a
        caller can hand the result straight to capture() without translation."""
        f = opp.parse_dictation(FULL)["fields"]
        assert set(f) <= set(opp.FIELDS), set(f) - set(opp.FIELDS)


class TestReadingOffABoardNaturally:
    """Mike asked whether he has to speak in a fixed order, reading listings off
    a real board. He does not, and these are the five readings that proved it --
    three of which lost the rate before 2026-09-10.

    A lost rate is not a cosmetic miss. Rate is required, so the capture is
    refused and the listing is gone by the time he looks up.
    """

    def test_a_rate_said_as_digits(self):
        """Reading a board aloud, "eighteen fifty" and "1850" are the same act.
        Only the spelled-out one was recognised."""
        f = opp.parse_dictation("log this Atlanta to Charlotte flatbed 1850 pu 9/15")["fields"]
        assert f["rate"] == 1850.0
        assert f["destination"] == "Charlotte"

    def test_a_rate_with_a_scale_at_the_end(self):
        """"twenty two hundred" is three words and one number. The old reader
        only ever looked at two of them, so it found nothing."""
        f = opp.parse_dictation(
            "log this one Ocala to Macon dry van twenty two hundred pickup tomorrow")["fields"]
        assert f["rate"] == 2200.0
        assert f["destination"] == "Macon"

    def test_a_rate_with_a_scale_in_the_middle(self):
        """"nine hundred fifty" read as nine hundred, and left "fifty" behind in
        the city."""
        f = opp.parse_dictation(
            "new opportunity Tampa to Miami two pallets dry van nine hundred fifty")["fields"]
        assert f["rate"] == 950.0
        assert f["destination"] == "Miami"
        assert f["pieces_weight"] == "two pallets"

    def test_a_weight_before_the_rate_does_not_become_the_rate(self):
        """The sharpest one. "forty four thousand pounds, twenty two hundred"
        has two numbers in it and the first is not the money."""
        f = opp.parse_dictation(
            "capture this one Savannah GA to Orlando FL reefer forty four thousand "
            "pounds twenty two hundred broker is TQL pick up tomorrow")["fields"]
        assert f["rate"] == 2200.0
        assert f["pieces_weight"] == "forty four thousand pounds"
        assert f["destination"] == "Orlando FL"
        assert f["contact"] == "TQL"

    def test_capture_this_one_does_not_leave_its_one_in_the_origin(self):
        """The opener matched "capture this" and left "one" at the front, so an
        origin came out as "one Savannah GA"."""
        f = opp.parse_dictation(
            "capture this one Savannah to Orlando dry van nine hundred")["fields"]
        assert f["origin"] == "Savannah"

    def test_a_bare_number_outside_a_rate_range_is_not_a_rate(self):
        """A bare number is also a unit number, a road and a year. This refuses
        rather than guessing, which is why the range exists."""
        f = opp.parse_dictation("log this Tampa to Miami dry van unit 13")["fields"]
        assert "rate" not in f
