"""Tests for the L2-COS state model lock and intelligence-library models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from l2_cos.models import (
    PUBLISH_THRESHOLD,
    BrokerIntelligence,
    InquiryArtifacts,
    IntelligenceScore,
    LifecycleStage,
    Load,
    LocationIntelligence,
    can_transition,
    next_stages,
)

FULL_PATH = [
    LifecycleStage.BOOKED,
    LifecycleStage.PLANNED,
    LifecycleStage.EN_ROUTE,
    LifecycleStage.AT_PICKUP,
    LifecycleStage.LOADED,
    LifecycleStage.IN_TRANSIT,
    LifecycleStage.AT_DELIVERY,
    LifecycleStage.DELIVERED,
    LifecycleStage.INVOICED,
    LifecycleStage.CLOSED,
]


def test_eleven_stages_locked():
    assert [s.value for s in LifecycleStage] == [
        "AVAILABLE",
        "BOOKED",
        "PLANNED",
        "EN_ROUTE",
        "AT_PICKUP",
        "LOADED",
        "IN_TRANSIT",
        "AT_DELIVERY",
        "DELIVERED",
        "INVOICED",
        "CLOSED",
    ]


def test_load_advances_through_full_lifecycle():
    load = Load(load_id="L-1")
    assert load.stage == LifecycleStage.AVAILABLE

    for target in FULL_PATH:
        load.advance(target, actor="dispatcher-1")

    assert load.stage == LifecycleStage.CLOSED
    assert [event.stage for event in load.history] == FULL_PATH
    assert next_stages(LifecycleStage.CLOSED) == ()


def test_stages_cannot_be_skipped_or_reversed():
    load = Load(load_id="L-2")
    with pytest.raises(ValueError):
        load.advance(LifecycleStage.LOADED, actor="dispatcher-1")  # skip ahead

    load.advance(LifecycleStage.BOOKED, actor="dispatcher-1")
    with pytest.raises(ValueError):
        load.advance(LifecycleStage.AVAILABLE, actor="dispatcher-1")  # reverse

    assert load.stage == LifecycleStage.BOOKED  # unchanged after rejected transitions


def test_can_transition_helper():
    assert can_transition(LifecycleStage.AVAILABLE, LifecycleStage.BOOKED)
    assert not can_transition(LifecycleStage.AVAILABLE, LifecycleStage.PLANNED)


def test_intelligence_score_publisher_threshold():
    below = IntelligenceScore(module="lane_fit", version="1.0.0", score=PUBLISH_THRESHOLD - 1)
    at = IntelligenceScore(module="lane_fit", version="1.0.0", score=PUBLISH_THRESHOLD)
    assert not below.publisher_eligible
    assert at.publisher_eligible


def test_intelligence_score_bounds_enforced():
    with pytest.raises(ValidationError):
        IntelligenceScore(module="lane_fit", version="1.0.0", score=101)


def test_inquiry_artifacts_completeness():
    artifacts = InquiryArtifacts()
    assert not artifacts.is_complete()
    complete = InquiryArtifacts(
        business_card=True,
        w9=True,
        insurance=True,
        authority=True,
        rate_sheet=True,
        terms=True,
        rate_confirmation_package=True,
    )
    assert complete.is_complete()


def test_location_and_broker_intelligence_capture_once():
    facility = LocationIntelligence(
        facility_id="FAC-1",
        name="Riverside DC",
        address="1 Dock Rd, Riverside, CA",
        historical_problems=["late gate opens on Fridays"],
    )
    broker = BrokerIntelligence(
        broker_id="BRK-1",
        company_name="Acme Logistics",
        preferred_lanes=["CA-TX"],
        historical_rates={"CA-TX": 2.15},
    )
    assert facility.facility_id == "FAC-1"
    assert broker.historical_rates["CA-TX"] == 2.15
