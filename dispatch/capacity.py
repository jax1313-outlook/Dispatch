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

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


CONFIG_STATUSES = ["UNCONFIGURED", "PARTIAL", "VERIFIED", "STALE", "INVALID"]
HOS_STATUSES = ["UNKNOWN", "VERIFIED", "ESTIMATED", "STALE", "UNAVAILABLE"]
STACKING_POLICIES = ["UNKNOWN", "STACKABLE", "NON_STACKABLE", "TOP_LOAD"]


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

    def __post_init__(self) -> None:
        if self.hos_status not in HOS_STATUSES:
            raise ValueError(f"Invalid hos_status: {self.hos_status!r}. Must be one of {HOS_STATUSES}")

    def to_dict(self) -> dict:
        return asdict(self)


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

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReserveCapacity:
    reserved_hos_hours: float = 1.0
    reserved_weight_lbs: float = 1000.0
    reserved_linear_feet: float = 2.0
    flexibility_buffer_pct: float = 10.0

    def to_dict(self) -> dict:
        return asdict(self)


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

    def __post_init__(self) -> None:
        if self.stacking_policy not in STACKING_POLICIES:
            raise ValueError(f"Invalid stacking_policy: {self.stacking_policy!r}. Must be one of {STACKING_POLICIES}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StopSequenceCapacity:
    max_stops: int = 5
    assigned_stops: int = 0
    route_out_of_route_miles: float = 0.0

    @property
    def remaining_stops(self) -> int:
        return max(0, self.max_stops - self.assigned_stops)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_stops"] = self.remaining_stops
        return d


@dataclass
class DynamicCapacity:
    capacity_id: str = ""
    equipment_id: str = ""
    driver_id: str = ""
    physical: PhysicalCapacity = field(default_factory=PhysicalCapacity)
    time: TimeCapacity = field(default_factory=TimeCapacity)
    position: PositionCapacity = field(default_factory=PositionCapacity)
    reserve: ReserveCapacity = field(default_factory=ReserveCapacity)
    cargo: CargoArrangementCapacity = field(default_factory=CargoArrangementCapacity)
    stop_sequence: StopSequenceCapacity = field(default_factory=StopSequenceCapacity)
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.capacity_id:
            self.capacity_id = f"CAP-{uuid.uuid4().hex[:8].upper()}"
        if not self.updated_at:
            self.updated_at = _utc_now()

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
        if stacking_policy == "NON_STACKABLE":
            if requires_floor_position and linear_feet > max(0.0, eff_feet):
                reasons.append("Non-stackable cargo requires floor position exceeding remaining linear feet")
            if not self.cargo.allows_top_load:
                reasons.append("Cargo arrangement forbids non-stackable placement")
        elif stacking_policy == "TOP_LOAD":
            if not self.cargo.allows_top_load:
                reasons.append("Top-load freight cannot be placed on current cargo arrangement")

        return (len(reasons) == 0 or all(r.startswith("NEEDS_REVIEW") and "stale" in r.lower() for r in reasons)), reasons

    def to_dict(self) -> dict:
        return {
            "capacity_id": self.capacity_id,
            "equipment_id": self.equipment_id,
            "driver_id": self.driver_id,
            "physical": self.physical.to_dict(),
            "time": self.time.to_dict(),
            "position": self.position.to_dict(),
            "reserve": self.reserve.to_dict(),
            "cargo": self.cargo.to_dict(),
            "stop_sequence": self.stop_sequence.to_dict(),
            "updated_at": self.updated_at,
        }
