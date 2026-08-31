"""Detention costs a day, not points.

`compute_score` deducted 3 points for a high detention history and
`compute_route_risk` listed it as a hazard. Both treated a load likely to sit as
a worse load. The operator's accessorial policy prices detention to make waiting
worth its lost capacity, so it is not:

    "Detention is free money even if it is 3 hours."

What detention does consume is a day, and that belongs in capacity, not scoring:

    "If shipper warns about possible detention and accepts rate then that is a
    dedicated day to that load even if there is no detention."
"""

from __future__ import annotations

import pytest

from dispatch.scoring import (
    compute_capacity_flags,
    compute_route_risk,
    compute_score,
    score_load,
)

BASE = {
    "load_id": "L1",
    "origin": "Jacksonville, FL",
    "destination": "Savannah, GA",
    "distance_miles": 140,
    "rate": 625,
    "weight_lbs": 20000,
    "equipment_match": "match",
}

DETENTION_STRINGS = ["High - avg 3h", "high", "Low - avg 30 min", "", "Unknown"]


class TestDetentionDoesNotReduceTheScore:
    @pytest.mark.parametrize("detention", DETENTION_STRINGS)
    def test_the_score_is_unmoved_by_detention_history(self, detention):
        assert compute_score(dict(BASE, detention_history=detention)) == compute_score(BASE)

    def test_a_high_detention_load_scores_what_a_clean_one_scores(self):
        """The ruling, stated as arithmetic."""
        assert (compute_score(dict(BASE, detention_history="High - avg 3h"))
                == compute_score(dict(BASE, detention_history="Low - avg 30 min")))


class TestDetentionIsNotARisk:
    @pytest.mark.parametrize("detention", DETENTION_STRINGS)
    def test_it_never_appears_as_a_risk(self, detention):
        assert "detention" not in compute_route_risk(
            dict(BASE, detention_history=detention)).lower()

    def test_route_risk_is_unchanged_by_detention(self):
        assert (compute_route_risk(dict(BASE, detention_history="High - avg 3h"))
                == compute_route_risk(BASE))


class TestItSurvivesAsACapacityFlag:
    """Removed from the score, not from the operator's sight."""

    def test_a_high_detention_history_raises_a_flag(self):
        flags = compute_capacity_flags(dict(BASE, detention_history="High - avg 3h"))
        assert flags and any("dedicated day" in f for f in flags)

    def test_a_warned_shipper_raises_a_flag(self):
        flags = compute_capacity_flags(dict(BASE, detention_warned=True))
        assert flags and any("dedicated day" in f for f in flags)

    def test_the_flag_says_it_does_not_reduce_the_score(self):
        """So the operator is never left guessing whether it counted against him."""
        flags = compute_capacity_flags(dict(BASE, detention_history="High - avg 3h"))
        assert any("does not reduce" in f for f in flags)

    def test_a_clean_load_raises_no_flags(self):
        assert compute_capacity_flags(BASE) == []

    def test_low_detention_raises_no_flags(self):
        assert compute_capacity_flags(dict(BASE, detention_history="Low - avg 30 min")) == []

    def test_flags_reach_the_result(self):
        result = score_load(dict(BASE, detention_history="High - avg 3h"))
        assert result["capacity_flags"]

    def test_flags_are_ascii_safe(self):
        """These strings reach a Windows console log, which is not UTF-8."""
        for flag in compute_capacity_flags(dict(BASE, detention_history="High - avg 3h",
                                                detention_warned=True)):
            flag.encode("ascii")
