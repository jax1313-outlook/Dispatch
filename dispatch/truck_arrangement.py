"""Truck Arrangement operational intelligence data structure.

Truck Arrangement is operational data (not merely documentation) representing
cargo geometry, stacking, handling, and sequence requirements.

It influences Capacity, Scheduling, Scoring, Pricing, and Revenue Projection.

Nothing here infers a workable arrangement from absent data. Cargo that never
recorded how it was loaded is UNKNOWN -- not stackable, not accessible, not
LIFO-clean, not secured. Every feasibility answer this module gives is derived
from recorded unit geometry (position, loading order, unloading order, delivery
sequence, access order, blocking relationships); when that geometry is missing
the answer is UNKNOWN and the missing inputs are named, because a dispatcher
can act on "we do not know which pallet is behind which" and cannot act on a
cheerful default.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ARRANGEMENT_TYPES = [
    "unknown",
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

# Securement is a physical act somebody performs and attests to. There is no
# integration that observes straps, so VERIFIED must carry an actor.
SECUREMENT_STATUSES = ["UNVERIFIED", "VERIFIED", "NOT_EVALUATED"]

# Derived feasibility answers. UNKNOWN is a first-class result, never a
# placeholder for "probably fine".
FEASIBILITY_STATUSES = ["UNKNOWN", "FEASIBLE", "INFEASIBLE"]

STACKABILITY_STATUSES = ["UNKNOWN", "STACKABLE", "NON_STACKABLE"]


@dataclass(frozen=True)
class ArrangementViolation:
    """One structured, machine-readable arrangement finding.

    Callers must never string-match prose to learn what went wrong, so the
    code carries the meaning and the message carries only the explanation.
    """

    code: str
    message: str
    unit_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CargoUnit:
    """A physically distinct piece of freight on the trailer.

    The four ordering fields are deliberately Optional: a unit whose loading or
    unloading order was never recorded cannot participate in a LIFO or access
    derivation, and saying so is the whole point of the type.
    """

    unit_id: str = ""
    description: str = ""
    position: str = ""  # NOSE / MID / TAIL / bay label -- as physically loaded
    loading_order: int | None = None
    unloading_order: int | None = None
    delivery_sequence: int | None = None
    access_order: int | None = None
    blocked_by: list[str] = field(default_factory=list)
    weight_lbs: float = 0.0
    linear_feet: float = 0.0
    is_stackable: bool | None = None  # None == UNKNOWN, never assumed True

    def __post_init__(self) -> None:
        if not self.unit_id:
            self.unit_id = f"UNIT-{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArrangementAssessment:
    """What the recorded cargo geometry actually supports.

    Each dimension answers separately. `unresolved` names the inputs that were
    missing, so the gap is auditable rather than absorbed into a default.
    """

    lifo_status: str = "UNKNOWN"
    access_status: str = "UNKNOWN"
    blocking_status: str = "UNKNOWN"
    stackability_status: str = "UNKNOWN"
    securement_status: str = "UNVERIFIED"
    violations: list[ArrangementViolation] = field(default_factory=list)
    unresolved: list[ArrangementViolation] = field(default_factory=list)

    @property
    def arrangement_status(self) -> str:
        """Roll-up. FEASIBLE only when every derived dimension is FEASIBLE."""
        derived = (self.lifo_status, self.access_status, self.blocking_status)
        if "INFEASIBLE" in derived:
            return "INFEASIBLE"
        if all(status == "FEASIBLE" for status in derived):
            return "FEASIBLE"
        return "UNKNOWN"

    @property
    def codes(self) -> set[str]:
        return {v.code for v in self.violations} | {u.code for u in self.unresolved}

    def to_dict(self) -> dict:
        return {
            "lifo_status": self.lifo_status,
            "access_status": self.access_status,
            "blocking_status": self.blocking_status,
            "stackability_status": self.stackability_status,
            "securement_status": self.securement_status,
            "arrangement_status": self.arrangement_status,
            "violations": [v.to_dict() for v in self.violations],
            "unresolved": [u.to_dict() for u in self.unresolved],
        }


@dataclass
class TruckArrangement:
    arrangement_id: str = ""
    load_id: str = ""
    arrangement_type: str = "unknown"
    pallet_count: int = 0
    linear_feet: float = 0.0
    total_weight_lbs: float = 0.0
    total_volume_cuft: float = 0.0
    is_stackable: bool | None = None  # None == UNKNOWN; absent paperwork is not permission
    requires_liftgate: bool = False
    requires_pallet_jack: bool = False
    requires_temperature_control: bool = False
    temp_target_fahrenheit: float | None = None
    stop_sequence_lifo: bool = False  # True == the sequence *requires* LIFO discipline
    securement_status: str = "UNVERIFIED"
    securement_verified_by: str = ""
    securement_verified_at: str = ""
    units: list[CargoUnit] = field(default_factory=list)
    special_handling_notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.arrangement_id:
            self.arrangement_id = f"ARR-{uuid.uuid4().hex[:8].upper()}"
        if not self.created_at:
            self.created_at = _utc_now()
        if self.arrangement_type not in ARRANGEMENT_TYPES:
            raise ValueError(f"Invalid arrangement_type: {self.arrangement_type!r}. Must be one of {ARRANGEMENT_TYPES}")
        if self.securement_status not in SECUREMENT_STATUSES:
            raise ValueError(f"Invalid securement_status: {self.securement_status!r}. Must be one of {SECUREMENT_STATUSES}")
        if self.securement_status == "VERIFIED" and not self.securement_verified_by.strip():
            raise ValueError("securement_status 'VERIFIED' requires securement_verified_by (an actor who performed the check)")
        if self.securement_status == "VERIFIED" and not self.securement_verified_at.strip():
            self.securement_verified_at = _utc_now()

    @property
    def density_lbs_per_cuft(self) -> float:
        if self.total_volume_cuft > 0:
            return round(self.total_weight_lbs / self.total_volume_cuft, 2)
        return 0.0

    def _units_missing(self, attribute: str) -> list[CargoUnit]:
        return [u for u in self.units if getattr(u, attribute) is None]

    def evaluate_stackability(self) -> tuple[str, list[ArrangementViolation]]:
        """Stackability from the units, falling back to the arrangement flag.

        A single known non-stackable unit dominates: one fragile pallet makes
        the whole arrangement non-stackable regardless of what the others say.
        """
        unresolved: list[ArrangementViolation] = []
        flags = [u.is_stackable for u in self.units]
        if self.is_stackable is not None:
            flags.append(self.is_stackable)
        if not flags:
            unresolved.append(
                ArrangementViolation(
                    code="STACKABILITY_UNRECORDED",
                    message="No unit-level or arrangement-level stackability was recorded",
                )
            )
            return "UNKNOWN", unresolved
        if any(flag is False for flag in flags):
            return "NON_STACKABLE", unresolved
        if any(flag is None for flag in flags):
            for unit in self._units_missing("is_stackable"):
                unresolved.append(
                    ArrangementViolation(
                        code="STACKABILITY_UNRECORDED",
                        message="Unit stackability was never recorded",
                        unit_id=unit.unit_id,
                    )
                )
            return "UNKNOWN", unresolved
        return "STACKABLE", unresolved

    def evaluate_lifo(self) -> tuple[str, list[ArrangementViolation], list[ArrangementViolation]]:
        """Derive LIFO feasibility from loading, unloading and delivery order.

        LIFO holds when the last unit loaded is the first unit off: sort by
        unloading order and the loading order must run strictly downward. The
        delivery sequence has to agree with the unloading order too, otherwise
        the trailer is packed for a route it is not running.
        """
        violations: list[ArrangementViolation] = []
        unresolved: list[ArrangementViolation] = []
        if not self.units:
            unresolved.append(
                ArrangementViolation(code="CARGO_UNITS_ABSENT", message="No cargo units recorded; LIFO cannot be derived")
            )
            return "UNKNOWN", violations, unresolved

        for attribute in ("loading_order", "unloading_order", "delivery_sequence"):
            for unit in self._units_missing(attribute):
                unresolved.append(
                    ArrangementViolation(
                        code="CARGO_SEQUENCE_UNRECORDED",
                        message=f"Unit is missing {attribute}; LIFO cannot be derived",
                        unit_id=unit.unit_id,
                    )
                )
        if unresolved:
            return "UNKNOWN", violations, unresolved

        by_unload = sorted(self.units, key=lambda u: u.unloading_order)
        for earlier, later in zip(by_unload, by_unload[1:]):
            if earlier.loading_order <= later.loading_order:
                violations.append(
                    ArrangementViolation(
                        code="LIFO_ORDER_VIOLATION",
                        message=(
                            f"Unit unloads at {earlier.unloading_order} but was loaded at "
                            f"{earlier.loading_order}, ahead of unit {later.unit_id} loaded at "
                            f"{later.loading_order}; it is buried behind freight that leaves later"
                        ),
                        unit_id=earlier.unit_id,
                    )
                )
        for earlier, later in zip(by_unload, by_unload[1:]):
            if earlier.delivery_sequence > later.delivery_sequence:
                violations.append(
                    ArrangementViolation(
                        code="DELIVERY_SEQUENCE_MISMATCH",
                        message=(
                            f"Unloading order puts this unit before {later.unit_id}, but its delivery "
                            f"sequence ({earlier.delivery_sequence}) comes after ({later.delivery_sequence})"
                        ),
                        unit_id=earlier.unit_id,
                    )
                )
        return ("INFEASIBLE" if violations else "FEASIBLE"), violations, unresolved

    def evaluate_access(self) -> tuple[str, list[ArrangementViolation], list[ArrangementViolation]]:
        """Access order must rise with unloading order.

        A unit that comes off first has to be reachable first; if the recorded
        access order disagrees, somebody is restacking the trailer on a dock.
        """
        violations: list[ArrangementViolation] = []
        unresolved: list[ArrangementViolation] = []
        if not self.units:
            unresolved.append(
                ArrangementViolation(code="CARGO_UNITS_ABSENT", message="No cargo units recorded; access order cannot be derived")
            )
            return "UNKNOWN", violations, unresolved

        for attribute in ("access_order", "unloading_order"):
            for unit in self._units_missing(attribute):
                unresolved.append(
                    ArrangementViolation(
                        code="ACCESS_ORDER_UNRECORDED",
                        message=f"Unit is missing {attribute}; access feasibility cannot be derived",
                        unit_id=unit.unit_id,
                    )
                )
        if unresolved:
            return "UNKNOWN", violations, unresolved

        by_unload = sorted(self.units, key=lambda u: u.unloading_order)
        for earlier, later in zip(by_unload, by_unload[1:]):
            if earlier.access_order > later.access_order:
                violations.append(
                    ArrangementViolation(
                        code="ACCESS_ORDER_VIOLATION",
                        message=(
                            f"Unit unloads before {later.unit_id} but is reachable only at access position "
                            f"{earlier.access_order} versus {later.access_order}"
                        ),
                        unit_id=earlier.unit_id,
                    )
                )
        return ("INFEASIBLE" if violations else "FEASIBLE"), violations, unresolved

    def evaluate_blocking(self) -> tuple[str, list[ArrangementViolation], list[ArrangementViolation]]:
        """Blocking relationships against unloading order.

        A blocker that leaves the trailer after the unit it blocks has to be
        pulled and reloaded at the stop -- that is a real operational cost, so
        it is reported rather than smoothed away.
        """
        violations: list[ArrangementViolation] = []
        unresolved: list[ArrangementViolation] = []
        if not self.units:
            unresolved.append(
                ArrangementViolation(code="CARGO_UNITS_ABSENT", message="No cargo units recorded; blocking cannot be derived")
            )
            return "UNKNOWN", violations, unresolved

        for unit in self._units_missing("unloading_order"):
            unresolved.append(
                ArrangementViolation(
                    code="CARGO_SEQUENCE_UNRECORDED",
                    message="Unit is missing unloading_order; blocking cannot be derived",
                    unit_id=unit.unit_id,
                )
            )
        if unresolved:
            return "UNKNOWN", violations, unresolved

        by_id = {u.unit_id: u for u in self.units}
        for unit in self.units:
            for blocker_id in unit.blocked_by:
                blocker = by_id.get(blocker_id)
                if blocker is None:
                    unresolved.append(
                        ArrangementViolation(
                            code="BLOCKER_UNRESOLVED",
                            message=f"Unit is blocked by {blocker_id!r}, which is not part of this arrangement",
                            unit_id=unit.unit_id,
                        )
                    )
                    continue
                if blocker.unloading_order > unit.unloading_order:
                    violations.append(
                        ArrangementViolation(
                            code="CARGO_BLOCKED",
                            message=(
                                f"Unit unloads at {unit.unloading_order} but is blocked by {blocker.unit_id}, "
                                f"which does not unload until {blocker.unloading_order}"
                            ),
                            unit_id=unit.unit_id,
                        )
                    )
        if unresolved:
            return "UNKNOWN", violations, unresolved
        return ("INFEASIBLE" if violations else "FEASIBLE"), violations, unresolved

    def evaluate_arrangement(self) -> ArrangementAssessment:
        """Every arrangement dimension, derived and reported separately."""
        assessment = ArrangementAssessment()

        assessment.stackability_status, stack_unresolved = self.evaluate_stackability()
        assessment.unresolved.extend(stack_unresolved)

        assessment.lifo_status, lifo_violations, lifo_unresolved = self.evaluate_lifo()
        assessment.violations.extend(lifo_violations)
        assessment.unresolved.extend(lifo_unresolved)

        assessment.access_status, access_violations, access_unresolved = self.evaluate_access()
        assessment.violations.extend(access_violations)
        assessment.unresolved.extend(access_unresolved)

        assessment.blocking_status, block_violations, block_unresolved = self.evaluate_blocking()
        assessment.violations.extend(block_violations)
        assessment.unresolved.extend(block_unresolved)

        assessment.securement_status = self.securement_status
        if self.securement_status != "VERIFIED":
            assessment.unresolved.append(
                ArrangementViolation(
                    code="SECUREMENT_UNVERIFIED",
                    message=f"Cargo securement is {self.securement_status}; no actor has attested to it",
                )
            )
        return assessment

    def to_dict(self) -> dict:
        d = asdict(self)
        d["density_lbs_per_cuft"] = self.density_lbs_per_cuft
        d["arrangement_assessment"] = self.evaluate_arrangement().to_dict()
        return d
