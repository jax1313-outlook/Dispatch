"""Scoring wired to the capacity engine.

`dispatch/scoring.py` carried its own weight constant and never consulted
`dispatch/capacity.py`, so a load that could not be run still scored well. These
tests pin the wiring, and — more importantly — pin the rule that made it worth
doing: blocking is a separate answer from fit, and it never moves the score.
"""

from __future__ import annotations

from dispatch.capacity import DynamicCapacity
from dispatch.scoring import assess_capacity, score_load


OBSERVED_AT = "2026-07-30T06:00:00+00:00"

SCORE_KEYS = {
    "position_impact",
    "return_home_required",
    "tomorrow_position_risk",
    "hos_risk",
    "route_risk",
    "economic_opportunity_flag",
    "deadhead_miles",
    "fuel_estimate",
    "score",
}

LOAD = {
    "load_id": "LOAD-001",
    "origin": "Jacksonville, FL 32202",
    "destination": "Savannah, GA 31401",
    "distance_miles": 140,
    "rate": 625,
    "pickup_window": "2026-07-30 06:00 - 10:00",
    "delivery_window": "2026-07-30 14:00 - 18:00",
    "equipment_match": "match",
    "weight_lbs": 10000,
    "pallets": 6,
    "broker_intelligence": "Reliable - 12 loads completed",
}


def van(**overrides) -> DynamicCapacity:
    """A small asset with an attested spec and an attested HOS snapshot."""
    cap = DynamicCapacity(equipment_id="VAN-01", driver_id="DRV-01")
    profile = {
        "asset_profile_id": "VAN-01-CARGO",
        "max_weight_lbs": 12000.0,
        "max_volume_cuft": 500.0,
        "max_linear_feet": 16.0,
        "max_pallets": 8,
        "source": "OEM_SPEC_SHEET",
        "verified_by": "Owner",
    }
    profile.update(overrides)
    cap.apply_asset_profile(**profile)
    cap.set_verified_hos(
        remaining_drive_hours=10.0,
        remaining_duty_hours=12.0,
        remaining_cycle_hours=60.0,
        source="ELD:Samsara",
        observed_at=OBSERVED_AT,
    )
    cap.cargo.stacking_policy = "STACKABLE"
    cap.cargo.allows_top_load = True
    return cap


class TestBackwardsCompatible:
    """Without a capacity, nothing changed."""

    def test_no_capacity_returns_the_original_keys_only(self):
        assert set(score_load(LOAD)) == SCORE_KEYS

    def test_no_capacity_is_byte_identical_to_the_capacity_path_for_shared_keys(self):
        plain = score_load(LOAD)
        wired = score_load(LOAD, capacity=van())
        for key in SCORE_KEYS:
            assert wired[key] == plain[key], key

    def test_capacity_adds_keys_rather_than_replacing_them(self):
        wired = score_load(LOAD, capacity=van())
        assert SCORE_KEYS.issubset(set(wired))
        assert "capacity_status" in wired
        assert "capacity_blocked" in wired


class TestBlockingIsSeparateFromScore:
    """The rule the wiring exists to enforce."""

    def test_a_load_that_fits_is_not_blocked(self):
        result = score_load(LOAD, capacity=van())
        assert result["capacity_blocked"] is False
        assert result["blocking_reasons"] == []

    def test_a_load_over_pallet_capacity_is_blocked(self):
        over = dict(LOAD, pallets=99)
        result = score_load(over, capacity=van())
        assert result["capacity_blocked"] is True
        assert result["blocking_reasons"]

    def test_a_load_over_weight_capacity_is_blocked(self):
        over = dict(LOAD, weight_lbs=50000)
        result = score_load(over, capacity=van())
        assert result["capacity_blocked"] is True

    def test_blocking_does_not_move_the_score(self):
        """A blocked load scores exactly what the same load unblocked scores.

        This is the whole point. Folding blocking into the score would make a
        disqualified load look like a merely worse one.
        """
        fits = score_load(LOAD, capacity=van())
        blocked = score_load(dict(LOAD, pallets=99), capacity=van())
        assert blocked["capacity_blocked"] is True
        assert blocked["score"] == fits["score"]

    def test_the_legacy_weight_constant_cannot_save_an_over_capacity_load(self):
        """12,000 lb is under the old 45,000 lb constant and over this asset.

        Before the wiring this load passed every check in the module.
        """
        over = dict(LOAD, weight_lbs=12500)
        result = score_load(over, capacity=van())
        assert result["capacity_blocked"] is True


class TestUnconfiguredAssetDoesNotSilentlyPass:
    def test_an_unconfigured_asset_is_not_clear_to_proceed(self):
        bare = DynamicCapacity(equipment_id="VAN-02")
        result = score_load(LOAD, capacity=bare)
        assert result["capacity_clear"] is False

    def test_an_unconfigured_asset_reports_findings_rather_than_silence(self):
        bare = DynamicCapacity(equipment_id="VAN-02")
        result = score_load(LOAD, capacity=bare)
        assert result["capacity_findings"]


class TestAssessmentIsAdvisory:
    def test_assessing_does_not_mutate_the_capacity(self):
        cap = van()
        before = cap.to_dict()
        assess_capacity(LOAD, cap)
        assert cap.to_dict() == before

    def test_scoring_with_capacity_does_not_mutate_the_capacity(self):
        cap = van()
        before = cap.to_dict()
        score_load(LOAD, capacity=cap)
        assert cap.to_dict() == before

    def test_scoring_does_not_mutate_the_load(self):
        load = dict(LOAD)
        score_load(load, capacity=van())
        assert load == LOAD


class TestDeterminism:
    def test_same_inputs_same_assessment(self):
        cap = van()
        first = score_load(LOAD, capacity=cap)
        second = score_load(LOAD, capacity=cap)
        assert first == second
