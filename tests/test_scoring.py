"""Tests for the dispatch load scoring engine."""

from __future__ import annotations

import pytest

from dispatch.scoring import (
    compute_deadhead_miles,
    compute_economic_opportunity,
    compute_fuel_estimate,
    compute_hos_risk,
    compute_position_impact,
    compute_return_home,
    compute_route_risk,
    compute_score,
    compute_tomorrow_position_risk,
    score_load,
)


SAMPLE_LOAD_GOOD = {
    "load_id": "LOAD-001",
    "origin": "Jacksonville, FL 32202",
    "destination": "Savannah, GA 31401",
    "distance_miles": 140,
    "rate": 625,
    "rpm": 4.46,
    "pickup_window": "2026-07-30 06:00 - 10:00",
    "delivery_window": "2026-07-30 14:00 - 18:00",
    "equipment_required": "Dry Van 53'",
    "equipment_match": "match",
    "weight_lbs": 38000,
    "detention_history": "Low - avg 30 min",
    "broker_intelligence": "Reliable - 12 loads completed, avg pay within 15 days",
}

SAMPLE_LOAD_RISKY = {
    "load_id": "LOAD-002",
    "origin": "Jacksonville, FL 32202",
    "destination": "Atlanta, GA 30301",
    "distance_miles": 345,
    "rate": None,
    "rpm": None,
    "pickup_window": None,
    "delivery_window": "2026-07-31 08:00 - 12:00",
    "equipment_required": "Flatbed 48'",
    "equipment_match": "mismatch",
    "weight_lbs": 44000,
    "broker_intelligence": "Unknown broker - no history",
}


class TestPositionImpact:
    def test_near_home(self):
        result = compute_position_impact(SAMPLE_LOAD_GOOD)
        assert "Favorable" in result or "Acceptable" in result

    def test_far_from_home(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": "Atlanta, GA 30301"}
        result = compute_position_impact(load)
        assert "Moderate" in result or "Unfavorable" in result

    def test_unknown_destination(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": ""}
        assert compute_position_impact(load) == "Unknown"

    def test_unknown_city(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": "Nowhere, XX"}
        assert compute_position_impact(load) == "Unknown"


class TestReturnHome:
    def test_short_return(self):
        result = compute_return_home(SAMPLE_LOAD_GOOD)
        assert "same-day" in result.lower() or "return" in result.lower()

    def test_long_return(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": "Birmingham, AL 35201"}
        result = compute_return_home(load)
        assert "return" in result.lower()

    def test_unknown(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": ""}
        assert compute_return_home(load) == "Unknown"


class TestTomorrowPositionRisk:
    def test_near_home(self):
        result = compute_tomorrow_position_risk(SAMPLE_LOAD_GOOD)
        assert "Low" in result

    def test_far_with_options(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": "Atlanta, GA 30301"}
        result = compute_tomorrow_position_risk(load)
        assert "Medium" in result or "Low" in result

    def test_unknown_destination(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": ""}
        assert compute_tomorrow_position_risk(load) == "Unknown"


class TestHOSRisk:
    def test_short_drive(self):
        result = compute_hos_risk(SAMPLE_LOAD_GOOD)
        assert "Low" in result

    def test_long_drive(self):
        load = {**SAMPLE_LOAD_GOOD, "distance_miles": 500}
        result = compute_hos_risk(load)
        assert "High" in result or "Medium" in result

    def test_exceeds_limit(self):
        load = {**SAMPLE_LOAD_GOOD, "distance_miles": 600}
        result = compute_hos_risk(load)
        assert "Critical" in result

    def test_tight_window(self):
        load = {
            **SAMPLE_LOAD_GOOD,
            "distance_miles": 300,
            "pickup_window": "2026-07-30 06:00 - 07:00",
            "delivery_window": "2026-07-30 10:00 - 12:00",
        }
        result = compute_hos_risk(load)
        assert "tight" in result.lower() or "High" in result

    def test_unknown_distance(self):
        load = {**SAMPLE_LOAD_GOOD, "distance_miles": None}
        assert compute_hos_risk(load) == "Unknown"


class TestRouteRisk:
    def test_clean_load(self):
        result = compute_route_risk(SAMPLE_LOAD_GOOD)
        assert "Low" in result

    def test_multiple_risks(self):
        result = compute_route_risk(SAMPLE_LOAD_RISKY)
        assert "High" in result or "Medium" in result

    def test_equipment_mismatch(self):
        load = {**SAMPLE_LOAD_GOOD, "equipment_match": "mismatch"}
        result = compute_route_risk(load)
        assert "mismatch" in result.lower()

    def test_overweight(self):
        load = {**SAMPLE_LOAD_GOOD, "weight_lbs": 48000}
        result = compute_route_risk(load)
        assert "overweight" in result.lower()

    def test_hard_stop(self):
        load = {**SAMPLE_LOAD_GOOD, "hard_stop": True, "hard_stop_reason": "no TWIC"}
        result = compute_route_risk(load)
        assert "hard stop" in result.lower()

    def test_outside_radius(self):
        load = {**SAMPLE_LOAD_GOOD, "distance_miles": 600}
        result = compute_route_risk(load)
        assert "outside operating radius" in result.lower()

    def test_high_detention(self):
        load = {**SAMPLE_LOAD_GOOD, "detention_history": "High - avg 3 hours"}
        result = compute_route_risk(load)
        assert "detention" in result.lower()

    def test_an_unknown_broker_is_not_a_risk(self):
        """Rewritten, not weakened: this asserted a rule the operator overruled.

        An unfamiliar broker used to be flagged as a hazard. Trust is assumed
        until broken and is not a program variable, so the assertion is inverted
        rather than removed -- the behaviour is still pinned, to the opposite
        answer. See docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md section 3.
        """
        load = {**SAMPLE_LOAD_GOOD, "broker_intelligence": "Unknown broker"}
        assert "broker" not in compute_route_risk(load).lower()
        assert compute_route_risk(load) == compute_route_risk(SAMPLE_LOAD_GOOD)


class TestEconomicOpportunity:
    def test_good_rate(self):
        result = compute_economic_opportunity(SAMPLE_LOAD_GOOD)
        assert "Good" in result or "Strong" in result

    def test_no_rate(self):
        result = compute_economic_opportunity(SAMPLE_LOAD_RISKY)
        assert "Unknown" in result

    def test_low_rate(self):
        load = {**SAMPLE_LOAD_GOOD, "rate": 200}
        result = compute_economic_opportunity(load)
        assert "Below floor" in result

    def test_excellent_rate(self):
        load = {**SAMPLE_LOAD_GOOD, "rate": 900}
        result = compute_economic_opportunity(load)
        assert "Strong" in result

    def test_includes_margin(self):
        result = compute_economic_opportunity(SAMPLE_LOAD_GOOD)
        assert "margin" in result.lower()
        assert "net" in result.lower()


class TestDeadheadAndFuel:
    def test_deadhead_known(self):
        result = compute_deadhead_miles(SAMPLE_LOAD_GOOD)
        assert result == 140  # Savannah -> Jacksonville

    def test_deadhead_unknown(self):
        load = {**SAMPLE_LOAD_GOOD, "destination": "Nowhere, XX"}
        assert compute_deadhead_miles(load) is None

    def test_fuel_estimate(self):
        result = compute_fuel_estimate(SAMPLE_LOAD_GOOD)
        assert result is not None
        assert result > 0
        # 140 miles + 140 deadhead * $0.62/mi = ~$173.60
        assert 150 < result < 200

    def test_fuel_no_distance(self):
        load = {**SAMPLE_LOAD_GOOD, "distance_miles": None}
        assert compute_fuel_estimate(load) is None


class TestOverallScore:
    def test_good_load_scores_high(self):
        """80% of what is achievable -- the same bar, expressed so it cannot drift.

        This read `>= 80` against an implicit maximum of 100. Removing broker
        confidence lowered the ceiling to 90, which would have silently made this
        a 89% bar. Naming the share keeps it honest through future weight changes.
        """
        from dispatch.scoring import MAX_SCORE

        assert compute_score(SAMPLE_LOAD_GOOD) >= 0.80 * MAX_SCORE

    def test_risky_load_scores_lower(self):
        score = compute_score(SAMPLE_LOAD_RISKY)
        assert score < compute_score(SAMPLE_LOAD_GOOD)

    def test_score_bounded(self):
        for load in [SAMPLE_LOAD_GOOD, SAMPLE_LOAD_RISKY]:
            score = compute_score(load)
            assert 0 <= score <= 100

    def test_minimal_load(self):
        score = compute_score({"load_id": "LOAD-EMPTY"})
        assert 0 <= score <= 100

    def test_deterministic(self):
        s1 = compute_score(SAMPLE_LOAD_GOOD)
        s2 = compute_score(SAMPLE_LOAD_GOOD)
        assert s1 == s2


class TestScoreLoad:
    def test_returns_all_fields(self):
        result = score_load(SAMPLE_LOAD_GOOD)
        assert "position_impact" in result
        assert "return_home_required" in result
        assert "tomorrow_position_risk" in result
        assert "hos_risk" in result
        assert "route_risk" in result
        assert "economic_opportunity_flag" in result
        assert "deadhead_miles" in result
        assert "fuel_estimate" in result
        assert "score" in result

    def test_good_load_values(self):
        result = score_load(SAMPLE_LOAD_GOOD)
        assert result["position_impact"] != "Unknown"
        assert result["return_home_required"] != "Unknown"
        assert result["hos_risk"] != "Unknown"
        assert result["route_risk"] != "Unknown"
        assert result["economic_opportunity_flag"] != "Unknown"
        assert result["deadhead_miles"] is not None
        assert result["fuel_estimate"] is not None
        from dispatch.scoring import MAX_SCORE

        assert result["score"] >= 0.80 * MAX_SCORE

    def test_risky_load_values(self):
        result = score_load(SAMPLE_LOAD_RISKY)
        assert "mismatch" in result["route_risk"].lower() or "unknown" in result["route_risk"].lower()
        assert result["score"] < score_load(SAMPLE_LOAD_GOOD)["score"]


class TestSandboxScoring:
    """Integration: scoring wires into sandbox entry creation."""

    def test_update_scoring(self, tmp_path, monkeypatch):
        from portal.models import sandbox

        monkeypatch.setattr(sandbox, "_sandbox_path", lambda: tmp_path / "sandbox.json")

        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="LOAD-001",
            title="Test Load",
            card_data=SAMPLE_LOAD_GOOD.copy(),
        )
        assert entry["position_impact"] == "Unknown"

        scoring = score_load(SAMPLE_LOAD_GOOD)
        updated = sandbox.update_scoring(entry["id"], scoring)

        assert updated is not None
        assert updated["position_impact"] != "Unknown"
        assert updated["hos_risk"] != "Unknown"
        assert updated["route_risk"] != "Unknown"
        assert updated["score"] == scoring["score"]
        assert updated["card_data"]["deadhead_miles"] == scoring["deadhead_miles"]
        assert updated["card_data"]["fuel_estimate"] == scoring["fuel_estimate"]

    def test_update_scoring_not_found(self, tmp_path, monkeypatch):
        from portal.models import sandbox

        monkeypatch.setattr(sandbox, "_sandbox_path", lambda: tmp_path / "sandbox.json")

        result = sandbox.update_scoring("NONEXISTENT", {"score": 50})
        assert result is None

    def test_helpers_load_dispatch_runs_scoring(self, tmp_path, monkeypatch):
        import json
        from dispatch import acquisition
        from portal import helpers

        sample_dir = tmp_path / "samples"
        sample_dir.mkdir()
        (sample_dir / "test.json").write_text(json.dumps(SAMPLE_LOAD_GOOD))
        monkeypatch.setattr(acquisition, "_DEFAULT_SAMPLE_DIR", sample_dir)

        loads = helpers.load_dispatch_data()
        assert len(loads) == 1
        load = loads[0]
        from dispatch.scoring import MAX_SCORE

        assert load["score"] >= 0.80 * MAX_SCORE
        assert load["deadhead_miles"] is not None
        assert load["fuel_estimate"] is not None
        assert "_scoring" in load
        assert load["_scoring"]["position_impact"] != "Unknown"
