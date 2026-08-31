"""Trust is not a program variable.

`compute_score` awarded 10 points of 100 for a broker a string-match believed
reliable and 3 for one it did not recognise, and `compute_route_risk` flagged an
unfamiliar broker as a hazard. Both were the engine forming a judgement the
operator has ruled is his — and both failed in the same direction, penalising an
unknown broker when trust is assumed until broken.

`docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md` §3.
"""

from __future__ import annotations

import pytest

from dispatch.scoring import compute_route_risk, compute_score, score_load


BASE = {
    "load_id": "L1",
    "origin": "Jacksonville, FL",
    "destination": "Savannah, GA",
    "distance_miles": 140,
    "rate": 625,
    "weight_lbs": 20000,
    "equipment_match": "match",
    "pickup_window": "2026-07-30 06:00 - 10:00",
    "delivery_window": "2026-07-30 14:00 - 18:00",
}

BROKER_STRINGS = [
    "Reliable - 12 loads completed, avg pay within 15 days",
    "Unknown broker",
    "No history",
    "Slow payer, 60+ days",
    "",
]


class TestTheScoreIgnoresTheBroker:
    @pytest.mark.parametrize("broker", BROKER_STRINGS)
    def test_the_score_is_the_same_whatever_the_broker_says(self, broker):
        assert compute_score(dict(BASE, broker_intelligence=broker)) == compute_score(BASE)

    def test_an_unknown_broker_is_not_penalised_against_a_known_one(self):
        """The failure that mattered: unknown cost 7 points against reliable."""
        known = compute_score(dict(BASE, broker_intelligence="Reliable - completed"))
        unknown = compute_score(dict(BASE, broker_intelligence="Unknown broker"))
        assert known == unknown

    def test_the_field_being_absent_changes_nothing(self):
        with_field = compute_score(dict(BASE, broker_intelligence=""))
        without = compute_score({k: v for k, v in BASE.items()})
        assert with_field == without


class TestRouteRiskIgnoresTheBroker:
    @pytest.mark.parametrize("broker", BROKER_STRINGS)
    def test_no_broker_string_produces_a_risk(self, broker):
        assert compute_route_risk(dict(BASE, broker_intelligence=broker)) == compute_route_risk(BASE)

    def test_an_unfamiliar_broker_is_not_a_hazard(self):
        risk = compute_route_risk(dict(BASE, broker_intelligence="Unknown broker"))
        assert "broker" not in risk.lower()


class TestNoTrustSurvivesAnywhere:
    @pytest.mark.parametrize("broker", BROKER_STRINGS)
    def test_the_whole_result_is_unchanged_by_the_broker(self, broker):
        assert score_load(dict(BASE, broker_intelligence=broker)) == score_load(BASE)

    def test_the_module_holds_no_broker_logic_at_all(self):
        """A grep-level guard: the concept should not reappear by another name."""
        import inspect

        from dispatch import scoring

        source = inspect.getsource(scoring)
        code = "\n".join(
            line for line in source.splitlines()
            if not line.strip().startswith("#")
        )
        assert "broker_intelligence" not in code
        assert "broker_intel" not in code
