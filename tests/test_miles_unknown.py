"""A card that cannot be scored says which input it is missing.

The silent miss these exist to prevent: a card shows `Score Unknown` and nothing
else. Two of Mike's sat that way on the Home strip on 2026-09-16 -- one of them
carrying a rate of $475 -- and nothing on the glass said whether the rate, the
miles or the engine itself was the problem. Scoring swallows every failure and
returns None, which is right (an unscored card still beats no card) and useless
on its own.

Absent miles now read the way a pending rate reads: one neutral line, on the
card, not in the warning list.
"""

from __future__ import annotations

from dispatch import load_assessment as la
from dispatch import mission_template as mt


class TestTheCardSaysWhichInputIsMissing:
    def test_a_lane_with_no_miles_carries_the_line(self):
        assessment = la.assess({"origin": "Ocala, FL", "destination": "Macon, GA",
                                "rate": "900"})
        assert assessment["miles_known"] is False
        assert assessment["miles_line"] == la.MILES_UNKNOWN_LINE

    def test_a_lane_the_table_holds_carries_no_line(self):
        assessment = la.assess({"origin": "Jacksonville, FL",
                                "destination": "Savannah, GA", "rate": "1150"})
        assert assessment["miles_known"] is True
        assert assessment["miles_line"] == ""

    def test_typed_miles_answer_for_a_lane_nothing_else_knows(self):
        """The whole point of the box on the New Mission screen: a load Mike can
        price himself is never left unranked."""
        assessment = la.assess({"origin": "Ocala, FL", "destination": "Macon, GA",
                                "rate": "900", "distance_miles": 210})
        assert assessment["miles_known"] is True
        assert assessment["miles_line"] == ""
        assert assessment["distance"]["miles"] == 210

    def test_the_line_is_never_a_warning(self):
        """Neutral, like "* Rate pending". A man reading warnings is reading
        things that are wrong; a lane the table does not hold is not wrong."""
        assessment = la.assess({"origin": "Ocala, FL", "destination": "Macon, GA"})
        assert all("mile" not in w["text"].lower() for w in assessment["warnings"])

    def test_the_gap_is_named_once_not_twice(self):
        """Miles used to sit in "Missing: equipment, weight, miles" as well,
        which both buried the blocking input among nice-to-haves and said the
        same thing twice. One line, in the place that means it cannot score."""
        assessment = la.assess({"origin": "Ocala, FL", "destination": "Macon, GA"})
        assert "miles" not in assessment["missing"]
        assert assessment["miles_line"] == la.MILES_UNKNOWN_LINE


class TestMilesCanBeTypedOnTheMission:
    def test_the_template_asks_for_them_beside_the_rate(self):
        keys = [f.key for f in mt.TEMPLATE if f.section == "LOAD CONTROL"]
        assert "distance_miles" in keys
        assert keys.index("distance_miles") == keys.index("rate") + 1

    def test_they_are_optional(self):
        """Blank is the normal case. Dispatch works the lane out when it can."""
        field = next(f for f in mt.TEMPLATE if f.key == "distance_miles")
        assert field.required is False

    def _filled(self, **extra):
        values = dict(mt.blank_template())
        values.update({"customer": "Ocala Freight", "commodity": "Pallets",
                       "pickup_location": "Ocala, FL", "pickup_window": "2026-10-01 08:00",
                       "delivery_location": "Macon, GA",
                       "delivery_window": "2026-10-01 15:00"})
        values.update(extra)
        return values

    def test_a_typed_number_reaches_the_card(self):
        record = mt.to_record(self._filled(distance_miles="210"),
                              source=mt.SOURCE_DIRECT, load_number="L1-9001")
        assert record["card_data"]["distance_miles"] == 210

    def test_a_blank_box_stores_nothing_rather_than_a_zero(self):
        """Zero would read as a measured distance of nothing, and would price."""
        record = mt.to_record(self._filled(distance_miles=""),
                              source=mt.SOURCE_DIRECT, load_number="L1-9002")
        assert "distance_miles" not in record["card_data"]
