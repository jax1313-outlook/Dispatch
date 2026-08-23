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


@dataclass
class PhysicalCapacity:
    max_weight_lbs: float = 45000.0
    used_weight_lbs: float = 0.0
    max_volume_cuft: float = 3500.0
    used_volume_cuft: float = 0.0
    max_linear_feet: float = 53.0
    used_linear_feet: float = 0.0
    max_pallets: int = 26
    used_pallets: int = 0
    equipment_type: str = "dry_van"
    has_liftgate: bool = False
    has_ramp: bool = False
    has_temp_control: bool = False

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
    available_drive_hours: float = 11.0
    used_drive_hours: float = 0.0
    available_duty_hours: float = 14.0
    used_duty_hours: float = 0.0
    available_cycle_hours: float = 70.0
    used_cycle_hours: float = 0.0
    next_reset_due_at: str | None = None
    time_window_start: str = ""
    time_window_end: str = ""

    @property
    def remaining_drive_hours(self) -> float:
        return max(0.0, self.available_drive_hours - self.used_drive_hours)

    @property
    def remaining_duty_hours(self) -> float:
        return max(0.0, self.available_duty_hours - self.used_duty_hours)

    @property
    def remaining_cycle_hours(self) -> float:
        return max(0.0, self.available_cycle_hours - self.used_cycle_hours)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_drive_hours"] = self.remaining_drive_hours
        d["remaining_duty_hours"] = self.remaining_duty_hours
        d["remaining_cycle_hours"] = self.remaining_cycle_hours
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
    arrangement_type: str = "single_pallet"  # single_pallet, multi_pallet, partials, mixed, stacked, non_stacked, courier, liftgate, multi_stop, custom
    stackable_permitted: bool = True
    max_stack_height_inches: float = 96.0
    liftgate_required: bool = False
    multi_stop_lifo_required: bool = False
    temp_target_fahrenheit: float | None = None

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

    def can_accommodate(
        self,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        drive_hours: float = 0.0,
        requires_liftgate: bool = False,
        is_stackable: bool = True,
    ) -> tuple[bool, list[str]]:
        reasons = []
        eff_weight = self.physical.remaining_weight_lbs - self.reserve.reserved_weight_lbs
        if weight_lbs > max(0.0, eff_weight):
            reasons.append(f"Insufficient weight capacity: needs {weight_lbs} lbs, effective available {max(0.0, eff_weight)} lbs")

        eff_feet = self.physical.remaining_linear_feet - self.reserve.reserved_linear_feet
        if linear_feet > max(0.0, eff_feet):
            reasons.append(f"Insufficient linear feet: needs {linear_feet} ft, effective available {max(0.0, eff_feet)} ft")

        eff_drive = self.time.remaining_drive_hours - self.reserve.reserved_hos_hours
        if drive_hours > max(0.0, eff_drive):
            reasons.append(f"Insufficient HOS drive time: needs {drive_hours} hrs, effective available {max(0.0, eff_drive)} hrs")

        if requires_liftgate and not self.physical.has_liftgate:
            reasons.append("Equipment lacks required liftgate")

        if not is_stackable and not self.cargo.stackable_permitted:
            reasons.append("Cargo arrangement forbids non-stackable placement")

        return (len(reasons) == 0), reasons

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
