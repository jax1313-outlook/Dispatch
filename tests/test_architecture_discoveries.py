"""Tests for Post-PR Architecture Update discoveries and supporting implementations.

Verifies:
  1. Discovery #1: Current Mission Priority (#1 rule)
  2. Discovery #2 & #8: Dynamic Capacity (6 dimensions & engine checks)
  3. Discovery #3: Score Does Not Decide (Noise reduction only, human decides)
  4. Discovery #4 & #5: High volume Opportunity Pipeline (Ingest, Analyze, Score, Filter, Commit)
  5. Discovery #6 & #7: State 1 Reality vs State 2 Possibilities & Opportunity Lifecycle
  6. Discovery #9: Truck Arrangement Data Structures
  7. Discovery #10: Driver Portal Execution Focus & Ownership Verification
  8. Hardened Dynamic Capacity: unconfigured assets, unknown HOS and unrecorded cargo
     produce structured refusals instead of optimistic answers
  9. Opportunity Card Consumption % Metrics
"""

import dataclasses

import pytest

from dispatch import db
from dispatch.capacity import (
    CargoArrangementCapacity,
    DynamicCapacity,
    PhysicalCapacity,
    PositionCapacity,
    ReserveCapacity,
    StopSequenceCapacity,
    TimeCapacity,
)
from dispatch.opportunities import (
    LifecycleAuthorityError,
    OpportunityCard,
    OpportunityPipeline,
)
from dispatch.truck_arrangement import TruckArrangement

OBSERVED_AT = "2026-08-23T12:00:00Z"


@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path, monkeypatch):
    """Spine work items and loads live in dispatch.db; keep this file's writes
    in a per-test temp database rather than a developer's live one."""
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


def _configured_capacity(**profile_overrides) -> DynamicCapacity:
    """A fully attested asset: verified spec, verified HOS, recorded cargo policy."""
    cap = DynamicCapacity()
    profile = {
        "asset_profile_id": "TRK-01",
        "max_weight_lbs": 44000.0,
        "max_volume_cuft": 3400.0,
        "max_linear_feet": 53.0,
        "max_pallets": 26,
        "source": "OEM_SPEC_SHEET",
        "verified_by": "Fleet Manager",
    }
    profile.update(profile_overrides)
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


def test_unconfigured_asset_and_unknown_hos():
    cap = DynamicCapacity()
    assert cap.physical.configuration_status == "UNCONFIGURED"
    assert cap.time.hos_status == "UNKNOWN"
    before = cap.to_dict()

    result = cap.can_accommodate(weight_lbs=10000.0, drive_hours=2.0)

    # An unconfigured asset cannot produce a fit answer at all: the engine says
    # "unknown", never "does not fit", because the load may well fit fine.
    assert result.data_sufficient is False
    assert result.status == "INSUFFICIENT_DATA"
    assert result.physical_fit is None
    assert result.baseline_fit is None
    assert result.exceeds_total_capacity is False
    assert result.requires_human_review is True
    assert result.clear_to_proceed is False
    assert "ASSET_CONFIGURATION_UNUSABLE" in result.codes
    assert "HOS_STATE_UNUSABLE" in result.codes
    # Evaluation is advisory and read-only.
    assert cap.to_dict() == before


def test_insufficient_data_findings_when_metrics_missing():
    cap = DynamicCapacity()
    # Partially configured physical status
    cap.physical.configuration_status = "PARTIAL"
    cap.physical.max_weight_lbs = 0.0
    before = cap.to_dict()

    result = cap.can_accommodate(weight_lbs=5000.0)

    assert result.data_sufficient is False
    assert "INSUFFICIENT_DATA_WEIGHT" in result.codes
    assert "ASSET_CONFIGURATION_UNVERIFIED" in result.codes
    # The missing max is named by its source reference, not buried in prose.
    gap = result.findings_for("INSUFFICIENT_DATA_WEIGHT")[0]
    assert gap.source_ref == "physical.max_weight_lbs"
    assert gap.data_gap is True
    assert result.reserve_impacts["weight"].evaluated is False
    assert result.reserve_impacts["weight"].status == "NOT_EVALUATED"
    assert cap.to_dict() == before


def test_stale_hos_handling_in_simulation_vs_current_reality():
    cap = _configured_capacity()
    cap.time.remaining_drive_hours = 8.0
    cap.time.hos_status = "STALE"
    before = cap.to_dict()

    # Current Reality evaluation escalates the stale snapshot to a human.
    current = cap.can_accommodate(drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE", is_simulation=False)
    assert "HOS_SNAPSHOT_STALE" in current.codes
    assert current.findings_for("HOS_SNAPSHOT_STALE")[0].requires_human_review is True
    assert current.clear_to_proceed is False
    assert current.status == "REQUIRES_HUMAN_REVIEW"

    # Possible Future / simulation accepts the stale snapshot as a stated
    # premise -- but still records that the premise was stale.
    simulated = cap.can_accommodate(drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE", is_simulation=True)
    assert simulated.clear_to_proceed is True
    assert simulated.is_simulation is True
    assert "HOS_SNAPSHOT_STALE" in simulated.codes
    assert simulated.findings_for("HOS_SNAPSHOT_STALE")[0].requires_human_review is False

    assert cap.to_dict() == before


def test_stacking_and_top_load_policies():
    cap = _configured_capacity()
    before = cap.to_dict()

    # Unrecorded stacking policy is a data gap, never an assumption of STACKABLE.
    unknown = cap.can_accommodate(stacking_policy="UNKNOWN")
    assert unknown.clear_to_proceed is False
    assert "CARGO_STACKING_POLICY_UNKNOWN" in unknown.codes
    assert unknown.findings_for("CARGO_STACKING_POLICY_UNKNOWN")[0].data_gap is True
    assert unknown.data_sufficient is False

    # An arrangement whose top-load policy was never recorded also refuses.
    cap.cargo.allows_top_load = None
    unrecorded = cap.can_accommodate(stacking_policy="TOP_LOAD")
    assert unrecorded.clear_to_proceed is False
    assert "CARGO_TOP_LOAD_POLICY_UNKNOWN" in unrecorded.codes

    # A recorded refusal blocks outright.
    cap.cargo.allows_top_load = False
    forbidden = cap.can_accommodate(stacking_policy="TOP_LOAD")
    assert forbidden.clear_to_proceed is False
    assert "CARGO_TOP_LOAD_FORBIDDEN" in forbidden.codes
    assert forbidden.findings_for("CARGO_TOP_LOAD_FORBIDDEN")[0].severity == "BLOCKING"

    cap.cargo.allows_top_load = True
    assert cap.to_dict() == before


def test_verified_asset_profile_and_hos_evaluation():
    cap = DynamicCapacity()
    cap.apply_asset_profile(
        asset_profile_id="TRK-01-53FT",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
        source="OEM_SPEC_SHEET",
        verified_by="Fleet Manager",
        equipment_type="dry_van",
        has_liftgate=True,
    )
    cap.set_verified_hos(
        remaining_drive_hours=10.0,
        remaining_duty_hours=12.0,
        remaining_cycle_hours=60.0,
        source="ELD:Samsara",
        observed_at=OBSERVED_AT,
    )
    cap.cargo.stacking_policy = "STACKABLE"
    cap.cargo.allows_top_load = True

    d = cap.to_dict()
    assert d["physical"]["configuration_status"] == "VERIFIED"
    assert d["physical"]["configuration_verified_by"] == "Fleet Manager"
    assert d["time"]["hos_status"] == "VERIFIED"
    assert d["time"]["hos_source"] == "ELD:Samsara"

    result = cap.can_accommodate(
        weight_lbs=20000.0,
        linear_feet=26.0,
        volume_cuft=1500.0,
        pallets=12,
        drive_hours=5.0,
        service_hours=2.0,
        requires_liftgate=True,
        stacking_policy="STACKABLE",
    )
    assert result.status == "FITS_WITHIN_BASELINE"
    assert result.physical_fit is True
    assert result.baseline_fit is True
    assert result.reserve_required is False
    assert result.data_sufficient is True
    assert result.requires_human_review is False
    assert result.clear_to_proceed is True
    assert result.blocking_findings == []
    # Every requested dimension was actually compared, not merely computed.
    for dimension in ("weight", "linear_feet", "volume", "pallets", "drive_hours", "duty_hours", "cycle_hours"):
        assert result.reserve_impacts[dimension].evaluated is True


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
    assert arr.evaluate_arrangement().stackability_status == "NON_STACKABLE"

    with pytest.raises(ValueError):
        TruckArrangement(arrangement_type="invalid_type")

    # An arrangement nobody described claims nothing: unknown type, unknown
    # stackability, unverified securement.
    blank = TruckArrangement()
    assert blank.arrangement_type == "unknown"
    assert blank.is_stackable is None
    assert blank.securement_status == "UNVERIFIED"
    blank_assessment = blank.evaluate_arrangement()
    assert blank_assessment.stackability_status == "UNKNOWN"
    assert blank_assessment.arrangement_status == "UNKNOWN"


def test_opportunity_lifecycle_is_spine_authoritative_and_needs_a_human():
    """CF-04: Opportunity recommends, Spine owns the lifecycle, a person decides."""
    pipeline = OpportunityPipeline()
    card = pipeline.ingest_opportunities(
        [
            {
                "origin_location": "Atlanta, GA",
                "destination_location": "Miami, FL",
                "offered_rate": 2500.0,
                "estimated_miles": 650.0,
            }
        ]
    )[0]

    assert card.rpm == 3.85
    # The competing lifecycle authority is gone: no stored stage, no local
    # transition guard. Stage is read through the Spine correlation.
    field_names = {f.name for f in dataclasses.fields(OpportunityCard)}
    assert "stage" not in field_names
    assert not hasattr(OpportunityCard, "transition_to")
    assert card.work_item_id
    assert card.stage == "CREATED"

    pipeline.analyze_opportunity(card.opportunity_id)
    assert card.stage == "VALIDATED"

    pipeline.score_opportunity(card.opportunity_id)
    assert card.stage == "SCORED"

    presented = pipeline.present(min_score=0.0)
    assert card in presented
    assert card.stage == "WAITING_FOR_MIKE"

    # Committing without a named human is refused, and nothing moves.
    with pytest.raises(LifecycleAuthorityError):
        pipeline.request_commitment(card.opportunity_id, "")
    assert card.stage == "WAITING_FOR_MIKE"

    # A machine identity cannot stand in for the person either.
    with pytest.raises(LifecycleAuthorityError):
        pipeline.request_commitment(card.opportunity_id, "AUTOMATION")
    assert card.stage == "WAITING_FOR_MIKE"


def test_opportunity_commitment_is_approved_by_a_human_and_realised_by_spine():
    """Opportunity asks, a named person approves, Spine creates the load."""
    pipeline = OpportunityPipeline()
    card = pipeline.ingest_opportunities(
        [
            {
                "origin_location": "Atlanta, GA",
                "destination_location": "Miami, FL",
                "offered_rate": 2500.0,
                "estimated_miles": 650.0,
            }
        ]
    )[0]
    pipeline.analyze_opportunity(card.opportunity_id)
    pipeline.score_opportunity(card.opportunity_id)
    pipeline.present(min_score=0.0)

    pipeline.request_commitment(card.opportunity_id, "Mike Zachary")
    assert card.stage == "MIKE_APPROVED"

    load = pipeline.realize_commitment(card.opportunity_id, actor_id="Mike Zachary")
    assert load["load_id"]
    assert card.linked_load_id == load["load_id"]


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

    cap = _configured_capacity()
    used_before = dict(
        weight=cap.physical.used_weight_lbs,
        volume=cap.physical.used_volume_cuft,
        pallets=cap.physical.used_pallets,
    )

    analyzed = pipeline.analyze_opportunity(card.opportunity_id, capacity=cap)

    assert analyzed.weight_consumption_pct == 50.0
    assert analyzed.volume_consumption_pct == 50.0
    assert analyzed.pallet_consumption_pct == 50.0
    assert analyzed.time_consumption_pct > 0.0
    # Analysing a Possible Future must not consume Current Reality's capacity.
    assert cap.physical.used_weight_lbs == used_before["weight"]
    assert cap.physical.used_volume_cuft == used_before["volume"]
    assert cap.physical.used_pallets == used_before["pallets"]


def test_high_volume_opportunity_pipeline():
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

    # The shortlist is put in front of a person and stops there: presentation
    # is where the pipeline's authority ends. Commitment and realisation are
    # covered by test_opportunity_commitment_is_approved_by_a_human_and_realised_by_spine.
    top_opp = presented[0]
    assert top_opp.stage == "WAITING_FOR_MIKE"
    assert top_opp.linked_load_id == ""
