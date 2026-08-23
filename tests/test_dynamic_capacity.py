"""Behavioural tests for the Dynamic Capacity advisory engine.

The engine's job is to evaluate, to refuse, and to raise -- never to decide.
Every refusal below is checked twice: that the refusal is truthful about *what*
is wrong, and that the refusal changed nothing. An advisory engine that mutates
state while saying no is deciding.
"""

from __future__ import annotations

import re

import pytest

from dispatch.capacity import (
    CapacityFinding,
    CargoArrangementCapacity,
    DynamicCapacity,
    Stop,
    StopSequenceCapacity,
    TimeCapacity,
    evaluate_reserve_dimension,
    parse_operational_timestamp,
)
from dispatch.truck_arrangement import CargoUnit, TruckArrangement

OBSERVED_AT = "2026-08-23T12:00:00Z"


def verified_capacity(**overrides) -> DynamicCapacity:
    """An asset with an attested spec, an attested HOS snapshot and recorded cargo policy."""
    cap = DynamicCapacity(equipment_id="TRK-01", driver_id="DRV-09")
    profile = {
        "asset_profile_id": "TRK-01-53FT",
        "max_weight_lbs": 44000.0,
        "max_volume_cuft": 3400.0,
        "max_linear_feet": 53.0,
        "max_pallets": 26,
        "source": "OEM_SPEC_SHEET",
        "verified_by": "Fleet Manager",
    }
    profile.update(overrides)
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


# A1: the fit concepts are reported separately


def test_load_that_fits_within_baseline_reports_every_concept_positively():
    cap = verified_capacity()

    result = cap.evaluate(weight_lbs=20000.0, linear_feet=20.0, drive_hours=4.0, service_hours=2.0, stacking_policy="STACKABLE")

    assert result.physical_fit is True
    assert result.baseline_fit is True
    assert result.reserve_required is False
    assert result.exceeds_total_capacity is False
    assert result.data_sufficient is True
    assert result.requires_human_review is False
    assert result.status == "FITS_WITHIN_BASELINE"
    assert bool(result) is True


def test_reserve_consuming_load_is_not_reported_as_a_physical_failure():
    cap = verified_capacity()
    before = cap.to_dict()

    # 43,500 lbs fits inside 44,000 lbs of trailer but leaves only 500 lbs of
    # the 1,000 lb reserve.
    result = cap.evaluate(weight_lbs=43500.0, stacking_policy="STACKABLE")

    assert result.physical_fit is True, "the freight physically fits; only the buffer is affected"
    assert result.baseline_fit is False
    assert result.reserve_required is True
    assert result.exceeds_total_capacity is False
    assert result.over_capacity == {}
    assert result.status == "FITS_ONLY_BY_CONSUMING_RESERVE"
    assert not any(code.startswith("CAPACITY_EXCEEDED_") for code in result.codes)
    assert "RESERVE_CONSUMED_WEIGHT" in result.codes
    assert result.findings_for("RESERVE_CONSUMED_WEIGHT")[0].severity == "ADVISORY"
    # Spending the safety buffer is a human's call, so the engine asks.
    assert result.requires_human_review is True
    assert result.clear_to_proceed is False
    assert cap.to_dict() == before


def test_total_capacity_exceedance_is_reported_as_exceedance_with_the_overage():
    cap = verified_capacity()
    before = cap.to_dict()

    result = cap.evaluate(weight_lbs=50000.0, stacking_policy="STACKABLE")

    assert result.physical_fit is False
    assert result.exceeds_total_capacity is True
    assert result.over_capacity["weight"] == 6000.0
    assert result.status == "EXCEEDS_TOTAL_CAPACITY"
    assert "CAPACITY_EXCEEDED_WEIGHT" in result.codes
    assert result.findings_for("CAPACITY_EXCEEDED_WEIGHT")[0].severity == "BLOCKING"
    assert cap.to_dict() == before


def test_unanswerable_fit_is_none_rather_than_false():
    cap = DynamicCapacity()
    before = cap.to_dict()

    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE")

    assert result.physical_fit is None
    assert result.baseline_fit is None
    assert result.reserve_required is None
    assert result.exceeds_total_capacity is False, "unknown is not an overage claim"
    assert result.data_sufficient is False
    assert cap.to_dict() == before


# A2: reserve impact per dimension


def test_reserve_impact_is_evaluated_per_dimension_not_as_one_boolean():
    cap = verified_capacity()

    # Weight eats its buffer, linear feet does not, HOS eats its buffer.
    result = cap.evaluate(
        weight_lbs=43500.0,
        linear_feet=10.0,
        drive_hours=9.5,
        service_hours=1.0,
        stacking_policy="STACKABLE",
    )

    impacts = result.reserve_impacts
    assert impacts["weight"].status == "CONSUMES_RESERVE"
    assert impacts["weight"].reserve_consumed == 500.0
    assert impacts["weight"].reserve_remaining_after == 500.0
    assert impacts["linear_feet"].status == "WITHIN_BASELINE"
    assert impacts["linear_feet"].reserve_consumed == 0.0
    assert impacts["drive_hours"].status == "CONSUMES_RESERVE"
    assert impacts["drive_hours"].reserve_consumed == 0.5
    assert impacts["flexibility_buffer"].status == "CONSUMES_RESERVE"
    # Each consuming dimension is named on its own finding.
    assert {"RESERVE_CONSUMED_WEIGHT", "RESERVE_CONSUMED_DRIVE_HOURS", "RESERVE_CONSUMED_FLEXIBILITY_BUFFER"} <= result.codes
    assert "RESERVE_CONSUMED_LINEAR_FEET" not in result.codes


def test_flexibility_buffer_is_its_own_reserve_dimension():
    cap = verified_capacity()

    tight = cap.evaluate(weight_lbs=41000.0, stacking_policy="STACKABLE")
    roomy = cap.evaluate(weight_lbs=10000.0, stacking_policy="STACKABLE")

    # 41,000 / 44,000 == 93.2%, past the 10% flexibility buffer, while the
    # weight reserve itself is untouched.
    assert tight.reserve_impacts["weight"].status == "WITHIN_BASELINE"
    assert tight.reserve_impacts["flexibility_buffer"].status == "CONSUMES_RESERVE"
    assert tight.reserve_impacts["flexibility_buffer"].unit == "pct"
    assert roomy.reserve_impacts["flexibility_buffer"].status == "WITHIN_BASELINE"


def test_reserve_dimension_helper_reports_overload_against_a_negative_remaining():
    impact, findings = evaluate_reserve_dimension(
        dimension="weight",
        requested=1000.0,
        raw_remaining=-6000.0,
        reserved=1000.0,
        unit="lbs",
        source_ref="physical.max_weight_lbs",
    )

    assert impact.over_capacity == 7000.0
    assert impact.status == "EXCEEDS_TOTAL"
    assert impact.reserve_consumed == 1000.0
    assert [f.code for f in findings] == ["CAPACITY_EXCEEDED_WEIGHT"]


# A3: no manufactured verification


def test_asset_profile_requires_an_explicit_source_and_changes_nothing_when_refused():
    cap = DynamicCapacity()
    before = cap.to_dict()

    with pytest.raises(ValueError, match="explicit source"):
        cap.apply_asset_profile(
            asset_profile_id="TRK-01",
            max_weight_lbs=44000.0,
            max_volume_cuft=3400.0,
            max_linear_feet=53.0,
            max_pallets=26,
            source="   ",
        )

    assert cap.to_dict() == before
    assert cap.physical.configuration_status == "UNCONFIGURED"


def test_asset_profile_without_a_named_actor_is_unverified_not_verified():
    cap = DynamicCapacity()

    cap.apply_asset_profile(
        asset_profile_id="TRK-01",
        max_weight_lbs=44000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
        source="CARRIER_PACKET_PDF",
    )

    assert cap.physical.configuration_status == "UNVERIFIED"
    assert cap.physical.configuration_verified_by is None
    assert cap.physical.configuration_verified_at is None
    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE")
    assert "ASSET_CONFIGURATION_UNVERIFIED" in result.codes
    assert result.requires_human_review is True


def test_no_capacity_entry_point_defaults_to_a_human_verification():
    """Locked doctrine: nothing may stamp a person's attestation by default."""
    import inspect

    from dispatch import capacity as capacity_module
    from dispatch import truck_arrangement as arrangement_module

    attested_fields = (
        "verified_by",
        "source",
        "hos_source",
        "committed_by",
        "recorded_by",
        "authority_ref",
        "securement_verified_by",
    )
    for module in (capacity_module, arrangement_module):
        for name, member in inspect.getmembers(module):
            if not (inspect.isclass(member) or inspect.isfunction(member)):
                continue
            if getattr(member, "__module__", "") != module.__name__:
                continue
            functions = (
                inspect.getmembers(member, predicate=inspect.isfunction) if inspect.isclass(member) else [(name, member)]
            )
            for attr_name, attr in functions:
                for param in inspect.signature(attr).parameters.values():
                    if param.default is inspect.Parameter.empty or not isinstance(param.default, str):
                        continue
                    lowered = param.default.lower()
                    assert "zachary" not in lowered, f"{name}.{attr_name} defaults {param.name} to a person"
                    assert "mike" not in lowered, f"{name}.{attr_name} defaults {param.name} to a person"
                    if param.name in attested_fields:
                        assert param.default == "", f"{name}.{attr_name} invents a value for {param.name}"


def test_hos_snapshot_requires_an_explicit_source_and_changes_nothing_when_refused():
    cap = verified_capacity()
    before = cap.to_dict()

    with pytest.raises(ValueError, match="explicit source"):
        cap.set_hos_snapshot(
            remaining_drive_hours=8.0,
            remaining_duty_hours=10.0,
            remaining_cycle_hours=40.0,
            source="",
        )

    assert cap.to_dict() == before


def test_verified_hos_requires_an_observation_time_and_rejects_ambiguous_ones():
    cap = DynamicCapacity()
    before = cap.to_dict()

    with pytest.raises(ValueError, match="requires observed_at"):
        cap.set_verified_hos(8.0, 10.0, 40.0, source="ELD:Samsara", observed_at="")
    with pytest.raises(ValueError, match="timezone-aware"):
        cap.set_verified_hos(8.0, 10.0, 40.0, source="ELD:Samsara", observed_at="2026-08-23 12:00:00")

    assert cap.to_dict() == before
    assert cap.time.hos_status == "UNKNOWN"


def test_estimated_hos_is_reported_as_an_estimate_not_a_reading():
    cap = verified_capacity()

    cap.set_hos_snapshot(
        remaining_drive_hours=8.0,
        remaining_duty_hours=10.0,
        remaining_cycle_hours=40.0,
        source="driver phone call",
        status="ESTIMATED",
    )

    assert cap.time.hos_status == "ESTIMATED"
    assert cap.time.hos_source == "driver phone call"
    result = cap.evaluate(drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE")
    assert "HOS_SNAPSHOT_ESTIMATED" in result.codes
    assert result.requires_human_review is True


def test_duty_status_is_unknown_until_recorded():
    assert TimeCapacity().duty_status == "UNKNOWN"
    with pytest.raises(ValueError, match="Invalid duty_status"):
        TimeCapacity(duty_status="MAYBE")


# A4: no optimistic cargo defaults


def test_unrecorded_cargo_stays_unknown_and_blocks_a_clean_answer():
    cargo = CargoArrangementCapacity()
    assert cargo.stacking_policy == "UNKNOWN"
    assert cargo.allows_top_load is None
    assert cargo.arrangement_type == "unknown"
    assert cargo.securement_status == "UNVERIFIED"
    assert cargo.max_stack_height_inches is None

    cap = verified_capacity()
    cap.cargo = CargoArrangementCapacity()
    before = cap.to_dict()

    result = cap.evaluate(weight_lbs=10000.0)  # stacking policy not supplied either

    assert result.clear_to_proceed is False
    assert "CARGO_STACKING_POLICY_UNKNOWN" in result.codes
    assert result.data_sufficient is False
    assert cap.to_dict() == before


def test_arrangement_securement_cannot_be_verified_without_an_actor():
    with pytest.raises(ValueError, match="requires securement_verified_by"):
        TruckArrangement(securement_status="VERIFIED")

    attested = TruckArrangement(securement_status="VERIFIED", securement_verified_by="Loader: R. Diaz")
    assert attested.evaluate_arrangement().securement_status == "VERIFIED"
    assert attested.securement_verified_at


def test_unverified_securement_is_surfaced_by_the_capacity_engine():
    cap = verified_capacity()
    arrangement = TruckArrangement(arrangement_type="multi_pallet")

    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE", arrangement=arrangement)

    assert "CARGO_SECUREMENT_UNVERIFIED" in result.codes
    assert result.clear_to_proceed is False


# A5: stop sequence integrated into the main evaluation


def _recorded_arrangement() -> TruckArrangement:
    """A fully recorded, attested arrangement: geometry known, securement signed."""
    return TruckArrangement(
        arrangement_type="multi_stop",
        securement_status="VERIFIED",
        securement_verified_by="Loader: R. Diaz",
        units=[
            _unit("A", load=1, unload=2, delivery=2, access=2),
            _unit("B", load=2, unload=1, delivery=1, access=1),
        ],
    )


def _stop(seq: int, start: str, end: str, drive: float | None, service: float | None, oor: float = 0.0) -> Stop:
    return Stop(
        stop_id=f"S{seq}",
        sequence=seq,
        location=f"Stop {seq}",
        appointment_start=start,
        appointment_end=end,
        drive_hours_to_stop=drive,
        service_hours=service,
        out_of_route_miles=oor,
    )


def test_stop_sequence_feeds_drive_and_duty_comparison():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=4, assigned_stops=0)
    stops = [
        _stop(1, "2026-08-24T08:00:00Z", "2026-08-24T10:00:00Z", 2.0, 1.0),
        _stop(2, "2026-08-24T13:00:00Z", "2026-08-24T18:00:00Z", 3.0, 1.5),
    ]

    result = cap.evaluate(
        weight_lbs=10000.0,
        stacking_policy="STACKABLE",
        stops=stops,
        arrangement=_recorded_arrangement(),
    )

    summary = result.stop_sequence
    assert summary["stop_count"] == 2
    assert summary["total_drive_hours"] == 5.0
    assert summary["total_service_hours"] == 2.5
    assert summary["appointments_evaluated"] is True
    # Stop drive and service time became the HOS comparison, not a side note.
    assert result.reserve_impacts["drive_hours"].requested == 5.0
    assert result.reserve_impacts["duty_hours"].requested == 7.5
    assert result.reserve_impacts["duty_hours"].evaluated is True
    assert result.clear_to_proceed is True


def test_stop_count_beyond_the_ceiling_is_an_exceedance():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=2, assigned_stops=1)
    before = cap.to_dict()
    stops = [
        _stop(1, "2026-08-24T08:00:00Z", "2026-08-24T10:00:00Z", 1.0, 0.5),
        _stop(2, "2026-08-24T12:00:00Z", "2026-08-24T14:00:00Z", 1.0, 0.5),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "CAPACITY_EXCEEDED_STOPS" in result.codes
    assert result.exceeds_total_capacity is True
    assert cap.to_dict() == before


def test_stop_ceiling_that_was_never_recorded_is_asked_about_not_assumed():
    cap = verified_capacity()
    assert cap.stop_sequence.max_stops is None
    assert cap.stop_sequence.remaining_stops is None

    result = cap.evaluate(stacking_policy="STACKABLE", stops=[_stop(1, "2026-08-24T08:00:00Z", "2026-08-24T10:00:00Z", 1.0, 0.5)])

    assert "STOP_CAPACITY_UNKNOWN" in result.codes
    assert result.requires_human_review is True


def test_out_of_route_impact_is_measured_and_compared():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5, max_out_of_route_miles=20.0, route_out_of_route_miles=5.0)
    stops = [
        _stop(1, "2026-08-24T08:00:00Z", "2026-08-24T10:00:00Z", 1.0, 0.5, oor=12.0),
        _stop(2, "2026-08-24T12:00:00Z", "2026-08-24T16:00:00Z", 1.0, 0.5, oor=8.0),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert result.stop_sequence["total_out_of_route_miles"] == 25.0
    assert "OUT_OF_ROUTE_EXCEEDED" in result.codes


def test_unrecorded_service_time_is_a_gap_not_a_zero():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [_stop(1, "2026-08-24T08:00:00Z", "2026-08-24T10:00:00Z", 2.0, None)]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "STOP_SERVICE_TIME_UNKNOWN" in result.codes
    assert result.stop_sequence["total_service_hours"] is None
    assert result.reserve_impacts["duty_hours"].evaluated is False
    assert result.reserve_impacts["duty_hours"].status == "NOT_EVALUATED"
    assert result.data_sufficient is False


# A6: timezone-aware appointment arithmetic


def test_parse_operational_timestamp_classifies_every_input():
    parsed, status = parse_operational_timestamp("2026-08-24T08:00:00-05:00")
    assert status == "PARSED"
    assert parsed.utcoffset().total_seconds() == 0
    assert parsed.hour == 13

    assert parse_operational_timestamp("") == (None, "MISSING")
    assert parse_operational_timestamp(None) == (None, "MISSING")
    assert parse_operational_timestamp("next tuesday")[1] == "INVALID"
    assert parse_operational_timestamp("2026-08-24T08:00:00")[1] == "NAIVE"


def test_naive_appointment_timestamps_produce_a_controlled_refusal():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    before = cap.to_dict()
    stops = [_stop(1, "2026-08-24T08:00:00", "2026-08-24T10:00:00", 1.0, 0.5)]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "STOP_APPOINTMENT_TIMESTAMP_UNUSABLE" in result.codes
    finding = result.findings_for("STOP_APPOINTMENT_TIMESTAMP_UNUSABLE")[0]
    assert finding.severity == "BLOCKING"
    assert finding.data_gap is True
    assert "ambiguous" in finding.message
    assert result.data_sufficient is False
    assert result.stop_sequence["appointments_evaluated"] is False
    assert cap.to_dict() == before


def test_unparseable_appointment_timestamps_produce_a_controlled_refusal():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [_stop(1, "tomorrow morning", "2026-08-24T10:00:00Z", 1.0, 0.5)]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "STOP_APPOINTMENT_TIMESTAMP_UNUSABLE" in result.codes
    assert result.data_sufficient is False


def test_appointment_conflict_is_detected_across_timezones_where_string_order_lies():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    # Sorted as text, "...09:00:00-05:00" precedes "...10:00:00Z"; in real time
    # the second stop (10:00Z) opens four hours before the first (14:00Z).
    first, second = "2026-08-24T09:00:00-05:00", "2026-08-24T10:00:00Z"
    assert first < second, "the string ordering this test guards against"
    stops = [
        _stop(1, first, "2026-08-24T16:00:00Z", 1.0, 0.5),
        _stop(2, second, "2026-08-24T11:00:00Z", 1.0, 0.5),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "STOP_APPOINTMENT_CONFLICT" in result.codes
    assert result.clear_to_proceed is False


def test_appointment_window_that_cannot_be_reached_is_blocking():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [
        _stop(1, "2026-08-24T08:00:00Z", "2026-08-24T09:00:00Z", 1.0, 1.0),
        _stop(2, "2026-08-24T09:30:00Z", "2026-08-24T10:00:00Z", 2.0, 0.5),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "STOP_APPOINTMENT_INFEASIBLE" in result.codes
    late = result.findings_for("STOP_APPOINTMENT_INFEASIBLE")[0]
    assert late.severity == "BLOCKING"
    assert late.source_ref == "stop[2].appointment_end"


def test_reachable_sequence_across_timezones_is_accepted():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [
        _stop(1, "2026-08-24T03:00:00-05:00", "2026-08-24T05:00:00-05:00", 1.0, 1.0),
        _stop(2, "2026-08-24T12:00:00Z", "2026-08-24T18:00:00Z", 2.0, 0.5),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops, arrangement=_recorded_arrangement())

    assert "STOP_APPOINTMENT_INFEASIBLE" not in result.codes
    assert "STOP_APPOINTMENT_CONFLICT" not in result.codes
    assert result.stop_sequence["appointments_evaluated"] is True
    assert result.clear_to_proceed is True


def test_invalid_capacity_window_timestamps_are_refused():
    cap = verified_capacity()
    cap.time.time_window_start = "2026-08-24T06:00:00"  # no zone
    cap.time.time_window_end = "2026-08-24T20:00:00Z"

    result = cap.evaluate(drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE")

    assert "CAPACITY_WINDOW_TIMESTAMP_UNUSABLE" in result.codes
    assert result.data_sufficient is False


# A7: LIFO and cargo blocking derived, never defaulted


def _unit(uid: str, load: int, unload: int, delivery: int, access: int, blocked_by=None) -> CargoUnit:
    return CargoUnit(
        unit_id=uid,
        loading_order=load,
        unloading_order=unload,
        delivery_sequence=delivery,
        access_order=access,
        blocked_by=list(blocked_by or []),
        is_stackable=False,
    )


def test_lifo_is_feasible_only_when_the_recorded_geometry_says_so():
    arrangement = TruckArrangement(
        arrangement_type="multi_stop",
        stop_sequence_lifo=True,
        units=[_unit("A", load=1, unload=3, delivery=3, access=3), _unit("B", load=2, unload=2, delivery=2, access=2), _unit("C", load=3, unload=1, delivery=1, access=1)],
    )

    assessment = arrangement.evaluate_arrangement()

    assert assessment.lifo_status == "FEASIBLE"
    assert assessment.access_status == "FEASIBLE"
    assert assessment.blocking_status == "FEASIBLE"
    assert assessment.arrangement_status == "FEASIBLE"
    assert assessment.violations == []


def test_lifo_violation_is_derived_from_loading_versus_unloading_order():
    arrangement = TruckArrangement(
        arrangement_type="multi_stop",
        stop_sequence_lifo=True,
        units=[_unit("A", load=1, unload=1, delivery=1, access=1), _unit("B", load=2, unload=2, delivery=2, access=2)],
    )

    assessment = arrangement.evaluate_arrangement()

    assert assessment.lifo_status == "INFEASIBLE"
    assert assessment.arrangement_status == "INFEASIBLE"
    assert {v.code for v in assessment.violations} == {"LIFO_ORDER_VIOLATION"}


def test_cargo_blocking_is_derived_from_blocking_relationships():
    arrangement = TruckArrangement(
        arrangement_type="multi_stop",
        units=[
            _unit("A", load=2, unload=1, delivery=1, access=1, blocked_by=["B"]),
            _unit("B", load=1, unload=2, delivery=2, access=2),
        ],
    )

    assessment = arrangement.evaluate_arrangement()

    assert assessment.blocking_status == "INFEASIBLE"
    blocked = [v for v in assessment.violations if v.code == "CARGO_BLOCKED"]
    assert [v.unit_id for v in blocked] == ["A"]


def test_missing_cargo_geometry_yields_unknown_never_feasible():
    arrangement = TruckArrangement(arrangement_type="multi_stop", units=[CargoUnit(unit_id="A"), CargoUnit(unit_id="B")])

    assessment = arrangement.evaluate_arrangement()

    assert assessment.lifo_status == "UNKNOWN"
    assert assessment.access_status == "UNKNOWN"
    assert assessment.blocking_status == "UNKNOWN"
    assert assessment.arrangement_status == "UNKNOWN"
    assert "CARGO_SEQUENCE_UNRECORDED" in assessment.codes


def test_unknown_lifo_blocks_when_the_sequence_requires_lifo_discipline():
    cap = verified_capacity()
    cap.cargo.multi_stop_lifo_required = True
    arrangement = TruckArrangement(arrangement_type="multi_stop", units=[CargoUnit(unit_id="A")])
    before = cap.to_dict()

    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE", arrangement=arrangement)

    assert "CARGO_LIFO_UNKNOWN" in result.codes
    assert result.findings_for("CARGO_LIFO_UNKNOWN")[0].severity == "BLOCKING"
    assert result.clear_to_proceed is False
    assert cap.to_dict() == before


def test_derived_lifo_violation_reaches_the_capacity_findings():
    cap = verified_capacity()
    arrangement = TruckArrangement(
        arrangement_type="multi_stop",
        securement_status="VERIFIED",
        securement_verified_by="Loader: R. Diaz",
        units=[_unit("A", load=1, unload=1, delivery=1, access=1), _unit("B", load=2, unload=2, delivery=2, access=2)],
    )

    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE", arrangement=arrangement)

    assert "CARGO_LIFO_INFEASIBLE" in result.codes
    assert result.arrangement["lifo_status"] == "INFEASIBLE"
    assert result.clear_to_proceed is False


def test_multi_stop_without_an_arrangement_cannot_claim_lifo_feasibility():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [
        _stop(1, "2026-08-24T08:00:00Z", "2026-08-24T12:00:00Z", 1.0, 0.5),
        _stop(2, "2026-08-24T14:00:00Z", "2026-08-24T20:00:00Z", 1.0, 0.5),
    ]

    result = cap.evaluate(stacking_policy="STACKABLE", stops=stops)

    assert "CARGO_ARRANGEMENT_NOT_PROVIDED" in result.codes
    assert result.arrangement == {"status": "NOT_EVALUATED"}
    assert result.data_sufficient is False


# A8: the time evaluation is complete: computed *and* compared


def test_every_time_dimension_is_compared_against_remaining_capacity():
    cap = verified_capacity()

    result = cap.evaluate(drive_hours=6.0, service_hours=2.0, stacking_policy="STACKABLE")

    drive, duty, cycle = (result.reserve_impacts[d] for d in ("drive_hours", "duty_hours", "cycle_hours"))
    assert (drive.requested, drive.raw_remaining) == (6.0, 10.0)
    assert (duty.requested, duty.raw_remaining) == (8.0, 12.0)
    assert (cycle.requested, cycle.raw_remaining) == (8.0, 60.0)
    assert all(impact.evaluated for impact in (drive, duty, cycle))
    assert result.time["duty_hours_required"] == 8.0


def test_break_requirement_is_added_to_duty_time_and_can_exhaust_it():
    cap = verified_capacity()

    result = cap.evaluate(drive_hours=9.0, service_hours=4.0, stacking_policy="STACKABLE")

    assert result.time["break_required"] is True
    assert result.time["duty_hours_required"] == 13.5
    assert "BREAK_REQUIRED" in result.codes
    # Drive time alone still fits; duty time does not, and the engine says which.
    assert result.reserve_impacts["drive_hours"].status == "WITHIN_BASELINE"
    assert "CAPACITY_EXCEEDED_DUTY_HOURS" in result.codes
    assert result.over_capacity["duty_hours"] == 1.5


def test_cycle_hours_are_compared_separately_from_duty_hours():
    cap = verified_capacity()
    cap.set_verified_hos(
        remaining_drive_hours=10.0,
        remaining_duty_hours=12.0,
        remaining_cycle_hours=5.0,
        source="ELD:Samsara",
        observed_at=OBSERVED_AT,
    )

    result = cap.evaluate(drive_hours=6.0, service_hours=2.0, stacking_policy="STACKABLE")

    assert "CAPACITY_EXCEEDED_CYCLE_HOURS" in result.codes
    assert "CAPACITY_EXCEEDED_DUTY_HOURS" not in result.codes
    assert result.over_capacity["cycle_hours"] == 3.0


def test_capacity_window_shorter_than_the_work_is_reported():
    cap = verified_capacity()
    cap.time.time_window_start = "2026-08-24T06:00:00Z"
    cap.time.time_window_end = "2026-08-24T10:00:00Z"

    result = cap.evaluate(drive_hours=6.0, service_hours=2.0, stacking_policy="STACKABLE")

    assert "CAPACITY_WINDOW_EXCEEDED" in result.codes
    assert result.time["capacity_window_hours"] == 4.0


def test_disagreeing_drive_time_estimates_are_reported_not_reconciled_silently():
    cap = verified_capacity()
    cap.stop_sequence = StopSequenceCapacity(max_stops=5)
    stops = [_stop(1, "2026-08-24T08:00:00Z", "2026-08-24T18:00:00Z", 6.0, 1.0)]

    result = cap.evaluate(drive_hours=2.0, stacking_policy="STACKABLE", stops=stops)

    assert "DRIVE_TIME_SOURCE_DISAGREEMENT" in result.codes
    assert result.reserve_impacts["drive_hours"].requested == 6.0, "the pessimistic figure carries the comparison"


# A9: overload visibility


def test_overloaded_asset_preserves_the_real_overage_while_display_clamps():
    cap = verified_capacity()
    cap.record_committed_load("LD-1", committed_by="Dispatcher", authority_ref="LOAD-1", weight_lbs=30000.0, linear_feet=40.0)
    cap.record_committed_load("LD-2", committed_by="Dispatcher", authority_ref="LOAD-2", weight_lbs=20000.0, linear_feet=20.0)

    physical = cap.physical
    assert physical.remaining_weight_lbs == -6000.0
    assert physical.display_remaining_weight_lbs == 0.0
    assert physical.over_capacity_weight_lbs == 6000.0
    assert physical.remaining_linear_feet == -7.0
    assert physical.over_capacity_linear_feet == 7.0
    assert physical.is_over_capacity is True

    audit = physical.to_dict()
    assert audit["remaining_weight_lbs"] == -6000.0
    assert audit["display_remaining_weight_lbs"] == 0.0
    assert audit["over_capacity_weight_lbs"] == 6000.0

    # A further request measures the overage from the true position.
    result = cap.evaluate(weight_lbs=1000.0, stacking_policy="STACKABLE")
    assert result.remaining["weight_lbs"] == -6000.0
    assert result.over_capacity["weight"] == 7000.0


def test_volume_and_pallet_overage_are_preserved_too():
    cap = verified_capacity()
    cap.record_committed_load(
        "LD-1",
        committed_by="Dispatcher",
        authority_ref="LOAD-1",
        volume_cuft=4000.0,
        pallets=30,
    )

    assert cap.physical.remaining_volume_cuft == -600.0
    assert cap.physical.over_capacity_volume_cuft == 600.0
    assert cap.physical.remaining_pallets == -4
    assert cap.physical.over_capacity_pallets == 4
    assert cap.physical.display_remaining_pallets == 0


# A10: profile updates do not erase utilization


def test_applying_an_asset_profile_updates_the_spec_and_keeps_utilization():
    cap = verified_capacity()
    cap.record_committed_load(
        "LD-1",
        committed_by="Dispatcher",
        authority_ref="LOAD-1",
        weight_lbs=12000.0,
        linear_feet=14.0,
        volume_cuft=900.0,
        pallets=8,
    )

    cap.apply_asset_profile(
        asset_profile_id="TRK-01-53FT-REWEIGHED",
        max_weight_lbs=42000.0,
        max_volume_cuft=3400.0,
        max_linear_feet=53.0,
        max_pallets=26,
        source="SCALE_TICKET",
        verified_by="Fleet Manager",
        version="2.0",
    )

    assert cap.physical.max_weight_lbs == 42000.0
    assert cap.physical.asset_profile_version == "2.0"
    assert cap.physical.configuration_source == "SCALE_TICKET"
    # Freight on the trailer did not fall off because a spec sheet was re-read.
    assert cap.physical.used_weight_lbs == 12000.0
    assert cap.physical.used_linear_feet == 14.0
    assert cap.physical.used_volume_cuft == 900.0
    assert cap.physical.used_pallets == 8
    assert cap.physical.remaining_weight_lbs == 30000.0
    assert [entry.ref_id for entry in cap.committed] == ["LD-1"]


# A11: candidate and committed identity


def test_projected_opportunity_never_mutates_current_reality():
    cap = verified_capacity()
    physical_before = cap.physical.to_dict()

    entry = cap.record_projected_opportunity("OPP-1", weight_lbs=20000.0, linear_feet=24.0, drive_hours=6.0, recorded_by="Planner")

    assert entry.kind == "PROJECTED"
    assert cap.physical.to_dict() == physical_before
    assert cap.committed == []
    assert [p.ref_id for p in cap.projected] == ["OPP-1"]
    # The possible future is visible, but only as a projection.
    projected = cap.projected_utilization()
    assert projected["weight_lbs"] == 20000.0
    assert projected["projection_count"] == 1
    assert projected["committed_count"] == 0
    assert cap.physical.used_weight_lbs == 0.0


def test_projection_requires_a_reference_and_refuses_duplicates():
    cap = verified_capacity()
    before = cap.to_dict()

    with pytest.raises(ValueError, match="requires a ref_id"):
        cap.record_projected_opportunity("", weight_lbs=1000.0)
    assert cap.to_dict() == before

    cap.record_projected_opportunity("OPP-1", weight_lbs=1000.0)
    with pytest.raises(ValueError, match="already recorded"):
        cap.record_projected_opportunity("OPP-1", weight_lbs=9999.0)
    assert len(cap.projected) == 1
    assert cap.projected[0].weight_lbs == 1000.0


def test_commitment_requires_an_actor_and_an_authority_and_mutates_nothing_when_refused():
    cap = verified_capacity()
    before = cap.to_dict()

    with pytest.raises(ValueError, match="holds no commitment authority"):
        cap.record_committed_load("LD-1", committed_by="", authority_ref="LOAD-1", weight_lbs=5000.0)
    with pytest.raises(ValueError, match="authority_ref"):
        cap.record_committed_load("LD-1", committed_by="Dispatcher", authority_ref="", weight_lbs=5000.0)

    assert cap.to_dict() == before
    assert cap.committed == []
    assert cap.physical.used_weight_lbs == 0.0


def test_committing_a_projected_candidate_moves_it_out_of_the_projection_ledger():
    cap = verified_capacity()
    cap.record_projected_opportunity("OPP-1", weight_lbs=20000.0, linear_feet=24.0)

    cap.record_committed_load(
        "OPP-1",
        committed_by="Mike Zachary",
        authority_ref="LOAD-4471",
        weight_lbs=20000.0,
        linear_feet=24.0,
    )

    assert cap.projected == []
    assert [c.ref_id for c in cap.committed] == ["OPP-1"]
    assert cap.committed[0].recorded_by == "Mike Zachary"
    assert cap.committed[0].authority_ref == "LOAD-4471"
    assert cap.physical.used_weight_lbs == 20000.0
    # Counted once, not twice.
    assert cap.projected_utilization()["weight_lbs"] == 20000.0


# A12: structured findings, and the stale-configuration bug


def test_findings_are_structured_records_not_sentences():
    cap = DynamicCapacity()

    result = cap.evaluate(weight_lbs=1000.0, drive_hours=3.0)

    assert result.findings, "a refusal must say why"
    for finding in result.findings:
        assert isinstance(finding, CapacityFinding)
        assert re.fullmatch(r"[A-Z][A-Z0-9_]+", finding.code), finding.code
        assert finding.dimension in ("ASSET", "PHYSICAL", "TIME", "POSITION", "RESERVE", "CARGO", "STOP_SEQUENCE")
        assert finding.severity in ("INFO", "ADVISORY", "BLOCKING")
        assert finding.message
        assert finding.source_ref
        assert isinstance(finding.requires_human_review, bool)
        assert finding.to_dict()["code"] == finding.code


def test_stale_asset_configuration_is_never_reported_as_feasible():
    """The old roll-up passed any finding that mentioned 'stale'; this is that bug."""
    cap = verified_capacity()
    cap.physical.configuration_status = "STALE"
    before = cap.to_dict()

    result = cap.evaluate(weight_lbs=20000.0, drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE")

    assert "ASSET_CONFIGURATION_STALE" in result.codes
    assert result.findings_for("ASSET_CONFIGURATION_STALE")[0].requires_human_review is True
    assert result.clear_to_proceed is False
    assert bool(result) is False
    assert result.status == "REQUIRES_HUMAN_REVIEW"
    # The load itself is fine; only the specification is doubtful, and the
    # result keeps those two facts apart.
    assert result.physical_fit is True
    assert cap.to_dict() == before


def test_stale_asset_configuration_stays_a_review_item_even_in_simulation():
    cap = verified_capacity()
    cap.physical.configuration_status = "STALE"

    result = cap.evaluate(weight_lbs=20000.0, drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE", is_simulation=True)

    assert result.clear_to_proceed is False
    assert "ASSET_CONFIGURATION_STALE" in result.codes


def test_verified_configuration_is_the_positive_counterpart():
    cap = verified_capacity()

    result = cap.evaluate(weight_lbs=20000.0, drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE")

    assert "ASSET_CONFIGURATION_STALE" not in result.codes
    assert result.clear_to_proceed is True


def test_assessment_keeps_the_legacy_call_shape_working():
    cap = verified_capacity()

    fits, findings = cap.can_accommodate(weight_lbs=20000.0, drive_hours=4.0, service_hours=1.0, stacking_policy="STACKABLE")

    assert fits is True
    assert [f for f in findings if f.requires_human_review] == []
    assert [f for f in findings if f.severity == "BLOCKING"] == []
    # Attribute paths other subsystems read straight off the capacity object.
    assert cap.position.estimated_deadhead_miles == 0.0
    assert cap.physical.max_weight_lbs == 44000.0
    assert cap.physical.max_volume_cuft == 3400.0
    assert cap.physical.max_pallets == 26
    assert cap.time.drive_limit_hours == 11.0


def test_assessment_serialises_every_reported_concept_for_audit():
    cap = verified_capacity()

    payload = cap.evaluate(weight_lbs=43500.0, stacking_policy="STACKABLE").to_dict()

    assert payload["status"] == "FITS_ONLY_BY_CONSUMING_RESERVE"
    assert payload["physical_fit"] is True
    assert payload["baseline_fit"] is False
    assert payload["reserve_required"] is True
    assert payload["exceeds_total_capacity"] is False
    assert payload["data_sufficient"] is True
    assert payload["requires_human_review"] is True
    assert payload["clear_to_proceed"] is False
    assert payload["reserve_impacts"]["weight"]["reserve_consumed"] == 500.0
    assert any(f["code"] == "RESERVE_CONSUMED_WEIGHT" for f in payload["findings"])
