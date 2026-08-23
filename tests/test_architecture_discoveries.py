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
  10. Seven-Capability Architecture Objects (CapacityState, CapacityDataMetadata, DynamicCapacityEvaluation, project_capacity, CargoUnit, CargoPosition, ArrangementPlan, StopRecord, StopSequenceEvaluation)
"""

import pytest
from dispatch.capacity import (
    CapacityDataMetadata,
    CapacityState,
    CargoArrangementCapacity,
    DynamicCapacity,
    DynamicCapacityEvaluation,
    PhysicalCapacity,
    PositionCapacity,
    ReserveCapacity,
    StopRecord,
    StopSequenceCapacity,
    StopSequenceEvaluation,
    TimeCapacity,
)
from dispatch.opportunities import OpportunityCard, OpportunityPipeline
from dispatch.truck_arrangement import (
    ArrangementPlan,
    CargoPosition,
    CargoUnit,
    TruckArrangement,
)


def test_capacity_state_serialization():
    assert CapacityState.CURRENT_REALITY.value == "CURRENT_REALITY"
    assert CapacityState.POSSIBLE_FUTURE.value == "POSSIBLE_FUTURE"

    cap = DynamicCapacity(state_type=CapacityState.CURRENT_REALITY)
    d = cap.to_dict()
    assert d["state_type"] == "CURRENT_REALITY"


def test_capacity_state_invalid_value():
    with pytest.raises(ValueError, match="Invalid state_type"):
        DynamicCapacity(state_type="INVALID_STATE")


def test_projection_is_possible_future():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)
    proj = cap.project_capacity(weight_lbs=10000.0, drive_hours=2.0)
    assert proj.state_type == CapacityState.POSSIBLE_FUTURE.value


def test_simulation_cannot_create_current_reality():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)
    eval_res = cap.evaluate_capacity(weight_lbs=10000.0)
    assert eval_res.state_type == CapacityState.POSSIBLE_FUTURE.value
    # Base snapshot remains CURRENT_REALITY
    assert cap.state_type == CapacityState.CURRENT_REALITY.value


def test_snapshot_has_unique_identity():
    cap = DynamicCapacity()
    proj = cap.project_capacity(weight_lbs=5000.0)
    assert cap.snapshot_id != proj.snapshot_id


def test_projected_snapshot_references_source():
    cap = DynamicCapacity()
    proj = cap.project_capacity(weight_lbs=5000.0)
    assert proj.based_on_snapshot_id == cap.snapshot_id
    assert proj.previous_snapshot_id == cap.snapshot_id


def test_multiple_scenarios_reference_same_reality():
    cap = DynamicCapacity()
    proj1 = cap.project_capacity(weight_lbs=5000.0, scenario_id="SCENARIO-A")
    proj2 = cap.project_capacity(weight_lbs=12000.0, scenario_id="SCENARIO-B")

    assert proj1.snapshot_id != proj2.snapshot_id
    assert proj1.based_on_snapshot_id == cap.snapshot_id
    assert proj2.based_on_snapshot_id == cap.snapshot_id


def test_snapshot_lineage_serialization():
    cap = DynamicCapacity(current_mission_id="MISSION-101", committed_load_ids=["LOAD-1", "LOAD-2"])
    d = cap.to_dict()
    assert d["current_mission_id"] == "MISSION-101"
    assert d["committed_load_ids"] == ["LOAD-1", "LOAD-2"]


def test_dynamic_capacity_evaluation_structure():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)
    cap.set_verified_hos(11.0, 14.0, 70.0)

    eval_res = cap.evaluate_capacity(weight_lbs=20000.0, drive_hours=4.0)
    assert eval_res.overall_status == "FITS_WITHIN_BASELINE"
    assert eval_res.verified_fit is True


def test_evaluation_serialization():
    eval_res = DynamicCapacityEvaluation(
        capacity_snapshot_id="CAP-123",
        opportunity_id="OPP-999",
        overall_status="CONSUMES_RESERVE",
    )
    d = eval_res.to_dict()
    assert d["capacity_snapshot_id"] == "CAP-123"
    assert d["overall_status"] == "CONSUMES_RESERVE"


def test_insufficient_data_differs_from_exceeded_capacity():
    # Partially configured asset missing weight limit produces INSUFFICIENT_DATA
    cap_partial = DynamicCapacity()
    cap_partial.physical.configuration_status = "PARTIAL"
    cap_partial.physical.max_weight_lbs = 0.0
    eval_res_unconf = cap_partial.evaluate_capacity(weight_lbs=10000.0)
    assert eval_res_unconf.overall_status == "INSUFFICIENT_DATA"

    # Configured asset with excessive weight produces EXCEEDS_CAPACITY
    cap_conf = DynamicCapacity()
    cap_conf.apply_asset_profile("TRK-01", 40000, 3400, 53, 26)
    cap_conf.set_verified_hos(11.0, 14.0, 70.0)
    eval_res_exceed = cap_conf.evaluate_capacity(weight_lbs=50000.0)
    assert eval_res_exceed.overall_status == "EXCEEDS_CAPACITY"


def test_reserve_consumption_differs_from_baseline_fit():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 40000, 3400, 53, 26)
    cap.set_verified_hos(11.0, 14.0, 70.0)

    # Max effective weight is 40000 - 1000 reserved = 39000
    eval_baseline = cap.evaluate_capacity(weight_lbs=30000.0)
    assert eval_baseline.overall_status == "FITS_WITHIN_BASELINE"

    eval_reserve = cap.evaluate_capacity(weight_lbs=39500.0)
    assert eval_reserve.overall_status == "CONSUMES_RESERVE"


def test_evaluation_contains_no_decision_authority():
    with pytest.raises(ValueError, match="Invalid overall_status"):
        DynamicCapacityEvaluation(overall_status="APPROVED")

    with pytest.raises(ValueError, match="Invalid overall_status"):
        DynamicCapacityEvaluation(overall_status="REJECTED")


def test_projection_does_not_mutate_current_reality():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)
    cap.set_verified_hos(11.0, 14.0, 70.0)

    dict_before = cap.to_dict()
    proj = cap.project_capacity(weight_lbs=15000.0, drive_hours=3.0)
    dict_after = cap.to_dict()

    assert dict_before == dict_after
    assert proj.physical.used_weight_lbs == 15000.0


def test_projection_has_new_snapshot_id():
    cap = DynamicCapacity()
    proj = cap.project_capacity(weight_lbs=5000.0)
    assert proj.snapshot_id != cap.snapshot_id


def test_projection_references_source_snapshot():
    cap = DynamicCapacity()
    proj = cap.project_capacity(weight_lbs=5000.0)
    assert proj.based_on_snapshot_id == cap.snapshot_id


def test_projection_calculates_remaining_capacity():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 40000, 3000, 50, 20)
    proj = cap.project_capacity(weight_lbs=10000.0, linear_feet=10.0)
    assert proj.physical.remaining_weight_lbs == 30000.0
    assert proj.physical.remaining_linear_feet == 40.0


def test_projection_creates_no_calendar_event():
    pipeline = OpportunityPipeline()
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)

    # Opportunity analysis/projection does not mutate state or create calendar events
    raw = [{"source": "test", "offered_rate": 1000.0, "estimated_miles": 200.0, "weight_lbs": 10000.0}]
    ingested = pipeline.ingest_opportunities(raw)
    card = ingested[0]
    analyzed = pipeline.analyze_opportunity(card.opportunity_id, capacity=cap)

    assert analyzed.stage == "Analyzed"
    assert card.linked_load_id == ""


def test_multiple_projections_share_one_source():
    cap = DynamicCapacity()
    p1 = cap.project_capacity(weight_lbs=5000.0)
    p2 = cap.project_capacity(weight_lbs=8000.0)

    assert p1.based_on_snapshot_id == cap.snapshot_id
    assert p2.based_on_snapshot_id == cap.snapshot_id
    assert p1.snapshot_id != p2.snapshot_id


def test_metadata_exists_on_all_six_dimensions():
    cap = DynamicCapacity()
    assert isinstance(cap.physical.metadata, CapacityDataMetadata)
    assert isinstance(cap.time.metadata, CapacityDataMetadata)
    assert isinstance(cap.position.metadata, CapacityDataMetadata)
    assert isinstance(cap.reserve.metadata, CapacityDataMetadata)
    assert isinstance(cap.cargo.metadata, CapacityDataMetadata)
    assert isinstance(cap.stop_sequence.metadata, CapacityDataMetadata)


def test_dimension_metadata_serialization():
    meta = CapacityDataMetadata(
        source_type="ELD",
        observed_at="2025-01-01T12:00:00Z",
        freshness_status="CURRENT",
    )
    d = meta.to_dict()
    assert d["source_type"] == "ELD"
    assert d["freshness_status"] == "CURRENT"


def test_stale_dimension_metadata_requires_review():
    cap = DynamicCapacity()
    cap.apply_asset_profile("TRK-01", 44000, 3400, 53, 26)
    cap.time.metadata.freshness_status = "STALE"
    cap.time.hos_status = "STALE"

    can_fit, reasons = cap.can_accommodate(drive_hours=2.0, is_simulation=False)
    assert any("NEEDS_REVIEW" in r for r in reasons)


def test_unknown_source_remains_unknown():
    meta = CapacityDataMetadata()
    assert meta.source_type == "UNKNOWN"
    assert meta.freshness_status == "UNKNOWN"


def test_dimensions_can_have_different_freshness():
    cap = DynamicCapacity()
    cap.physical.metadata.freshness_status = "CURRENT"
    cap.time.metadata.freshness_status = "STALE"

    assert cap.physical.metadata.freshness_status == "CURRENT"
    assert cap.time.metadata.freshness_status == "STALE"


def test_multiple_cargo_units_remain_distinct():
    u1 = CargoUnit(description="Pallet of Electronics", weight_lbs=1200.0)
    u2 = CargoUnit(description="Pallet of Paper", weight_lbs=800.0)

    assert u1.cargo_unit_id != u2.cargo_unit_id
    assert u1.description != u2.description


def test_cargo_positions_remain_distinct():
    p1 = CargoPosition(cargo_unit_id="U1", cargo_zone="nose", longitudinal_position=4.0)
    p2 = CargoPosition(cargo_unit_id="U2", cargo_zone="tail", longitudinal_position=48.0)

    assert p1.position_id != p2.position_id
    assert p1.cargo_zone != p2.cargo_zone


def test_cargo_stop_assignments():
    u = CargoUnit(pickup_stop_id="STOP-01", delivery_stop_id="STOP-02")
    assert u.pickup_stop_id == "STOP-01"
    assert u.delivery_stop_id == "STOP-02"


def test_loading_and_unloading_order_are_distinct():
    plan = ArrangementPlan(
        loading_order=["UNIT-1", "UNIT-2"],
        unloading_order=["UNIT-2", "UNIT-1"],
    )
    assert plan.loading_order != plan.unloading_order


def test_cargo_blocking_relationships():
    pos2 = CargoPosition(blocked_by_position_ids=["POS-1"])
    assert "POS-1" in pos2.blocked_by_position_ids


def test_unknown_cargo_dimensions_remain_unknown():
    u = CargoUnit(length_inches=0, width_inches=0, height_inches=0)
    assert u.volume_cuft == 0.0


def test_arrangement_plan_serialization():
    u = CargoUnit(description="Test Unit", weight_lbs=500.0)
    plan = ArrangementPlan(cargo_units=[u])
    d = plan.to_dict()

    assert len(d["cargo_units"]) == 1
    assert d["cargo_units"][0]["description"] == "Test Unit"


def test_stop_count_fits_but_access_sequence_fails():
    seq_cap = StopSequenceCapacity(max_stops=5, assigned_stops=2)
    s1 = StopRecord(sequence_number=1, findings=["CARGO_BLOCKING: Cargo for Stop 2 blocks access to Stop 1"])

    eval_res = seq_cap.evaluate_sequence([s1])
    assert eval_res.stop_count_status == "STOP_COUNT_FITS"
    assert eval_res.requires_human_review is True
    assert len(eval_res.cargo_blocking_findings) > 0


def test_stop_count_fits_but_appointment_sequence_fails():
    seq_cap = StopSequenceCapacity(max_stops=5)
    s1 = StopRecord(appointment_start="2025-01-01T14:00:00Z", appointment_end="2025-01-01T15:00:00Z")
    s2 = StopRecord(appointment_start="2025-01-01T10:00:00Z", appointment_end="2025-01-01T11:00:00Z")

    eval_res = seq_cap.evaluate_sequence([s1, s2])
    assert eval_res.stop_count_status == "STOP_COUNT_FITS"
    assert eval_res.appointment_status == "APPOINTMENT_CONFLICT"
    assert eval_res.overall_status == "SEQUENCE_INFEASIBLE"


def test_cargo_blocking_detected():
    s = StopRecord(findings=["BLOCKING_DETECTED"])
    seq_cap = StopSequenceCapacity()
    eval_res = seq_cap.evaluate_sequence([s])
    assert "BLOCKING_DETECTED" in eval_res.cargo_blocking_findings


def test_added_stop_changes_drive_time():
    s = StopRecord(drive_time_impact=1.5)
    seq_cap = StopSequenceCapacity()
    eval_res = seq_cap.evaluate_sequence([s])
    assert eval_res.added_drive_time == 1.5


def test_added_stop_changes_duty_time():
    s = StopRecord(duty_time_impact=0.5, service_time_minutes=30.0)
    seq_cap = StopSequenceCapacity()
    eval_res = seq_cap.evaluate_sequence([s])
    assert eval_res.added_duty_time == 1.0


def test_stop_projection_does_not_mutate_reality():
    seq_cap = StopSequenceCapacity(max_stops=5, assigned_stops=1)
    s = StopRecord(drive_time_impact=2.0)
    eval_res = seq_cap.evaluate_sequence([s])

    assert eval_res.state_type == CapacityState.POSSIBLE_FUTURE.value
    assert seq_cap.assigned_stops == 1


def test_stop_sequence_evaluation_serialization():
    s = StopRecord(location="Chicago, IL")
    eval_res = StopSequenceEvaluation(stops=[s])
    d = eval_res.to_dict()

    assert len(d["stops"]) == 1
    assert d["stops"][0]["location"] == "Chicago, IL"


def test_unconfigured_asset_and_unknown_hos():
    cap = DynamicCapacity()
    assert cap.physical.configuration_status == "UNCONFIGURED"
    assert cap.time.hos_status == "UNKNOWN"

    can_fit, reasons = cap.can_accommodate(weight_lbs=10000.0, drive_hours=2.0)
    assert can_fit is False
    assert any("NEEDS_REVIEW" in r for r in reasons)


def test_insufficient_data_findings_when_metrics_missing():
    cap = DynamicCapacity()
    cap.physical.configuration_status = "PARTIAL"
    cap.physical.max_weight_lbs = 0.0

    can_fit, reasons = cap.can_accommodate(weight_lbs=5000.0)
    assert can_fit is False
    assert any("INSUFFICIENT_DATA" in r for r in reasons)


def test_stale_hos_handling_in_simulation_vs_current_reality():
    cap = DynamicCapacity()
    cap.apply_asset_profile(
        asset_profile_id="TRK-01",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
    )
    cap.time.remaining_drive_hours = 8.0
    cap.time.hos_status = "STALE"

    can_fit_cr, reasons_cr = cap.can_accommodate(drive_hours=4.0, is_simulation=False)
    assert any("NEEDS_REVIEW: Driver HOS snapshot is stale" in r for r in reasons_cr)

    can_fit_sim, reasons_sim = cap.can_accommodate(drive_hours=4.0, is_simulation=True)
    assert can_fit_sim is True


def test_stacking_and_top_load_policies():
    cap = DynamicCapacity()
    cap.apply_asset_profile(
        asset_profile_id="TRK-01",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
    )
    cap.set_verified_hos(remaining_drive_hours=10.0, remaining_duty_hours=10.0, remaining_cycle_hours=50.0)

    can_fit_unk, reasons_unk = cap.can_accommodate(stacking_policy="UNKNOWN")
    assert can_fit_unk is False
    assert any("NEEDS_REVIEW: Cargo stacking policy is unknown" in r for r in reasons_unk)

    cap.cargo.allows_top_load = False
    can_fit_top, reasons_top = cap.can_accommodate(stacking_policy="TOP_LOAD")
    assert can_fit_top is False
    assert any("Top-load freight cannot be placed" in r for r in reasons_top)


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

    card.transition_to("Analyzed")
    assert card.stage == "Analyzed"

    card.transition_to("Scored")
    assert card.stage == "Scored"

    card.transition_to("Filtered")
    card.transition_to("Presented")
    card.transition_to("Selected")

    with pytest.raises(ValueError, match="explicit human authority"):
        card.transition_to("Committed")

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

    for opp in ingested:
        pipeline.analyze_opportunity(opp.opportunity_id)
        pipeline.score_opportunity(opp.opportunity_id)

    presented = pipeline.filter_and_present(min_score=50.0)
    assert len(presented) > 0
    scores = [c.score for c in presented]
    assert scores == sorted(scores, reverse=True)

    top_opp = presented[0]
    committed_load = pipeline.commit_opportunity_to_reality(
        top_opp.opportunity_id, human_actor="Mike Zachary"
    )

    assert committed_load["load_id"] is not None
    assert top_opp.stage == "Current Reality"
