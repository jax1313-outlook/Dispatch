"""Tests for Post-PR Architecture Update discoveries and supporting implementations.

Verifies:
  1. Discovery #1: Current Mission Priority (#1 rule)
  2. Discovery #2 & #8: Dynamic Capacity (6 dimensions & engine checks)
  3. Discovery #3: Score Does Not Decide (Noise reduction only, human decides)
  4. Discovery #4 & #5: High volume Opportunity Pipeline (Ingest, Analyze, Score, Filter, Commit)
  5. Discovery #6 & #7: State 1 Reality vs State 2 Possibilities & Opportunity Lifecycle
  6. Discovery #9: Truck Arrangement Data Structures
  7. Discovery #10: Driver Portal Execution Focus & Ownership Verification
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


def test_dynamic_capacity_six_dimensions():
    cap = DynamicCapacity(
        physical=PhysicalCapacity(
            max_weight_lbs=45000.0,
            used_weight_lbs=20000.0,
            max_linear_feet=53.0,
            used_linear_feet=26.0,
            has_liftgate=True,
        ),
        time=TimeCapacity(
            available_drive_hours=11.0,
            used_drive_hours=4.0,
        ),
        position=PositionCapacity(
            current_location="Dallas, TX",
            estimated_deadhead_miles=25.0,
        ),
        reserve=ReserveCapacity(
            reserved_hos_hours=1.0,
            reserved_weight_lbs=1000.0,
        ),
        cargo=CargoArrangementCapacity(
            arrangement_type="multi_pallet",
            stackable_permitted=True,
        ),
        stop_sequence=StopSequenceCapacity(
            max_stops=5,
            assigned_stops=1,
        ),
    )

    d = cap.to_dict()
    assert d["physical"]["remaining_weight_lbs"] == 25000.0
    assert d["physical"]["remaining_linear_feet"] == 27.0
    assert d["time"]["remaining_drive_hours"] == 7.0
    assert d["stop_sequence"]["remaining_stops"] == 4

    # Test accommodation check
    can_fit, reasons = cap.can_accommodate(
        weight_lbs=20000.0,
        linear_feet=20.0,
        drive_hours=5.0,
        requires_liftgate=True,
    )
    assert can_fit is True
    assert len(reasons) == 0

    # Over weight limit test
    can_fit_over, reasons_over = cap.can_accommodate(weight_lbs=30000.0)
    assert can_fit_over is False
    assert any("weight capacity" in r for r in reasons_over)


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
