"""Truck Arrangement operational intelligence data structure.

Truck Arrangement is operational data (not merely documentation) representing
cargo geometry, stacking, handling, and sequence requirements.

It influences Capacity, Scheduling, Scoring, Pricing, and Revenue Projection.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from dispatch.capacity import CapacityDataMetadata, CapacityState


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ARRANGEMENT_TYPES = [
    "single_pallet",
    "multi_pallet",
    "partials",
    "mixed_freight",
    "stacked",
    "non_stacked",
    "courier",
    "liftgate",
    "multi_stop",
    "custom",
]


@dataclass
class CargoUnit:
    cargo_unit_id: str = ""
    description: str = ""
    quantity: int = 1
    freight_type: str = "general"
    length_inches: float = 48.0
    width_inches: float = 40.0
    height_inches: float = 48.0
    weight_lbs: float = 0.0
    volume_cuft: float = 0.0
    palletized: bool = True
    pallet_type: str = "standard_48x40"
    stack_policy: str = "STACKABLE"  # UNKNOWN, STACKABLE, NON_STACKABLE, TOP_LOAD
    can_support_top_load: bool = True
    can_be_top_loaded: bool = True
    requires_floor_position: bool = True
    handling_requirements: list[str] = field(default_factory=list)
    liftgate_required: bool = False
    ramp_required: bool = False
    pallet_jack_required: bool = False
    temperature_requirements: float | None = None
    segregation_requirements: list[str] = field(default_factory=list)
    securement_requirements: list[str] = field(default_factory=list)
    pickup_stop_id: str = ""
    delivery_stop_id: str = ""
    source_metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)
    findings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.cargo_unit_id:
            self.cargo_unit_id = f"UNIT-{uuid.uuid4().hex[:8].upper()}"
        if self.volume_cuft <= 0 and self.length_inches > 0 and self.width_inches > 0 and self.height_inches > 0:
            self.volume_cuft = round((self.length_inches * self.width_inches * self.height_inches) / 1728.0, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source_metadata"] = self.source_metadata.to_dict() if hasattr(self.source_metadata, "to_dict") else self.source_metadata
        return d


@dataclass
class CargoPosition:
    position_id: str = ""
    cargo_unit_id: str = ""
    cargo_zone: str = "A"  # nose, middle, tail
    longitudinal_position: float = 0.0  # distance from nose in feet
    lateral_position: str = "CENTER"  # LEFT, RIGHT, CENTER
    vertical_level: int = 1  # 1 = floor, 2 = stacked
    orientation: str = "NORMAL"  # NORMAL, TURNED
    loading_sequence: int = 1
    unloading_sequence: int = 1
    access_sequence: int = 1
    securement_point_reference: str = ""
    blocks_position_ids: list[str] = field(default_factory=list)
    blocked_by_position_ids: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.position_id:
            self.position_id = f"POS-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArrangementPlan:
    arrangement_id: str = ""
    asset_profile_id: str = ""
    state_type: str = CapacityState.POSSIBLE_FUTURE.value
    scenario_id: str = ""
    cargo_units: list[CargoUnit] = field(default_factory=list)
    cargo_positions: list[CargoPosition] = field(default_factory=list)
    loading_order: list[str] = field(default_factory=list)
    unloading_order: list[str] = field(default_factory=list)
    total_weight: float = 0.0
    total_volume: float = 0.0
    total_floor_space: float = 0.0
    stop_compatibility: bool = True
    stacking_compatibility: bool = True
    securement_review_status: str = "VERIFIED"
    arrangement_status: str = "FEASIBLE"
    findings: list[str] = field(default_factory=list)
    source_metadata: CapacityDataMetadata = field(default_factory=CapacityDataMetadata)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.arrangement_id:
            self.arrangement_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
        now = _utc_now()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
        if self.cargo_units and self.total_weight == 0.0:
            self.total_weight = sum(u.weight_lbs * u.quantity for u in self.cargo_units)
        if self.cargo_units and self.total_volume == 0.0:
            self.total_volume = sum(u.volume_cuft * u.quantity for u in self.cargo_units)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cargo_units"] = [u.to_dict() for u in self.cargo_units]
        d["cargo_positions"] = [p.to_dict() for p in self.cargo_positions]
        d["source_metadata"] = self.source_metadata.to_dict() if hasattr(self.source_metadata, "to_dict") else self.source_metadata
        return d


@dataclass
class TruckArrangement:
    arrangement_id: str = ""
    load_id: str = ""
    arrangement_type: str = "single_pallet"
    pallet_count: int = 0
    linear_feet: float = 0.0
    total_weight_lbs: float = 0.0
    total_volume_cuft: float = 0.0
    is_stackable: bool = True
    requires_liftgate: bool = False
    requires_pallet_jack: bool = False
    requires_temperature_control: bool = False
    temp_target_fahrenheit: float | None = None
    stop_sequence_lifo: bool = False
    special_handling_notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.arrangement_id:
            self.arrangement_id = f"ARR-{uuid.uuid4().hex[:8].upper()}"
        if not self.created_at:
            self.created_at = _utc_now()
        if self.arrangement_type not in ARRANGEMENT_TYPES:
            raise ValueError(f"Invalid arrangement_type: {self.arrangement_type!r}. Must be one of {ARRANGEMENT_TYPES}")

    @property
    def density_lbs_per_cuft(self) -> float:
        if self.total_volume_cuft > 0:
            return round(self.total_weight_lbs / self.total_volume_cuft, 2)
        return 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["density_lbs_per_cuft"] = self.density_lbs_per_cuft
        return d
