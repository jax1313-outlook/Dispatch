"""Tests for the dispatch router module."""

from __future__ import annotations

import pytest

from cin_lite.dispatch.dispatch_router import (
    DispatchDecision,
    dispatch_load,
    DISPATCH_ACTIONS,
    DISPATCH_PRIORITIES,
    _ACCEPT_HIGH_THRESHOLD,
    _ACCEPT_THRESHOLD,
)


# ------------------------------------------------------------------ fixtures

@pytest.fixture
def strong_load() -> dict:
    """A perfect regional load: excellent rate, short distance, good weight."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Orlando, FL",
        "miles": 140,
        "rate": 560.00,
        "weight": 28000,
        "equipment_type": "dry_van",
        "pickup_date": "2026-07-29",
    }


@pytest.fixture
def medium_load() -> dict:
    """Acceptable rate, acceptable distance, light cargo."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Tallahassee, FL",
        "miles": 300,
        "rate": 660.00,
        "weight": 10000,
        "equipment_type": "flatbed",
        "pickup_date": "2026-07-30",
    }


@pytest.fixture
def marginal_load() -> dict:
    """Viable but marginal: acceptable rate, acceptable distance, no weight/equipment."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Savannah, GA",
        "miles": 300,
        "rate": 600.00,
        "pickup_date": "2026-07-30",
    }


@pytest.fixture
def low_rate_load() -> dict:
    """Rate below minimum — not viable."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Orlando, FL",
        "miles": 200,
        "rate": 100.00,
        "weight": 20000,
        "equipment_type": "dry_van",
    }


@pytest.fixture
def too_far_load() -> dict:
    """Distance exceeds practical max — not viable."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Los Angeles, CA",
        "miles": 2500,
        "rate": 10000.00,
        "weight": 30000,
        "equipment_type": "dry_van",
    }


@pytest.fixture
def overweight_load() -> dict:
    """Weight exceeds legal limit — not viable."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Orlando, FL",
        "miles": 140,
        "rate": 700.00,
        "weight": 50000,
        "equipment_type": "flatbed",
    }


# ------------------------------------------------- accept (high priority)

class TestAcceptHighPriority:
    def test_strong_load_accepted(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.action == "accept"
        assert decision.priority == "high"

    def test_strong_load_score_above_threshold(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.score >= _ACCEPT_HIGH_THRESHOLD

    def test_strong_load_reason_mentions_strong(self, strong_load):
        decision = dispatch_load(strong_load)
        assert "strong" in decision.reason

    def test_excellent_rate_preferred_distance_good_weight(self):
        load = {"miles": 200, "rate": 800.00, "weight": 30000, "equipment_type": "reefer"}
        decision = dispatch_load(load)
        assert decision.action == "accept"
        assert decision.priority == "high"
        assert decision.score == 100

    def test_acceptable_rate_preferred_distance_good_weight_equipment(self):
        load = {"miles": 200, "rate": 400.00, "weight": 30000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action == "accept"
        assert decision.priority == "high"
        assert decision.score == 85

    def test_threshold_boundary_exactly_70(self):
        load = {"miles": 300, "rate": 600.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.score >= _ACCEPT_HIGH_THRESHOLD
        assert decision.action == "accept"
        assert decision.priority == "high"


# ------------------------------------------------- accept (medium priority)

class TestAcceptMediumPriority:
    def test_medium_load_accepted(self, medium_load):
        decision = dispatch_load(medium_load)
        assert decision.action == "accept"
        assert decision.priority == "medium"

    def test_medium_load_score_in_range(self, medium_load):
        decision = dispatch_load(medium_load)
        assert _ACCEPT_THRESHOLD <= decision.score < _ACCEPT_HIGH_THRESHOLD

    def test_acceptable_rate_preferred_distance_no_weight(self):
        load = {"miles": 200, "rate": 400.00}
        decision = dispatch_load(load)
        assert decision.action == "accept"
        assert decision.priority == "medium"
        assert decision.score == 55

    def test_acceptable_rate_acceptable_distance_light_equipment(self):
        load = {"miles": 400, "rate": 800.00, "weight": 5000, "equipment_type": "sprinter"}
        decision = dispatch_load(load)
        assert decision.action == "accept"
        assert decision.priority == "medium"
        assert decision.score == 60

    def test_excellent_rate_acceptable_distance_no_weight_no_equipment(self):
        load = {"miles": 400, "rate": 1600.00}
        decision = dispatch_load(load)
        assert decision.action == "accept"
        assert decision.priority == "medium"
        assert decision.score == 55


# ------------------------------------------------- flag_review

class TestFlagReview:
    def test_marginal_load_flagged(self, marginal_load):
        decision = dispatch_load(marginal_load)
        assert decision.action == "flag_review"
        assert decision.priority == "low"

    def test_marginal_load_score_below_accept(self, marginal_load):
        decision = dispatch_load(marginal_load)
        assert decision.score < _ACCEPT_THRESHOLD

    def test_marginal_reason_mentions_review(self, marginal_load):
        decision = dispatch_load(marginal_load)
        assert "review" in decision.reason

    def test_acceptable_rate_acceptable_distance_only(self):
        load = {"miles": 300, "rate": 600.00}
        decision = dispatch_load(load)
        assert decision.action == "flag_review"
        assert decision.score == 40


# ------------------------------------------------- reject (not viable)

class TestReject:
    def test_low_rate_rejected(self, low_rate_load):
        decision = dispatch_load(low_rate_load)
        assert decision.action == "reject"
        assert decision.priority == "low"

    def test_low_rate_reason(self, low_rate_load):
        decision = dispatch_load(low_rate_load)
        assert "rate" in decision.reason

    def test_too_far_rejected(self, too_far_load):
        decision = dispatch_load(too_far_load)
        assert decision.action == "reject"
        assert "distance" in decision.reason

    def test_overweight_rejected(self, overweight_load):
        decision = dispatch_load(overweight_load)
        assert decision.action == "reject"
        assert "weight" in decision.reason

    def test_multiple_rejection_reasons(self):
        load = {"miles": 800, "rate": 100.00, "weight": 50000}
        decision = dispatch_load(load)
        assert decision.action == "reject"
        assert "rate" in decision.reason
        assert "distance" in decision.reason
        assert "weight" in decision.reason

    def test_reject_carries_flags(self, low_rate_load):
        decision = dispatch_load(low_rate_load)
        assert "rate_below_minimum" in decision.flags


# ------------------------------------------------- invalid data

class TestInvalidData:
    def test_missing_miles(self):
        decision = dispatch_load({"rate": 500})
        assert decision.action == "reject"
        assert "mileage" in decision.reason

    def test_zero_miles(self):
        decision = dispatch_load({"miles": 0, "rate": 500})
        assert decision.action == "reject"
        assert "invalid_miles" in decision.flags

    def test_negative_miles(self):
        decision = dispatch_load({"miles": -10, "rate": 500})
        assert decision.action == "reject"

    def test_missing_rate(self):
        decision = dispatch_load({"miles": 100})
        assert decision.action == "reject"
        assert "rate" in decision.reason

    def test_zero_rate(self):
        decision = dispatch_load({"miles": 100, "rate": 0})
        assert decision.action == "reject"
        assert "invalid_rate" in decision.flags

    def test_negative_rate(self):
        decision = dispatch_load({"miles": 100, "rate": -50})
        assert decision.action == "reject"

    def test_empty_dict(self):
        decision = dispatch_load({})
        assert decision.action == "reject"

    def test_string_miles(self):
        decision = dispatch_load({"miles": "one hundred", "rate": 500})
        assert decision.action == "reject"

    def test_string_rate(self):
        decision = dispatch_load({"miles": 100, "rate": "five hundred"})
        assert decision.action == "reject"


# ------------------------------------------------- DispatchDecision structure

class TestDispatchDecision:
    def test_returns_dispatch_decision(self, strong_load):
        decision = dispatch_load(strong_load)
        assert isinstance(decision, DispatchDecision)

    def test_action_in_valid_actions(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.action in DISPATCH_ACTIONS

    def test_priority_in_valid_priorities(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.priority in DISPATCH_PRIORITIES

    def test_flags_is_list(self, strong_load):
        decision = dispatch_load(strong_load)
        assert isinstance(decision.flags, list)

    def test_load_result_is_dict(self, strong_load):
        decision = dispatch_load(strong_load)
        assert isinstance(decision.load_result, dict)
        assert "viable" in decision.load_result
        assert "score" in decision.load_result

    def test_to_json_round_trip(self, strong_load):
        decision = dispatch_load(strong_load)
        data = decision.to_json()
        assert isinstance(data, dict)
        assert data["action"] == "accept"
        assert data["priority"] == "high"
        assert data["score"] == decision.score
        assert isinstance(data["flags"], list)
        assert isinstance(data["load_result"], dict)

    def test_to_json_on_rejected(self, low_rate_load):
        decision = dispatch_load(low_rate_load)
        data = decision.to_json()
        assert data["action"] == "reject"
        assert data["load_result"]["viable"] is False


# ------------------------------------------------- score consistency

class TestScoreConsistency:
    def test_strong_beats_medium(self, strong_load, medium_load):
        strong = dispatch_load(strong_load)
        medium = dispatch_load(medium_load)
        assert strong.score > medium.score

    def test_medium_beats_marginal(self, medium_load, marginal_load):
        medium = dispatch_load(medium_load)
        marginal = dispatch_load(marginal_load)
        assert medium.score > marginal.score

    def test_score_matches_load_result(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.score == decision.load_result["score"]

    def test_flags_match_load_result(self, strong_load):
        decision = dispatch_load(strong_load)
        assert decision.flags == decision.load_result["flags"]


# ------------------------------------------------- equipment variations

class TestEquipmentVariations:
    @pytest.mark.parametrize("equip", [
        "dry_van", "flatbed", "reefer", "box_truck", "sprinter", "straight_truck",
    ])
    def test_supported_equipment_adds_score(self, equip):
        load = {"miles": 200, "rate": 600.00, "weight": 25000, "equipment_type": equip}
        decision = dispatch_load(load)
        assert "equipment_supported" in decision.flags

    def test_unknown_equipment_no_score(self):
        load = {"miles": 200, "rate": 600.00, "weight": 25000, "equipment_type": "helicopter"}
        decision = dispatch_load(load)
        assert "equipment_unknown" in decision.flags

    def test_missing_equipment_neutral(self):
        load = {"miles": 200, "rate": 600.00, "weight": 25000}
        decision = dispatch_load(load)
        assert "equipment_supported" not in decision.flags
        assert "equipment_unknown" not in decision.flags


# ------------------------------------------------- boundary values

class TestBoundaryValues:
    def test_rate_at_minimum(self):
        load = {"miles": 100, "rate": 200.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action != "reject"
        assert "rate_acceptable" in decision.flags

    def test_rate_just_below_minimum(self):
        load = {"miles": 100, "rate": 199.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action == "reject"
        assert "rate_below_minimum" in decision.flags

    def test_distance_at_preferred_max(self):
        load = {"miles": 250, "rate": 750.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert "distance_preferred" in decision.flags

    def test_distance_just_over_preferred(self):
        load = {"miles": 251, "rate": 753.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert "distance_acceptable" in decision.flags

    def test_distance_at_practical_max(self):
        load = {"miles": 500, "rate": 1500.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert "distance_acceptable" in decision.flags
        assert decision.action != "reject"

    def test_distance_just_over_practical_max(self):
        load = {"miles": 501, "rate": 1503.00, "weight": 25000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action == "reject"
        assert "distance_too_far" in decision.flags

    def test_weight_at_max(self):
        load = {"miles": 100, "rate": 400.00, "weight": 44000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action != "reject"
        assert "overweight" not in decision.flags

    def test_weight_just_over_max(self):
        load = {"miles": 100, "rate": 400.00, "weight": 44001, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert decision.action == "reject"
        assert "overweight" in decision.flags

    def test_weight_at_half_utilization(self):
        load = {"miles": 100, "rate": 400.00, "weight": 22000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert "good_weight_utilization" in decision.flags

    def test_weight_just_below_half_utilization(self):
        load = {"miles": 100, "rate": 400.00, "weight": 21000, "equipment_type": "dry_van"}
        decision = dispatch_load(load)
        assert "light_load" in decision.flags


# ------------------------------------------------- logging

class TestDispatchRouterLogging:
    def test_accept_logs_info(self, strong_load, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="cin_lite.dispatch.dispatch_router"):
            dispatch_load(strong_load)
        assert any("accepting" in r.message for r in caplog.records)

    def test_reject_logs_info(self, low_rate_load, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="cin_lite.dispatch.dispatch_router"):
            dispatch_load(low_rate_load)
        assert any("rejecting" in r.message for r in caplog.records)

    def test_flag_review_logs_info(self, marginal_load, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger="cin_lite.dispatch.dispatch_router"):
            dispatch_load(marginal_load)
        assert any("flagging" in r.message for r in caplog.records)

    def test_debug_log_includes_score(self, strong_load, caplog):
        import logging
        with caplog.at_level(logging.DEBUG, logger="cin_lite.dispatch.dispatch_router"):
            dispatch_load(strong_load)
        assert any("scored" in r.message for r in caplog.records)
