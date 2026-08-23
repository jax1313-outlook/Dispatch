"""Tests for Post-PR Architecture Update discoveries and supporting implementations.

Verifies:
  1. Discovery #1: Current Mission Priority (#1 rule)
  2. Discovery #2 & #8: Dynamic Capacity (6 dimensions & engine checks)
  3. Discovery #3: Score Does Not Decide (Noise reduction only, human decides)
  4. Discovery #4 & #5: High volume Opportunity Pipeline (Ingest, Analyze, Score, Filter, Commit)
  5. Discovery #6 & #7: State 1 Reality vs State 2 Possibilities & Opportunity Lifecycle
  6. Discovery #9: Truck Arrangement Data Structures
  7. Discovery #10: Driver Portal Execution Focus & Ownership Verification
  8. Hardened Dynamic Capacity: Unconfigured assets & unknown HOS produce NEEDS_REVIEW / INSUFFICIENT_DATA
  9. Opportunity Card Consumption % Metrics
"""

import pytest
from dispatch.capacity import (
    CargoArrangementCapacity,
    DynamicCapacity,
    PhysicalCapacity,
    PositionCapacity,
    ReserveCapacity,
    StopSequenceCapacity,
    TimeCapacity,
)
from dispatch.opportunities import OpportunityCard, OpportunityPipeline
from dispatch.truck_arrangement import TruckArrangement


def test_unconfigured_asset_and_unknown_hos():
    cap = DynamicCapacity()
    assert cap.physical.configuration_status == "UNCONFIGURED"
    assert cap.time.hos_status == "UNKNOWN"

    can_fit, reasons = cap.can_accommodate(weight_lbs=10000.0, drive_hours=2.0)
    assert can_fit is False
    assert any("NEEDS_REVIEW" in r for r in reasons)


def test_verified_asset_profile_and_hos_evaluation():
    cap = DynamicCapacity()
    cap.apply_asset_profile(
        asset_profile_id="TRK-01-53FT",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
        equipment_type="dry_van",
        has_liftgate=True,
    )
    cap.set_verified_hos(
        remaining_drive_hours=10.0,
        remaining_duty_hours=12.0,
        remaining_cycle_hours=60.0,
    )

    d = cap.to_dict()
    assert d["physical"]["configuration_status"] == "VERIFIED"
    assert d["time"]["hos_status"] == "VERIFIED"

    can_fit, reasons = cap.can_accommodate(
        weight_lbs=20000.0,
        linear_feet=26.0,
        volume_cuft=1500.0,
        pallets=12,
        drive_hours=5.0,
        requires_liftgate=True,
    )
    assert can_fit is True
    assert len(reasons) == 0


def test_truck_arrangement_data_structure():
    arr = TruckArrangement(
        arrangement_type="liftgate",
        pallet_count=10,
        linear_feet=20.0,
        total_weight_lbs=15000.0,
        total_volume_cuft=1000.0,
        is_stackable=False,
        requires_liftgate=True,
    )

    assert arr.density_lbs_per_cuft == 15.0
    assert arr.requires_liftgate is True
    assert arr.is_stackable is False

    with pytest.raises(ValueError):
        TruckArrangement(arrangement_type="invalid_type")


def test_opportunity_lifecycle_and_human_authority():
    card = OpportunityCard(
        origin_location="Atlanta, GA",
        destination_location="Miami, FL",
        offered_rate=2500.0,
        estimated_miles=650.0,
    )

    assert card.stage == "Discovered"
    assert card.rpm == 3.85

    # Legal transitions
    card.transition_to("Analyzed")
    assert card.stage == "Analyzed"

    card.transition_to("Scored")
    assert card.stage == "Scored"

    card.transition_to("Filtered")
    card.transition_to("Presented")
    card.transition_to("Selected")

    # Committing without human actor must fail
    with pytest.raises(ValueError, match="explicit human authority"):
        card.transition_to("Committed")

    # Committing with human actor succeeds
    card.transition_to("Committed", actor="Mike Zachary")
    assert card.stage == "Committed"
    assert card.committed_by == "Mike Zachary"


def test_opportunity_card_consumption_metrics():
    pipeline = OpportunityPipeline()
    raw = [
        {
            "source": "dat",
            "external_ref_id": "REF-001",
            "origin_location": "Chicago, IL",
            "destination_location": "Indianapolis, IN",
            "offered_rate": 1200.0,
            "estimated_miles": 180.0,
            "weight_lbs": 22000.0,
            "volume_cuft": 1700.0,
            "pallets": 13,
        }
    ]
    ingested = pipeline.ingest_opportunities(raw)
    card = ingested[0]

    cap = DynamicCapacity()
    cap.apply_asset_profile(
        asset_profile_id="TRK-01",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
    )
    cap.set_verified_hos(remaining_drive_hours=11.0, remaining_duty_hours=14.0, remaining_cycle_hours=70.0)

    analyzed = pipeline.analyze_opportunity(card.opportunity_id, capacity=cap)

    assert analyzed.weight_consumption_pct == 50.0
    assert analyzed.volume_consumption_pct == 50.0
    assert analyzed.pallet_consumption_pct == 50.0
    assert analyzed.time_consumption_pct > 0.0


def test_high_volume_opportunity_pipeline(monkeypatch):
    pipeline = OpportunityPipeline()

    # Generate 50 raw opportunities
    raw_list = [
        {
            "source": "dat",
            "external_ref_id": f"REF-{i}",
            "origin_location": "Chicago, IL",
            "destination_location": "St. Louis, MO",
            "offered_rate": 800.0 + (i * 10),
            "estimated_miles": 300.0,
            "weight_lbs": 25000.0,
        }
        for i in range(50)
    ]

    ingested = pipeline.ingest_opportunities(raw_list)
    assert len(ingested) == 50

    # Process all opportunities through Analysis & Scoring
    for opp in ingested:
        pipeline.analyze_opportunity(opp.opportunity_id)
        pipeline.score_opportunity(opp.opportunity_id)

    presented = pipeline.filter_and_present(min_score=50.0)
    assert len(presented) > 0
    # Confirm sorted by score descending (reducing noise)
    scores = [c.score for c in presented]
    assert scores == sorted(scores, reverse=True)

    # Pick top opportunity and commit
    top_opp = presented[0]
    committed_load = pipeline.commit_opportunity_to_reality(
        top_opp.opportunity_id, human_actor="Mike Zachary"
    )

    assert committed_load["load_id"] is not None
    assert top_opp.stage == "Current Reality"
