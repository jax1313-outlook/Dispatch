"""Truck Arrangement operational intelligence data structure.

Truck Arrangement is operational data (not merely documentation) representing
cargo geometry, stacking, handling, and sequence requirements.

It influences Capacity, Scheduling, Scoring, Pricing, and Revenue Projection.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


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
