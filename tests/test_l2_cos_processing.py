"""Tests for the L2-COS Processing Layer (rule aggregation + overall score)."""

from __future__ import annotations

from l2_cos import processing


def test_process_runs_all_six_modules(clean_load, clean_broker, clean_facility):
    intelligence = processing.process(
        clean_load, facility_pickup=clean_facility, facility_delivery=clean_facility, broker=clean_broker
    )
    assert set(intelligence) == {
        "lane_fit",
        "rate_anomaly",
        "facility_risk",
        "broker_risk",
        "capacity_match",
        "deadhead_cost",
    }
    for result in intelligence.values():
        assert "score" in result and "flags" in result and "findings" in result


def test_all_flags_flattens_every_module(clean_load, clean_broker):
    intelligence = processing.process(clean_load, broker=clean_broker)
    flags = processing.all_flags(intelligence)
    assert "preferred_lane_match" in flags
    assert "rate_in_band" in flags
    assert len(flags) >= 6


def test_overall_score_is_mean_rounded(clean_load, clean_broker):
    intelligence = processing.process(clean_load, broker=clean_broker)
    scores = [r["score"] for r in intelligence.values()]
    assert processing.overall_score(intelligence) == round(sum(scores) / len(scores))


def test_overall_score_empty_intelligence():
    assert processing.overall_score({}) == 0


def test_clean_load_is_publisher_eligible(clean_load, clean_broker, clean_facility):
    from l2_cos.models.intelligence import PUBLISH_THRESHOLD

    intelligence = processing.process(
        clean_load, facility_pickup=clean_facility, facility_delivery=clean_facility, broker=clean_broker
    )
    assert processing.overall_score(intelligence) >= PUBLISH_THRESHOLD


def test_risky_load_is_not_publisher_eligible(risky_load, risky_broker):
    from l2_cos.models.intelligence import PUBLISH_THRESHOLD

    intelligence = processing.process(risky_load, broker=risky_broker)
    assert processing.overall_score(intelligence) < PUBLISH_THRESHOLD
