"""Dynamic Capacity model as a first-class Dispatch Spine object.

Dynamic Capacity models asset operational capacity across six core dimensions:
  1. Physical Capacity
  2. Time Capacity
  3. Position Capacity
  4. Reserve Capacity
  5. Cargo Arrangement Capacity
  6. Stop Sequence Capacity

It is designed as a reusable Dispatch Spine engine for Intelligence, Analysis,
Score, Filters, Opportunity Cards, Scheduler, Calendar, Pricing, Revenue
Projection, and Routing.
"""

from __future__ import annotations

import copy
import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CapacityState(str, enum.Enum):
    CURRENT_REALITY = "CURRENT_REALITY"
    POSSIBLE_FUTURE = "POSSIBLE_FUTURE"


CONFIG_STATUSES = ["UNCONFIGURED", "PARTIAL", "VERIFIED", "STALE", "INVALID"]
HOS_STATUSES = ["UNKNOWN", "VERIFIED", "ESTIMATED", "STALE", "UNAVAILABLE"]
STACKING_POLICIES = ["UNKNOWN", "STACKABLE", "NON_STACKABLE", "TOP_LOAD"]

APPROVED_EVALUATION_STATUSES = [
    "FITS_WITHIN_BASELINE",
    "FITS_BUT_CONSTRAINED",
    "CONSUMES_RESERVE",
    "EXCEEDS_CAPACITY",
    "INSUFFICIENT_DATA",
    "NEEDS_REVIEW",
]

PROHIBITED_AUTHORITY_STATUSES = [
    "APPROVED",
    "REJECTED",
    "ACCEPTED",
    "BOOKED",
    "ASSIGNED",
    "SCHEDULED",
    "BID_NOW",
    "AUTO_COMMIT",
]


@dataclass
class CapacityDataMetadata:
    source_type: str = "UNKNOWN"
    source_reference: str = ""
    observed_at: str | None = None
    received_at: str | None = None
    verified_at: str | None = None
    verified_by: str | None = None
    confidence: str = "LOW"
    freshness_status: str = "UNKNOWN"  # CURRENT, STALE, UNKNOWN, UNAVAILABLE, NOT_APPLICABLE
    findings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PhysicalCapacity:
    asset_profile_id: str = ""
    asset_profile_version: str = ""
    configuration_status: str = "UNCONFIGURED"  # UNCONFIGURED, PARTIAL, VERIFIED, STALE, INVALID
    configuration_source: str = ""
    configuration_verified_at: str | None = None
    configuration_verified_by: str | None = None

    max_weight_lbs: float = 0.0
    used_weight_lbs: float = 0.0
    max_volume_cuft: float = 0.0
    used_volume_cuft: float = 0.0
    max_linear_feet: float = 0.0
    used_linear_feet: float = 0.0
    max_pallets: int = 0
    used_pallets: int = 0
    equipment_type: str = "unknown"
    has_liftgate: bool = False
    has_ramp: bool = False
    has_temp_control: bool = False

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    def __post_init__(self) -> None:
        if self.configuration_status not in CONFIG_STATUSES:
            raise ValueError(f"Invalid configuration_status: {self.configuration_status!r}. Must be one of {CONFIG_STATUSES}")

    @property
    def remaining_weight_lbs(self) -> float:
        return max(0.0, self.max_weight_lbs - self.used_weight_lbs)

    @property
    def remaining_volume_cuft(self) -> float:
        return max(0.0, self.max_volume_cuft - self.used_volume_cuft)

    @property
    def remaining_linear_feet(self) -> float:
        return max(0.0, self.max_linear_feet - self.used_linear_feet)

    @property
    def remaining_pallets(self) -> int:
        return max(0, self.max_pallets - self.used_pallets)

    @property
    def weight_utilization_pct(self) -> float:
        if self.max_weight_lbs <= 0:
            return 0.0
        return round((self.used_weight_lbs / self.max_weight_lbs) * 100.0, 1)

    @property
    def space_utilization_pct(self) -> float:
        if self.max_linear_feet <= 0:
            return 0.0
        return round((self.used_linear_feet / self.max_linear_feet) * 100.0, 1)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_weight_lbs"] = self.remaining_weight_lbs
        d["remaining_volume_cuft"] = self.remaining_volume_cuft
        d["remaining_linear_feet"] = self.remaining_linear_feet
        d["remaining_pallets"] = self.remaining_pallets
        d["weight_utilization_pct"] = self.weight_utilization_pct
        d["space_utilization_pct"] = self.space_utilization_pct
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class TimeCapacity:
    drive_limit_hours: float = 11.0
    duty_limit_hours: float = 14.0
    cycle_limit_hours: float = 70.0

    remaining_drive_hours: float = 0.0
    remaining_duty_hours: float = 0.0
    remaining_cycle_hours: float = 0.0
    duty_status: str = "OFF_DUTY"
    required_break_due_at: str | None = None
    reset_eligible_at: str | None = None

    hos_source: str = ""
    hos_observed_at: str | None = None
    hos_status: str = "UNKNOWN"  # UNKNOWN, VERIFIED, ESTIMATED, STALE, UNAVAILABLE
    confidence: str = "LOW"  # LOW, MEDIUM, HIGH

    time_window_start: str = ""
    time_window_end: str = ""

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    def __post_init__(self) -> None:
        if self.hos_status not in HOS_STATUSES:
            raise ValueError(f"Invalid hos_status: {self.hos_status!r}. Must be one of {HOS_STATUSES}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class PositionCapacity:
    current_location: str = ""
    current_lat: float | None = None
    current_lon: float | None = None
    destination_location: str = ""
    destination_lat: float | None = None
    destination_lon: float | None = None
    estimated_deadhead_miles: float = 0.0
    relocation_market_quality: str = "medium"  # low, medium, high

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class ReserveCapacity:
    reserved_hos_hours: float = 1.0
    reserved_weight_lbs: float = 1000.0
    reserved_linear_feet: float = 2.0
    flexibility_buffer_pct: float = 10.0

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class CargoArrangementCapacity:
    arrangement_type: str = "single_pallet"  # single_pallet, multi_pallet, partials, mixed_freight, stacked, non_stacked, courier, liftgate, multi_stop, custom
    stacking_policy: str = "STACKABLE"  # UNKNOWN, STACKABLE, NON_STACKABLE, TOP_LOAD
    allows_top_load: bool = True
    requires_floor_position: bool = True
    max_stack_height_inches: float = 96.0
    liftgate_required: bool = False
    multi_stop_lifo_required: bool = False
    temp_target_fahrenheit: float | None = None

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    def __post_init__(self) -> None:
        if self.stacking_policy not in STACKING_POLICIES:
            raise ValueError(f"Invalid stacking_policy: {self.stacking_policy!r}. Must be one of {STACKING_POLICIES}")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class StopRecord:
    stop_id: str = ""
    stop_type: str = "PICKUP"  # PICKUP, DELIVERY, WAYPOINT
    sequence_number: int = 1
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    appointment_start: str | None = None
    appointment_end: str | None = None
    cargo_unit_ids: list[str] = field(default_factory=list)
    service_time_minutes: float = 30.0
    required_access_order: int = 1
    loading_or_unloading_action: str = "LOAD"
    estimated_arrival: str | None = None
    estimated_departure: str | None = None
    out_of_route_miles: float = 0.0
    drive_time_impact: float = 0.0
    duty_time_impact: float = 0.0
    source_metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)
    findings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stop_id:
            self.stop_id = f"STOP-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_metadata"] = self.source_metadata.to_dict() if hasattr(self.source_metadata, "to_dict") else self.source_metadata
        return d


@dataclass
class StopSequenceEvaluation:
    evaluation_id: str = ""
    state_type: str = "POSSIBLE_FUTURE"
    scenario_id: str = ""
    stops: list[StopRecord] = field(default_factory=list)
    overall_status: str = "SEQUENCE_FEASIBLE"
    stop_count_status: str = "STOP_COUNT_FITS"
    appointment_status: str = "APPOINTMENTS_FEASIBLE"
    access_status: str = "ACCESS_FEASIBLE"
    lifo_status: str = "LIFO_FEASIBLE"
    cargo_blocking_findings: list[str] = field(default_factory=list)
    added_drive_time: float = 0.0
    added_duty_time: float = 0.0
    hos_findings: list[str] = field(default_factory=list)
    reserve_time_impact: float = 0.0
    constraints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_human_review: bool = False

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            self.evaluation_id = f"STPEVAL-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stops"] = [s.to_dict() for s in self.stops]
        return d


@dataclass
class StopSequenceCapacity:
    max_stops: int = 5
    assigned_stops: int = 0
    route_out_of_route_miles: float = 0.0

    metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)

    @property
    def remaining_stops(self) -> int:
        return max(0, self.max_stops - self.assigned_stops)

    def evaluate_sequence(self, new_stops: list[StopRecord]) -> StopSequenceEvaluation:
        total_stops = self.assigned_stops + len(new_stops)
        eval_res = StopSequenceEvaluation(
            scenario_id=f"SEQ-SCENARIO-{uuid.uuid4().hex[:6].upper()}"
        )
        eval_res.stops = new_stops

        if total_stops > self.max_stops:
            eval_res.stop_count_status = "STOP_COUNT_EXCEEDED"
            eval_res.overall_status = "SEQUENCE_INFEASIBLE"
            eval_res.constraints.append(f"Exceeds max stops limit ({self.max_stops})")

        # Evaluate appointments and LIFO
        prev_delivery_time = None
        for s in new_stops:
            if s.appointment_start and prev_delivery_time:
                if s.appointment_start < prev_delivery_time:
                    eval_res.appointment_status = "APPOINTMENT_CONFLICT"
                    eval_res.overall_status = "SEQUENCE_INFEASIBLE"
                    eval_res.constraints.append(f"Appointment start {s.appointment_start} conflicts with previous sequence")
            prev_delivery_time = s.appointment_end or s.appointment_start

            eval_res.added_drive_time += s.drive_time_impact
            eval_res.added_duty_time += s.duty_time_impact + (s.service_time_minutes / 60.0)

        if any(s.findings for s in new_stops):
            eval_res.requires_human_review = True
            for s in new_stops:
                eval_res.cargo_blocking_findings.extend(s.findings)

        return eval_res

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_stops"] = self.remaining_stops
        d["metadata"] = self.metadata.to_dict() if hasattr(self.metadata, "to_dict") else self.metadata
        return d


@dataclass
class DynamicCapacityEvaluation:
    evaluation_id: str = ""
    evaluated_at: str = ""
    capacity_snapshot_id: str = ""
    based_on_snapshot_id: str = ""
    opportunity_id: str = ""
    scenario_id: str = ""
    state_type: str = "POSSIBLE_FUTURE"
    overall_status: str = "FITS_WITHIN_BASELINE"  # FITS_WITHIN_BASELINE, FITS_BUT_CONSTRAINED, CONSUMES_RESERVE, EXCEEDS_CAPACITY, INSUFFICIENT_DATA, NEEDS_REVIEW
    verified_fit: bool = True
    insufficient_data: bool = False
    constraints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    reserve_impact: dict = field(default_factory=dict)
    capacity_consumption_profile: dict = field(default_factory=dict)
    projected_after_snapshot: dict = field(default_factory=dict)
    source_freshness_summary: dict = field(default_factory=dict)
    requires_human_review: bool = False

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            self.evaluation_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"
        if not self.evaluated_at:
            self.evaluated_at = _utc_now()
        if self.overall_status not in APPROVED_EVALUATION_STATUSES:
            raise ValueError(f"Invalid overall_status: {self.overall_status!r}. Must be one of {APPROVED_EVALUATION_STATUSES}")
        for prohibited in PROHIBITED_AUTHORITY_STATUSES:
            if self.overall_status == prohibited:
                raise ValueError(f"Prohibited decision status used: {prohibited}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DynamicCapacity:
    capacity_id: str = ""
    snapshot_id: str = ""
    previous_snapshot_id: str = ""
    based_on_snapshot_id: str = ""
    scenario_id: str = ""
    state_type: str = CapacityState.CURRENT_REALITY.value
    asset_profile_id: str = ""
    asset_profile_version: str = ""
    equipment_id: str = ""
    driver_id: str = ""
    current_mission_id: str = ""
    committed_load_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    effective_from: str = ""
    effective_to: str = ""

    physical: PhysicalCapacity = field(default_factory=PhysicalCapacity)
    time: TimeCapacity = field(default_factory=TimeCapacity)
    position: PositionCapacity = field(default_factory=PositionCapacity)
    reserve: ReserveCapacity = field(default_factory=ReserveCapacity)
    cargo: CargoArrangementCapacity = field(default_factory=CargoArrangementCapacity)
    stop_sequence: StopSequenceCapacity = field(default_factory=StopSequenceCapacity)

    def __post_init__(self) -> None:
        if not self.capacity_id:
            self.capacity_id = f"CAP-{uuid.uuid4().hex[:8].upper()}"
        if not self.snapshot_id:
            self.snapshot_id = self.capacity_id
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if isinstance(self.state_type, CapacityState):
            self.state_type = self.state_type.value
        if self.state_type not in [s.value for s in CapacityState]:
            raise ValueError(f"Invalid state_type: {self.state_type!r}. Must be one of {[s.value for s in CapacityState]}")

    def apply_asset_profile(
        self,
        asset_profile_id: str,
        max_weight_lbs: float,
        max_volume_cuft: float,
        max_linear_feet: float,
        max_pallets: int,
        equipment_type: str = "dry_van",
        version: str = "1.0",
        source: str = "verified_spec",
        verified_by: str = "Mike Zachary",
        has_liftgate: bool = False,
        has_ramp: bool = False,
        has_temp_control: bool = False,
    ) -> None:
        self.asset_profile_id = asset_profile_id
        self.asset_profile_version = version
        self.physical = PhysicalCapacity(
            asset_profile_id=asset_profile_id,
            asset_profile_version=version,
            configuration_status="VERIFIED",
            configuration_source=source,
            configuration_verified_at=_utc_now(),
            configuration_verified_by=verified_by,
            max_weight_lbs=max_weight_lbs,
            max_volume_cuft=max_volume_cuft,
            max_linear_feet=max_linear_feet,
            max_pallets=max_pallets,
            equipment_type=equipment_type,
            has_liftgate=has_liftgate,
            has_ramp=has_ramp,
            has_temp_control=has_temp_control,
            metadata=CapacityDataMetadata(
                source_type="ASSET_PROFILE",
                source_reference=asset_profile_id,
                verified_at=_utc_now(),
                verified_by=verified_by,
                confidence="HIGH",
                freshness_status="CURRENT",
            ),
        )

    def set_verified_hos(
        self,
        remaining_drive_hours: float,
        remaining_duty_hours: float,
        remaining_cycle_hours: float,
        duty_status: str = "ON_DUTY",
        source: str = "ELD_LOG",
        confidence: str = "HIGH",
    ) -> None:
        self.time = TimeCapacity(
            drive_limit_hours=11.0,
            duty_limit_hours=14.0,
            cycle_limit_hours=70.0,
            remaining_drive_hours=remaining_drive_hours,
            remaining_duty_hours=remaining_duty_hours,
            remaining_cycle_hours=remaining_cycle_hours,
            duty_status=duty_status,
            hos_source=source,
            hos_observed_at=_utc_now(),
            hos_status="VERIFIED",
            confidence=confidence,
            metadata=CapacityDataMetadata(
                source_type="ELD",
                source_reference=source,
                observed_at=_utc_now(),
                confidence=confidence,
                freshness_status="CURRENT",
            ),
        )

    def can_accommodate(
        self,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
        requires_liftgate: bool = False,
        stacking_policy: str = "STACKABLE",  # UNKNOWN, STACKABLE, NON_STACKABLE, TOP_LOAD
        requires_floor_position: bool = True,
        is_simulation: bool = False,
    ) -> tuple[bool, list[str]]:
        reasons = []

        # Asset configuration check
        if self.physical.configuration_status in ("UNCONFIGURED", "INVALID"):
            reasons.append("NEEDS_REVIEW: Asset physical capacity is unconfigured or invalid")
            return False, reasons
        if self.physical.configuration_status in ("STALE", "PARTIAL"):
            reasons.append(f"NEEDS_REVIEW: Asset configuration status is {self.physical.configuration_status}")

        if weight_lbs > 0 and self.physical.max_weight_lbs <= 0:
            reasons.append("INSUFFICIENT_DATA: Asset max weight payload is unconfigured")
        if linear_feet > 0 and self.physical.max_linear_feet <= 0:
            reasons.append("INSUFFICIENT_DATA: Asset linear footage is unconfigured")
        if volume_cuft > 0 and self.physical.max_volume_cuft <= 0:
            reasons.append("INSUFFICIENT_DATA: Asset interior volume capacity is unconfigured")
        if pallets > 0 and self.physical.max_pallets <= 0:
            reasons.append("INSUFFICIENT_DATA: Asset pallet position capacity is unconfigured")

        if any("INSUFFICIENT_DATA" in r for r in reasons):
            return False, reasons

        # Physical capacity checks
        eff_weight = self.physical.remaining_weight_lbs - self.reserve.reserved_weight_lbs
        if weight_lbs > max(0.0, eff_weight):
            reasons.append(f"Insufficient weight capacity: needs {weight_lbs} lbs, effective available {max(0.0, eff_weight)} lbs")

        eff_feet = self.physical.remaining_linear_feet - self.reserve.reserved_linear_feet
        if linear_feet > max(0.0, eff_feet):
            reasons.append(f"Insufficient linear feet: needs {linear_feet} ft, effective available {max(0.0, eff_feet)} ft")

        eff_volume = self.physical.remaining_volume_cuft
        if volume_cuft > max(0.0, eff_volume):
            reasons.append(f"Insufficient volume: needs {volume_cuft} cuft, effective available {max(0.0, eff_volume)} cuft")

        eff_pallets = self.physical.remaining_pallets
        if pallets > max(0, eff_pallets):
            reasons.append(f"Insufficient pallet positions: needs {pallets}, effective available {eff_pallets}")

        # HOS Check
        if drive_hours > 0:
            if self.time.hos_status == "UNKNOWN":
                reasons.append("NEEDS_REVIEW: Driver HOS state is unknown")
                return False, reasons
            elif self.time.hos_status == "STALE" and not is_simulation:
                reasons.append("NEEDS_REVIEW: Driver HOS snapshot is stale")

            eff_drive = self.time.remaining_drive_hours - self.reserve.reserved_hos_hours
            if drive_hours > max(0.0, eff_drive):
                reasons.append(f"Insufficient HOS drive time: needs {drive_hours} hrs, effective available {max(0.0, eff_drive)} hrs")

        if requires_liftgate and not self.physical.has_liftgate:
            reasons.append("Equipment lacks required liftgate")

        # Refined Stacking and Top-Load Policy Logic
        if stacking_policy == "UNKNOWN":
            reasons.append("NEEDS_REVIEW: Cargo stacking policy is unknown")
        elif stacking_policy == "NON_STACKABLE":
            if requires_floor_position and linear_feet > max(0.0, eff_feet):
                reasons.append("Non-stackable cargo requires floor position exceeding remaining linear feet")
            if self.cargo.stacking_policy == "NON_STACKABLE" and not self.cargo.allows_top_load:
                reasons.append("Cargo arrangement forbids stacking or top-load placement")
        elif stacking_policy == "TOP_LOAD":
            if not self.cargo.allows_top_load:
                reasons.append("Top-load freight cannot be placed on current cargo arrangement")

        return (len(reasons) == 0 or all(r.startswith("NEEDS_REVIEW") and "stale" in r.lower() for r in reasons)), reasons

    def project_capacity(
        self,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
        scenario_id: str = "",
        opportunity_id: str = "",
    ) -> DynamicCapacity:
        """Deep copy source snapshot and apply hypothetical consumption without mutating source."""
        proj = copy.deepcopy(self)
        proj.previous_snapshot_id = self.snapshot_id
        proj.based_on_snapshot_id = self.snapshot_id
        proj.snapshot_id = f"CAP-PROJ-{uuid.uuid4().hex[:8].upper()}"
        proj.capacity_id = proj.snapshot_id
        proj.scenario_id = scenario_id or f"SCENARIO-{uuid.uuid4().hex[:6].upper()}"
        proj.state_type = CapacityState.POSSIBLE_FUTURE.value
        proj.updated_at = _utc_now()

        # Deduct consumption on projected copy
        proj.physical.used_weight_lbs += weight_lbs
        proj.physical.used_linear_feet += linear_feet
        proj.physical.used_volume_cuft += volume_cuft
        proj.physical.used_pallets += pallets
        proj.time.remaining_drive_hours = max(0.0, proj.time.remaining_drive_hours - drive_hours)

        return proj

    def evaluate_capacity(
        self,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
        opportunity_id: str = "",
        scenario_id: str = "",
        requires_liftgate: bool = False,
        stacking_policy: str = "STACKABLE",
    ) -> DynamicCapacityEvaluation:
        """Structured, non-mutating evaluation returning DynamicCapacityEvaluation object."""
        can_fit, reasons = self.can_accommodate(
            weight_lbs=weight_lbs,
            linear_feet=linear_feet,
            volume_cuft=volume_cuft,
            pallets=pallets,
            drive_hours=drive_hours,
            requires_liftgate=requires_liftgate,
            stacking_policy=stacking_policy,
            is_simulation=True,
        )

        insufficient_data = any("INSUFFICIENT_DATA" in r for r in reasons)
        needs_review = any("NEEDS_REVIEW" in r for r in reasons)

        # Check reserve consumption
        consumes_reserve = False
        res_weight = self.physical.remaining_weight_lbs - self.reserve.reserved_weight_lbs
        if weight_lbs > max(0.0, res_weight) and weight_lbs <= self.physical.remaining_weight_lbs:
            consumes_reserve = True

        # Generate projected snapshot
        proj = self.project_capacity(
            weight_lbs=weight_lbs,
            linear_feet=linear_feet,
            volume_cuft=volume_cuft,
            pallets=pallets,
            drive_hours=drive_hours,
            scenario_id=scenario_id,
            opportunity_id=opportunity_id,
        )

        if insufficient_data:
            overall_status = "INSUFFICIENT_DATA"
        elif needs_review:
            overall_status = "NEEDS_REVIEW"
        elif consumes_reserve:
            overall_status = "CONSUMES_RESERVE"
        elif not can_fit:
            overall_status = "EXCEEDS_CAPACITY"
        elif reasons:
            overall_status = "FITS_BUT_CONSTRAINED"
        else:
            overall_status = "FITS_WITHIN_BASELINE"

        return DynamicCapacityEvaluation(
            capacity_snapshot_id=self.snapshot_id,
            based_on_snapshot_id=self.snapshot_id,
            opportunity_id=opportunity_id,
            scenario_id=scenario_id,
            state_type=CapacityState.POSSIBLE_FUTURE.value,
            overall_status=overall_status,
            verified_fit=can_fit,
            insufficient_data=insufficient_data,
            constraints=[r for r in reasons if "INSUFFICIENT_DATA" not in r and "NEEDS_REVIEW" not in r],
            warnings=[r for r in reasons if "NEEDS_REVIEW" in r],
            assumptions=["Simulated projection evaluated for Possible Future scenario"],
            reserve_impact={
                "consumes_reserve": consumes_reserve,
                "reserved_weight_lbs": self.reserve.reserved_weight_lbs,
                "reserved_hos_hours": self.reserve.reserved_hos_hours,
            },
            capacity_consumption_profile={
                "weight_lbs": weight_lbs,
                "linear_feet": linear_feet,
                "volume_cuft": volume_cuft,
                "pallets": pallets,
                "drive_hours": drive_hours,
            },
            projected_after_snapshot=proj.to_dict(),
            source_freshness_summary={
                "physical_status": self.physical.configuration_status,
                "time_status": self.time.hos_status,
            },
            requires_human_review=needs_review or consumes_reserve or not can_fit,
        )

    def to_dict(self) -> dict:
        return {
            "capacity_id": self.capacity_id,
            "snapshot_id": self.snapshot_id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "based_on_snapshot_id": self.based_on_snapshot_id,
            "scenario_id": self.scenario_id,
            "state_type": self.state_type,
            "asset_profile_id": self.asset_profile_id,
            "asset_profile_version": self.asset_profile_version,
            "equipment_id": self.equipment_id,
            "driver_id": self.driver_id,
            "current_mission_id": self.current_mission_id,
            "committed_load_ids": list(self.committed_load_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "physical": self.physical.to_dict(),
            "time": self.time.to_dict(),
            "position": self.position.to_dict(),
            "reserve": self.reserve.to_dict(),
            "cargo": self.cargo.to_dict(),
            "stop_sequence": self.stop_sequence.to_dict(),
        }
