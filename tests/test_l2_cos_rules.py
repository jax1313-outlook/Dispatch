"""Tests for the six deterministic L2-COS dispatch rule modules."""

from __future__ import annotations

import pytest

from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence
from l2_cos.rules import ALL_RULES
from l2_cos.rules import broker_risk, capacity_match, deadhead_cost, facility_risk, lane_fit, rate_anomaly


def test_all_rules_registered():
    names = {m.NAME for m in ALL_RULES}
    assert names == {
        "lane_fit",
        "rate_anomaly",
        "facility_risk",
        "broker_risk",
        "capacity_match",
        "deadhead_cost",
    }


def test_rule_result_shape_and_determinism(clean_load, clean_broker):
    for module in ALL_RULES:
        first = module.run(clean_load, broker=clean_broker)
        second = module.run(clean_load, broker=clean_broker)
        assert first == second  # deterministic: identical input -> identical output
        assert 0 <= first.score <= 100
        assert first.module == module.NAME
        assert first.version == module.VERSION
        assert isinstance(first.flags, list)


# --------------------------------------------------------------------------- lane_fit

def test_lane_fit_preferred_match(clean_load, clean_broker):
    result = lane_fit.run(clean_load, broker=clean_broker)
    assert result.score == 100
    assert "preferred_lane_match" in result.flags


def test_lane_fit_adjacent(clean_broker):
    load = {"origin_state": "CA", "destination_state": "NV"}  # shares CA with CA-TX/CA-AZ
    result = lane_fit.run(load, broker=clean_broker)
    assert result.score == 60
    assert "adjacent_lane" in result.flags


def test_lane_fit_new_lane(clean_broker):
    load = {"origin_state": "NY", "destination_state": "OH"}
    result = lane_fit.run(load, broker=clean_broker)
    assert result.score == 30
    assert "new_lane" in result.flags


def test_lane_fit_unknown_lane_no_broker():
    result = lane_fit.run({}, broker=None)
    assert "lane_unknown" in result.flags
    assert result.score == 30


# --------------------------------------------------------------------------- rate_anomaly

def test_rate_anomaly_in_band(clean_load, clean_broker):
    result = rate_anomaly.run(clean_load, broker=clean_broker)
    assert "rate_in_band" in result.flags
    assert result.score == 100


def test_rate_anomaly_below_band(risky_load, risky_broker):
    result = rate_anomaly.run(risky_load, broker=risky_broker)
    assert "rate_below_band" in result.flags
    assert result.score == 20


def test_rate_anomaly_missing_rate(clean_broker):
    result = rate_anomaly.run({"origin_state": "CA", "destination_state": "TX"}, broker=clean_broker)
    assert "rate_missing" in result.flags


def test_rate_anomaly_no_history(clean_broker):
    load = {"origin_state": "NY", "destination_state": "OH", "rate_per_mile": 2.0}
    result = rate_anomaly.run(load, broker=clean_broker)
    assert "no_rate_history" in result.flags


def test_rate_anomaly_above_band(clean_broker):
    load = {"origin_state": "CA", "destination_state": "TX", "rate_per_mile": 10.0}
    result = rate_anomaly.run(load, broker=clean_broker)
    assert "rate_above_band" in result.flags
    assert result.score == 85


# --------------------------------------------------------------------------- facility_risk

def test_facility_risk_clean_facilities():
    facility = LocationIntelligence(facility_id="F1", name="N", address="A")
    result = facility_risk.run({}, facility_pickup=facility, facility_delivery=facility)
    assert result.score == 100
    assert result.flags == []


def test_facility_risk_flags_history_and_security():
    facility = LocationIntelligence(
        facility_id="F1", name="N", address="A",
        historical_problems=["late gate"], security_requirements="TWIC",
    )
    result = facility_risk.run({}, facility_pickup=facility, facility_delivery=None)
    assert "pickup_history_flagged" in result.flags
    assert "pickup_security_requirements" in result.flags
    assert "facility_profile_missing" in result.flags
    assert result.score == 100 - 15 - 10


def test_facility_risk_score_floor():
    facility = LocationIntelligence(
        facility_id="F1", name="N", address="A",
        historical_problems=["a", "b", "c", "d", "e", "f"],  # capped at 4 penalties
        security_requirements="TWIC",
    )
    result = facility_risk.run({}, facility_pickup=facility, facility_delivery=facility)
    assert result.score == 0  # 2 * (4*15 + 10) = 140 > 100, floored


# --------------------------------------------------------------------------- broker_risk

def test_broker_risk_no_profile():
    result = broker_risk.run({}, broker=None)
    assert "broker_profile_missing" in result.flags
    assert result.score == 50


def test_broker_risk_acceptable_terms(clean_broker):
    result = broker_risk.run({}, broker=clean_broker)
    assert "payment_terms_acceptable" in result.flags
    assert result.score == 100


def test_broker_risk_slow_pay_and_missing_contact(risky_broker):
    result = broker_risk.run({}, broker=risky_broker)
    assert "slow_payment_terms" in result.flags
    assert "broker_contact_incomplete" in result.flags
    assert result.score == 40


# --------------------------------------------------------------------------- capacity_match

def test_capacity_match_ok():
    result = capacity_match.run({"equipment_type": "Dry Van"})
    assert result.score == 100
    assert "equipment_match" in result.flags


def test_capacity_match_mismatch():
    result = capacity_match.run({"equipment_type": "Step Deck"})
    assert result.score == 0
    assert "equipment_mismatch" in result.flags


def test_capacity_match_unspecified():
    result = capacity_match.run({})
    assert "equipment_unspecified" in result.flags


# --------------------------------------------------------------------------- deadhead_cost

def test_deadhead_cost_low():
    result = deadhead_cost.run({"miles": 1000, "deadhead_miles": 50})
    assert "low_deadhead" in result.flags
    assert result.score == 100


def test_deadhead_cost_moderate():
    result = deadhead_cost.run({"miles": 1000, "deadhead_miles": 200})
    assert "moderate_deadhead" in result.flags
    assert result.score == 65


def test_deadhead_cost_high():
    result = deadhead_cost.run({"miles": 1000, "deadhead_miles": 500})
    assert "high_deadhead" in result.flags
    assert result.score == 20


def test_deadhead_cost_missing_data():
    result = deadhead_cost.run({"miles": None, "deadhead_miles": 50})
    assert "deadhead_data_missing" in result.flags
    result2 = deadhead_cost.run({"miles": 0, "deadhead_miles": 50})
    assert "deadhead_data_missing" in result2.flags
