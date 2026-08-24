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

This engine is **advisory**. It evaluates, it refuses, and it raises; it never
decides. Nothing here books a load, accepts a load, advances a lifecycle stage,
or asserts that a human approved anything. Two consequences run through the
whole module:

* Absent data is reported as absent (UNKNOWN / UNVERIFIED / ESTIMATED / STALE /
  NOT_EVALUATED) instead of being replaced by a convenient value. A default
  that flatters the asset is a lie the dispatcher pays for at the dock.
* The distinct reasons a load might not work are reported separately: physical
  fit, baseline fit, reserve consumption, total-capacity exceedance, data
  sufficiency, and human-review requirement. A load that physically fits but
  eats the safety buffer is a judgement call for a human, not a physical
  failure, and the result object says exactly that.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from dispatch.truck_arrangement import ARRANGEMENT_TYPES, TruckArrangement


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# UNVERIFIED sits between PARTIAL and VERIFIED: the spec is complete but no
# actor has attested to it. Previously such profiles were stamped VERIFIED.
CONFIG_STATUSES = ["UNCONFIGURED", "PARTIAL", "UNVERIFIED", "VERIFIED", "STALE", "INVALID"]
HOS_STATUSES = ["UNKNOWN", "VERIFIED", "ESTIMATED", "STALE", "UNAVAILABLE"]
DUTY_STATUSES = ["UNKNOWN", "OFF_DUTY", "SLEEPER_BERTH", "ON_DUTY", "DRIVING"]
STACKING_POLICIES = ["UNKNOWN", "STACKABLE", "NON_STACKABLE", "TOP_LOAD"]

SEVERITY_INFO = "INFO"
SEVERITY_ADVISORY = "ADVISORY"
SEVERITY_BLOCKING = "BLOCKING"
SEVERITIES = [SEVERITY_INFO, SEVERITY_ADVISORY, SEVERITY_BLOCKING]

DIMENSION_PHYSICAL = "PHYSICAL"
DIMENSION_TIME = "TIME"
DIMENSION_POSITION = "POSITION"
DIMENSION_RESERVE = "RESERVE"
DIMENSION_CARGO = "CARGO"
DIMENSION_STOP_SEQUENCE = "STOP_SEQUENCE"
DIMENSION_ASSET = "ASSET"

PHYSICAL_DIMENSIONS = ["weight", "linear_feet", "volume", "pallets"]

# Federal property-carrying HOS: a 30-minute break is owed after 8 cumulative
# hours of driving, and it burns duty time even though it is not drive time.
BREAK_TRIGGER_DRIVE_HOURS = 8.0
REQUIRED_BREAK_HOURS = 0.5

# Two drive-time estimates that disagree by more than this are reported rather
# than silently reconciled -- the disagreement is the finding.
DRIVE_TIME_DISAGREEMENT_HOURS = 0.5

TIMESTAMP_PARSED = "PARSED"
TIMESTAMP_MISSING = "MISSING"
TIMESTAMP_INVALID = "INVALID"
TIMESTAMP_NAIVE = "NAIVE"


def parse_operational_timestamp(value: str | None) -> tuple[datetime | None, str]:
    """Parse an operational timestamp into an aware UTC datetime.

    Appointment times decide whether a truck is late, so they are never
    compared as strings: "2026-03-01T09:00:00-05:00" is earlier than
    "2026-03-01T08:00:00Z" and lexical ordering gets that backwards. A naive
    timestamp is rejected rather than assumed to be UTC -- a pickup window in
    an unstated zone is genuinely ambiguous, and guessing costs a load.
    """
    if value is None:
        return None, TIMESTAMP_MISSING
    text = str(value).strip()
    if not text:
        return None, TIMESTAMP_MISSING
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None, TIMESTAMP_INVALID
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return None, TIMESTAMP_NAIVE
    return parsed.astimezone(timezone.utc), TIMESTAMP_PARSED


@dataclass(frozen=True)
class CapacityFinding:
    """One structured, machine-readable capacity finding.

    Callers used to string-match English sentences to decide what a refusal
    meant, which is how a STALE asset configuration once got reported as
    feasible. The code carries the meaning; the message is for humans only.
    """

    code: str
    dimension: str
    severity: str
    message: str
    source_ref: str = ""
    requires_human_review: bool = False
    data_gap: bool = False

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"Invalid severity: {self.severity!r}. Must be one of {SEVERITIES}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReserveImpact:
    """What one requested dimension does to the reserve held on that dimension.

    Reserve is evaluated per dimension because the dimensions fail differently:
    spending the weight buffer on a heavy partial is a different operational
    decision from spending the HOS buffer on a long run, and one aggregate
    boolean cannot tell a dispatcher which buffer is gone.
    """

    dimension: str
    unit: str = ""
    requested: float = 0.0
    raw_remaining: float = 0.0
    reserved: float = 0.0
    baseline_available: float = 0.0
    reserve_consumed: float = 0.0
    reserve_remaining_after: float = 0.0
    over_capacity: float = 0.0
    status: str = "NOT_EVALUATED"  # NOT_EVALUATED, WITHIN_BASELINE, CONSUMES_RESERVE, EXCEEDS_TOTAL
    evaluated: bool = False
    source_ref: str = ""

    @property
    def consumes_reserve(self) -> bool:
        return self.evaluated and self.reserve_consumed > 0

    @property
    def exceeds_total(self) -> bool:
        return self.evaluated and self.over_capacity > 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["consumes_reserve"] = self.consumes_reserve
        d["exceeds_total"] = self.exceeds_total
        return d


def _round(value: float) -> float:
    return round(float(value), 4)


def evaluate_reserve_dimension(
    dimension: str,
    requested: float,
    raw_remaining: float,
    reserved: float,
    unit: str,
    source_ref: str,
    configured: bool = True,
    insufficient_data_message: str = "",
) -> tuple[ReserveImpact, list[CapacityFinding]]:
    """Compare one request against one dimension's remaining and reserved capacity.

    `raw_remaining` is deliberately allowed to be negative: an asset that is
    already over its rating must keep saying so, because clamping the number at
    zero hides the overload from every downstream consumer.
    """
    impact = ReserveImpact(
        dimension=dimension,
        unit=unit,
        requested=_round(requested),
        reserved=_round(reserved),
        source_ref=source_ref,
    )
    if requested <= 0:
        # Nothing was asked of this dimension. Silence here is honest; claiming
        # a pass would not be.
        return impact, []

    if not configured:
        impact.status = "NOT_EVALUATED"
        message = insufficient_data_message or f"{dimension} capacity is not configured, so the request cannot be evaluated"
        return impact, [
            CapacityFinding(
                code=f"INSUFFICIENT_DATA_{dimension.upper()}",
                dimension=DIMENSION_PHYSICAL if dimension in PHYSICAL_DIMENSIONS else DIMENSION_TIME,
                severity=SEVERITY_BLOCKING,
                message=message,
                source_ref=source_ref,
                requires_human_review=True,
                data_gap=True,
            ),
        ]

    baseline_available = raw_remaining - reserved
    impact.raw_remaining = _round(raw_remaining)
    impact.baseline_available = _round(baseline_available)
    impact.over_capacity = _round(max(0.0, requested - raw_remaining))
    impact.reserve_consumed = _round(min(reserved, max(0.0, requested - baseline_available)))
    impact.reserve_remaining_after = _round(min(reserved, raw_remaining - requested))
    impact.evaluated = True

    findings: list[CapacityFinding] = []
    if impact.over_capacity > 0:
        impact.status = "EXCEEDS_TOTAL"
        findings.append(
            CapacityFinding(
                code=f"CAPACITY_EXCEEDED_{dimension.upper()}",
                dimension=DIMENSION_PHYSICAL if dimension in PHYSICAL_DIMENSIONS else DIMENSION_TIME,
                severity=SEVERITY_BLOCKING,
                message=(
                    f"Requested {impact.requested} {unit} against {impact.raw_remaining} {unit} remaining; "
                    f"over capacity by {impact.over_capacity} {unit}"
                ),
                source_ref=source_ref,
                requires_human_review=True,
            )
        )
    elif impact.reserve_consumed > 0:
        impact.status = "CONSUMES_RESERVE"
        findings.append(
            CapacityFinding(
                code=f"RESERVE_CONSUMED_{dimension.upper()}",
                dimension=DIMENSION_RESERVE,
                severity=SEVERITY_ADVISORY,
                message=(
                    f"Requested {impact.requested} {unit} fits the asset but consumes {impact.reserve_consumed} {unit} "
                    f"of the {impact.reserved} {unit} reserve, leaving {impact.reserve_remaining_after} {unit}"
                ),
                source_ref=source_ref,
                requires_human_review=True,
            )
        )
    else:
        impact.status = "WITHIN_BASELINE"
    return impact, findings


@dataclass
class PhysicalCapacity:
    asset_profile_id: str = ""
    asset_profile_version: str = ""
    configuration_status: str = "UNCONFIGURED"
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

    # Remaining capacity is signed. A trailer loaded past its rating reports a
    # negative number here, and every consumer that needs the truth (analysis,
    # audit, exception reporting) gets it. Only the display_* twins clamp.
    @property
    def remaining_weight_lbs(self) -> float:
        return self.max_weight_lbs - self.used_weight_lbs

    @property
    def remaining_volume_cuft(self) -> float:
        return self.max_volume_cuft - self.used_volume_cuft

    @property
    def remaining_linear_feet(self) -> float:
        return self.max_linear_feet - self.used_linear_feet

    @property
    def remaining_pallets(self) -> int:
        return self.max_pallets - self.used_pallets

    @property
    def display_remaining_weight_lbs(self) -> float:
        return max(0.0, self.remaining_weight_lbs)

    @property
    def display_remaining_volume_cuft(self) -> float:
        return max(0.0, self.remaining_volume_cuft)

    @property
    def display_remaining_linear_feet(self) -> float:
        return max(0.0, self.remaining_linear_feet)

    @property
    def display_remaining_pallets(self) -> int:
        return max(0, self.remaining_pallets)

    @property
    def over_capacity_weight_lbs(self) -> float:
        return max(0.0, -self.remaining_weight_lbs)

    @property
    def over_capacity_volume_cuft(self) -> float:
        return max(0.0, -self.remaining_volume_cuft)

    @property
    def over_capacity_linear_feet(self) -> float:
        return max(0.0, -self.remaining_linear_feet)

    @property
    def over_capacity_pallets(self) -> int:
        return max(0, -self.remaining_pallets)

    @property
    def is_over_capacity(self) -> bool:
        return (
            self.over_capacity_weight_lbs > 0
            or self.over_capacity_volume_cuft > 0
            or self.over_capacity_linear_feet > 0
            or self.over_capacity_pallets > 0
        )

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
        d["display_remaining_weight_lbs"] = self.display_remaining_weight_lbs
        d["display_remaining_volume_cuft"] = self.display_remaining_volume_cuft
        d["display_remaining_linear_feet"] = self.display_remaining_linear_feet
        d["display_remaining_pallets"] = self.display_remaining_pallets
        d["over_capacity_weight_lbs"] = self.over_capacity_weight_lbs
        d["over_capacity_volume_cuft"] = self.over_capacity_volume_cuft
        d["over_capacity_linear_feet"] = self.over_capacity_linear_feet
        d["over_capacity_pallets"] = self.over_capacity_pallets
        d["is_over_capacity"] = self.is_over_capacity
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
    duty_status: str = "UNKNOWN"
    required_break_due_at: str | None = None
    reset_eligible_at: str | None = None

    hos_source: str = ""
    hos_observed_at: str | None = None
    hos_status: str = "UNKNOWN"
    confidence: str = "LOW"

    time_window_start: str = ""
    time_window_end: str = ""

    def __post_init__(self) -> None:
        if self.hos_status not in HOS_STATUSES:
            raise ValueError(f"Invalid hos_status: {self.hos_status!r}. Must be one of {HOS_STATUSES}")
        if self.duty_status not in DUTY_STATUSES:
            raise ValueError(f"Invalid duty_status: {self.duty_status!r}. Must be one of {DUTY_STATUSES}")

    @property
    def is_actionable(self) -> bool:
        """Whether the HOS snapshot can carry an operational comparison at all."""
        return self.hos_status in ("VERIFIED", "ESTIMATED", "STALE")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_actionable"] = self.is_actionable
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
    """How the trailer is currently arranged.

    The tri-state fields default to unknown on purpose. An empty record means
    nobody told us how the freight sits; it does not mean the freight stacks.
    """

    arrangement_type: str = "unknown"
    stacking_policy: str = "UNKNOWN"
    allows_top_load: bool | None = None  # None == UNKNOWN
    requires_floor_position: bool = True  # conservative: assume floor space is needed
    max_stack_height_inches: float | None = None
    liftgate_required: bool = False
    multi_stop_lifo_required: bool = False
    securement_status: str = "UNVERIFIED"
    temp_target_fahrenheit: float | None = None

    def __post_init__(self) -> None:
        if self.stacking_policy not in STACKING_POLICIES:
            raise ValueError(f"Invalid stacking_policy: {self.stacking_policy!r}. Must be one of {STACKING_POLICIES}")
        if self.arrangement_type not in ARRANGEMENT_TYPES:
            raise ValueError(f"Invalid arrangement_type: {self.arrangement_type!r}. Must be one of {ARRANGEMENT_TYPES}")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Stop:
    """One stop on a candidate or committed sequence.

    Service and drive time are Optional because an unrecorded dwell is not a
    zero-minute dwell; the evaluation reports the gap instead of pretending the
    driver teleports through the dock.
    """

    stop_id: str = ""
    sequence: int = 0
    location: str = ""
    stop_type: str = "delivery"  # pickup | delivery
    appointment_start: str = ""
    appointment_end: str = ""
    service_hours: float | None = None
    drive_hours_to_stop: float | None = None
    out_of_route_miles: float = 0.0
    cargo_unit_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stop_id:
            self.stop_id = f"STOP-{uuid.uuid4().hex[:6].upper()}"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StopSequenceCapacity:
    # max_stops is Optional: an asset whose stop ceiling was never set does not
    # thereby get a ceiling of five.
    max_stops: int | None = None
    assigned_stops: int = 0
    route_out_of_route_miles: float = 0.0
    max_out_of_route_miles: float | None = None
    stops: list[Stop] = field(default_factory=list)

    @property
    def remaining_stops(self) -> int | None:
        if self.max_stops is None:
            return None
        return self.max_stops - self.assigned_stops

    def to_dict(self) -> dict:
        d = asdict(self)
        d["remaining_stops"] = self.remaining_stops
        return d


@dataclass
class CapacityLedgerEntry:
    """A recorded consumption of capacity, either projected or committed.

    Candidates and commitments live in separate lists on purpose. A projected
    opportunity is a Possible Future; it may be evaluated, scored and displayed,
    but it may never move the utilization numbers that describe Current
    Reality.
    """

    ref_id: str = ""
    kind: str = "PROJECTED"  # PROJECTED | COMMITTED
    weight_lbs: float = 0.0
    linear_feet: float = 0.0
    volume_cuft: float = 0.0
    pallets: int = 0
    drive_hours: float = 0.0
    recorded_by: str = ""
    authority_ref: str = ""
    recorded_at: str = ""

    def __post_init__(self) -> None:
        if not self.recorded_at:
            self.recorded_at = _utc_now()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CapacityAssessment:
    """The advisory answer: what fits, what does not, and what nobody knows.

    The fit concepts are reported separately and are never collapsed into one
    verdict. `physical_fit`, `baseline_fit` and `reserve_required` are
    tri-state -- None means the question could not be answered from the data
    available, which is different from answering "no".

    This object carries no authority. `clear_to_proceed` means "the engine has
    no objection and no question", not "accepted".
    """

    capacity_id: str = ""
    physical_fit: bool | None = None
    baseline_fit: bool | None = None
    reserve_required: bool | None = None
    exceeds_total_capacity: bool = False
    data_sufficient: bool = True
    requires_human_review: bool = False
    findings: list[CapacityFinding] = field(default_factory=list)
    reserve_impacts: dict[str, ReserveImpact] = field(default_factory=dict)
    remaining: dict[str, float] = field(default_factory=dict)
    over_capacity: dict[str, float] = field(default_factory=dict)
    stop_sequence: dict = field(default_factory=dict)
    time: dict = field(default_factory=dict)
    arrangement: dict = field(default_factory=dict)
    is_simulation: bool = False
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.evaluated_at:
            self.evaluated_at = _utc_now()

    @property
    def codes(self) -> set[str]:
        return {f.code for f in self.findings}

    @property
    def blocking_findings(self) -> list[CapacityFinding]:
        return [f for f in self.findings if f.severity == SEVERITY_BLOCKING]

    @property
    def review_findings(self) -> list[CapacityFinding]:
        return [f for f in self.findings if f.requires_human_review]

    @property
    def data_gaps(self) -> list[CapacityFinding]:
        return [f for f in self.findings if f.data_gap]

    @property
    def status(self) -> str:
        """Single roll-up label, ordered by what a dispatcher must act on first."""
        if not self.data_sufficient:
            return "INSUFFICIENT_DATA"
        if self.exceeds_total_capacity:
            return "EXCEEDS_TOTAL_CAPACITY"
        if self.blocking_findings:
            return "BLOCKED"
        # Reserve consumption is checked before the generic review label: it is
        # the more specific answer, and it already implies a human decision.
        if self.reserve_required:
            return "FITS_ONLY_BY_CONSUMING_RESERVE"
        if self.requires_human_review:
            return "REQUIRES_HUMAN_REVIEW"
        if self.baseline_fit:
            return "FITS_WITHIN_BASELINE"
        return "NOT_EVALUATED"

    @property
    def clear_to_proceed(self) -> bool:
        """No objection and no open question. Not an acceptance."""
        return (
            self.data_sufficient
            and not self.exceeds_total_capacity
            and not self.requires_human_review
            and not self.blocking_findings
            and self.baseline_fit is not False
        )

    def has_code(self, code: str) -> bool:
        return code in self.codes

    def findings_for(self, code: str) -> list[CapacityFinding]:
        return [f for f in self.findings if f.code == code]

    def __bool__(self) -> bool:
        return self.clear_to_proceed

    def __iter__(self):
        """Compatibility shim for `fits, findings = cap.can_accommodate(...)`.

        The engine used to return a bare tuple. Callers that still unpack get
        the same shape, except the second element is structured findings rather
        than English sentences nobody could branch on safely.
        """
        yield self.clear_to_proceed
        yield self.findings

    def to_dict(self) -> dict:
        return {
            "capacity_id": self.capacity_id,
            "status": self.status,
            "physical_fit": self.physical_fit,
            "baseline_fit": self.baseline_fit,
            "reserve_required": self.reserve_required,
            "exceeds_total_capacity": self.exceeds_total_capacity,
            "data_sufficient": self.data_sufficient,
            "requires_human_review": self.requires_human_review,
            "clear_to_proceed": self.clear_to_proceed,
            "findings": [f.to_dict() for f in self.findings],
            "reserve_impacts": {k: v.to_dict() for k, v in self.reserve_impacts.items()},
            "remaining": dict(self.remaining),
            "over_capacity": dict(self.over_capacity),
            "stop_sequence": dict(self.stop_sequence),
            "time": dict(self.time),
            "arrangement": dict(self.arrangement),
            "is_simulation": self.is_simulation,
            "evaluated_at": self.evaluated_at,
        }


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
    committed: list[CapacityLedgerEntry] = field(default_factory=list)
    projected: list[CapacityLedgerEntry] = field(default_factory=list)
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
        source: str,
        equipment_type: str = "dry_van",
        version: str = "1.0",
        verified_by: str | None = None,
        has_liftgate: bool = False,
        has_ramp: bool = False,
        has_temp_control: bool = False,
    ) -> None:
        """Update the verified equipment specification in place.

        Two rules govern this method.

        First, the profile updates the *specification* only. Utilization
        (used_weight_lbs and friends) describes freight physically on the
        trailer right now; re-reading a spec sheet does not unload it, so the
        used_* fields are left exactly as they were.

        Second, nothing here manufactures a verification. `source` is required
        and `verified_by` has no default: a profile applied without a named
        actor lands in UNVERIFIED, not VERIFIED, and downstream evaluation asks
        a human about it. Stamping an operator's name on data they never saw is
        prohibited outright.
        """
        if not asset_profile_id or not str(asset_profile_id).strip():
            raise ValueError("apply_asset_profile requires an asset_profile_id")
        if not source or not str(source).strip():
            raise ValueError("apply_asset_profile requires an explicit source (where this specification came from)")

        actor = (verified_by or "").strip()
        physical = self.physical
        physical.asset_profile_id = asset_profile_id
        physical.asset_profile_version = version
        physical.configuration_source = source
        if actor:
            physical.configuration_status = "VERIFIED"
            physical.configuration_verified_at = _utc_now()
            physical.configuration_verified_by = actor
        else:
            physical.configuration_status = "UNVERIFIED"
            physical.configuration_verified_at = None
            physical.configuration_verified_by = None
        physical.max_weight_lbs = max_weight_lbs
        physical.max_volume_cuft = max_volume_cuft
        physical.max_linear_feet = max_linear_feet
        physical.max_pallets = max_pallets
        physical.equipment_type = equipment_type
        physical.has_liftgate = has_liftgate
        physical.has_ramp = has_ramp
        physical.has_temp_control = has_temp_control
        self.updated_at = _utc_now()

    def set_hos_snapshot(
        self,
        remaining_drive_hours: float,
        remaining_duty_hours: float,
        remaining_cycle_hours: float,
        source: str,
        status: str = "ESTIMATED",
        observed_at: str | None = None,
        duty_status: str = "UNKNOWN",
        confidence: str = "LOW",
        drive_limit_hours: float = 11.0,
        duty_limit_hours: float = 14.0,
        cycle_limit_hours: float = 70.0,
    ) -> None:
        """Record an HOS snapshot with an explicit provenance.

        `source` is required because the previous default claimed every
        snapshot came from an ELD integration that does not exist in this
        program. A VERIFIED status additionally requires the observation time,
        since a verification with no "as of" is not a verification -- an hour
        later it is only a memory.
        """
        if status not in HOS_STATUSES:
            raise ValueError(f"Invalid hos status: {status!r}. Must be one of {HOS_STATUSES}")
        if not source or not str(source).strip():
            raise ValueError("HOS snapshot requires an explicit source (ELD vendor, driver report, dispatcher estimate)")
        if status == "VERIFIED":
            if not observed_at or not str(observed_at).strip():
                raise ValueError("hos_status 'VERIFIED' requires observed_at (when the snapshot was actually taken)")
            _, ts_status = parse_operational_timestamp(observed_at)
            if ts_status != TIMESTAMP_PARSED:
                raise ValueError(f"observed_at is not a timezone-aware timestamp ({ts_status}): {observed_at!r}")

        self.time = TimeCapacity(
            drive_limit_hours=drive_limit_hours,
            duty_limit_hours=duty_limit_hours,
            cycle_limit_hours=cycle_limit_hours,
            remaining_drive_hours=remaining_drive_hours,
            remaining_duty_hours=remaining_duty_hours,
            remaining_cycle_hours=remaining_cycle_hours,
            duty_status=duty_status,
            hos_source=source,
            hos_observed_at=observed_at,
            hos_status=status,
            confidence=confidence,
            time_window_start=self.time.time_window_start,
            time_window_end=self.time.time_window_end,
        )
        self.updated_at = _utc_now()

    def set_verified_hos(
        self,
        remaining_drive_hours: float,
        remaining_duty_hours: float,
        remaining_cycle_hours: float,
        source: str,
        observed_at: str,
        duty_status: str = "ON_DUTY",
        confidence: str = "HIGH",
    ) -> None:
        """Record a VERIFIED HOS snapshot. Both source and observed_at required."""
        self.set_hos_snapshot(
            remaining_drive_hours=remaining_drive_hours,
            remaining_duty_hours=remaining_duty_hours,
            remaining_cycle_hours=remaining_cycle_hours,
            source=source,
            status="VERIFIED",
            observed_at=observed_at,
            duty_status=duty_status,
            confidence=confidence,
        )

    def record_projected_opportunity(
        self,
        ref_id: str,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
        recorded_by: str = "",
    ) -> CapacityLedgerEntry:
        """Record a Possible Future against this asset without touching reality.

        Deliberately does not move used_* by so much as a pound. Projections
        exist so a dispatcher can see what a candidate would cost; the moment
        they silently consumed real capacity, the asset's current state would
        become a fiction assembled from loads nobody accepted.
        """
        if not ref_id or not str(ref_id).strip():
            raise ValueError("record_projected_opportunity requires a ref_id identifying the candidate")
        if any(entry.ref_id == ref_id for entry in self.projected):
            raise ValueError(f"Projection already recorded for {ref_id!r}")
        entry = CapacityLedgerEntry(
            ref_id=ref_id,
            kind="PROJECTED",
            weight_lbs=weight_lbs,
            linear_feet=linear_feet,
            volume_cuft=volume_cuft,
            pallets=pallets,
            drive_hours=drive_hours,
            recorded_by=recorded_by,
        )
        self.projected.append(entry)
        return entry

    def record_committed_load(
        self,
        ref_id: str,
        committed_by: str,
        authority_ref: str,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
    ) -> CapacityLedgerEntry:
        """Record a commitment somebody else already made.

        Capacity holds no lifecycle authority: it cannot commit a load, so this
        method only *transcribes* a commitment, and it refuses to transcribe an
        anonymous one. Both the human actor and the authoritative record (the
        Spine load id, the signed rate confirmation) are required, and the
        refusal happens before any field is touched so a rejected call leaves
        utilization untouched.
        """
        if not ref_id or not str(ref_id).strip():
            raise ValueError("record_committed_load requires a ref_id")
        if not committed_by or not str(committed_by).strip():
            raise ValueError("record_committed_load requires committed_by; Dynamic Capacity holds no commitment authority")
        if not authority_ref or not str(authority_ref).strip():
            raise ValueError("record_committed_load requires authority_ref identifying the record that authorized the commitment")
        if any(entry.ref_id == ref_id for entry in self.committed):
            raise ValueError(f"Commitment already recorded for {ref_id!r}")

        entry = CapacityLedgerEntry(
            ref_id=ref_id,
            kind="COMMITTED",
            weight_lbs=weight_lbs,
            linear_feet=linear_feet,
            volume_cuft=volume_cuft,
            pallets=pallets,
            drive_hours=drive_hours,
            recorded_by=committed_by,
            authority_ref=authority_ref,
        )
        self.committed.append(entry)
        self.physical.used_weight_lbs += weight_lbs
        self.physical.used_linear_feet += linear_feet
        self.physical.used_volume_cuft += volume_cuft
        self.physical.used_pallets += pallets
        # The candidate is now reality; drop its projection so the same freight
        # is never counted twice.
        self.projected = [p for p in self.projected if p.ref_id != ref_id]
        self.updated_at = _utc_now()
        return entry

    def projected_utilization(self) -> dict:
        """Utilization if every recorded projection were committed. Computed, never stored."""
        return {
            "weight_lbs": self.physical.used_weight_lbs + sum(p.weight_lbs for p in self.projected),
            "linear_feet": self.physical.used_linear_feet + sum(p.linear_feet for p in self.projected),
            "volume_cuft": self.physical.used_volume_cuft + sum(p.volume_cuft for p in self.projected),
            "pallets": self.physical.used_pallets + sum(p.pallets for p in self.projected),
            "drive_hours": sum(p.drive_hours for p in self.projected),
            "projection_count": len(self.projected),
            "committed_count": len(self.committed),
        }

    def _evaluate_asset_configuration(self) -> list[CapacityFinding]:
        status = self.physical.configuration_status
        ref = "physical.configuration_status"
        if status in ("UNCONFIGURED", "INVALID"):
            return [
                CapacityFinding(
                    code="ASSET_CONFIGURATION_UNUSABLE",
                    dimension=DIMENSION_ASSET,
                    severity=SEVERITY_BLOCKING,
                    message=f"Asset physical configuration is {status}; no capacity claim can be made about this asset",
                    source_ref=ref,
                    requires_human_review=True,
                    data_gap=True,
                )
            ]
        if status == "STALE":
            # This is the case that used to slip through as feasible: the old
            # roll-up treated a lone stale-configuration note as harmless.
            # Stale specs are exactly the ones that overload an axle.
            return [
                CapacityFinding(
                    code="ASSET_CONFIGURATION_STALE",
                    dimension=DIMENSION_ASSET,
                    severity=SEVERITY_ADVISORY,
                    message="Asset configuration is STALE; the recorded specification may no longer match the equipment",
                    source_ref=ref,
                    requires_human_review=True,
                )
            ]
        if status in ("PARTIAL", "UNVERIFIED"):
            return [
                CapacityFinding(
                    code="ASSET_CONFIGURATION_UNVERIFIED",
                    dimension=DIMENSION_ASSET,
                    severity=SEVERITY_ADVISORY,
                    message=f"Asset configuration is {status}; no actor has attested to this specification",
                    source_ref=ref,
                    requires_human_review=True,
                )
            ]
        return []

    def _evaluate_stops(self, stops: list[Stop]) -> tuple[list[CapacityFinding], dict]:
        """Stop count, appointments, service time, drive time, out-of-route.

        Appointment feasibility is walked forward through the sequence with
        real timezone-aware arithmetic: arrive, wait for the window to open,
        serve, drive on. A stop that cannot be reached inside its window is a
        blocking finding, not a note in a string.
        """
        findings: list[CapacityFinding] = []
        summary: dict = {
            "stop_count": len(stops),
            "assigned_stops": self.stop_sequence.assigned_stops,
            "max_stops": self.stop_sequence.max_stops,
            "remaining_stops": self.stop_sequence.remaining_stops,
            "total_service_hours": None,
            "total_drive_hours": None,
            "total_out_of_route_miles": None,
            "appointments_evaluated": False,
            "projected_arrivals": [],
        }
        if not stops:
            return findings, summary

        ordered = sorted(stops, key=lambda s: s.sequence)

        # Stop count against the asset's stop ceiling.
        total_stops = self.stop_sequence.assigned_stops + len(ordered)
        summary["projected_stop_count"] = total_stops
        if self.stop_sequence.max_stops is None:
            findings.append(
                CapacityFinding(
                    code="STOP_CAPACITY_UNKNOWN",
                    dimension=DIMENSION_STOP_SEQUENCE,
                    severity=SEVERITY_ADVISORY,
                    message=f"{len(ordered)} stops requested but the asset has no recorded stop ceiling",
                    source_ref="stop_sequence.max_stops",
                    requires_human_review=True,
                )
            )
        elif total_stops > self.stop_sequence.max_stops:
            findings.append(
                CapacityFinding(
                    code="CAPACITY_EXCEEDED_STOPS",
                    dimension=DIMENSION_STOP_SEQUENCE,
                    severity=SEVERITY_BLOCKING,
                    message=(
                        f"{total_stops} stops ({self.stop_sequence.assigned_stops} assigned + {len(ordered)} requested) "
                        f"exceeds the ceiling of {self.stop_sequence.max_stops}"
                    ),
                    source_ref="stop_sequence.max_stops",
                    requires_human_review=True,
                )
            )

        # Service and drive time totals; an unrecorded value makes the total
        # unknown rather than optimistically small.
        service_values = [s.service_hours for s in ordered]
        if any(v is None for v in service_values):
            for stop in [s for s in ordered if s.service_hours is None]:
                findings.append(
                    CapacityFinding(
                        code="STOP_SERVICE_TIME_UNKNOWN",
                        dimension=DIMENSION_STOP_SEQUENCE,
                        severity=SEVERITY_ADVISORY,
                        message=f"Stop {stop.stop_id} ({stop.location or 'unnamed'}) has no recorded service time",
                        source_ref=f"stop[{stop.sequence}].service_hours",
                        requires_human_review=True,
                        data_gap=True,
                    )
                )
        else:
            summary["total_service_hours"] = _round(sum(service_values))

        drive_values = [s.drive_hours_to_stop for s in ordered]
        if any(v is None for v in drive_values):
            for stop in [s for s in ordered if s.drive_hours_to_stop is None]:
                findings.append(
                    CapacityFinding(
                        code="STOP_DRIVE_TIME_UNKNOWN",
                        dimension=DIMENSION_STOP_SEQUENCE,
                        severity=SEVERITY_ADVISORY,
                        message=f"Stop {stop.stop_id} ({stop.location or 'unnamed'}) has no recorded drive time",
                        source_ref=f"stop[{stop.sequence}].drive_hours_to_stop",
                        requires_human_review=True,
                        data_gap=True,
                    )
                )
        else:
            summary["total_drive_hours"] = _round(sum(drive_values))

        out_of_route = sum(s.out_of_route_miles for s in ordered) + self.stop_sequence.route_out_of_route_miles
        summary["total_out_of_route_miles"] = _round(out_of_route)
        ceiling = self.stop_sequence.max_out_of_route_miles
        if ceiling is not None and out_of_route > ceiling:
            findings.append(
                CapacityFinding(
                    code="OUT_OF_ROUTE_EXCEEDED",
                    dimension=DIMENSION_STOP_SEQUENCE,
                    severity=SEVERITY_BLOCKING,
                    message=f"Sequence adds {_round(out_of_route)} out-of-route miles against a ceiling of {ceiling}",
                    source_ref="stop_sequence.max_out_of_route_miles",
                    requires_human_review=True,
                )
            )
        elif out_of_route > 0:
            findings.append(
                CapacityFinding(
                    code="OUT_OF_ROUTE_IMPACT",
                    dimension=DIMENSION_STOP_SEQUENCE,
                    severity=SEVERITY_INFO,
                    message=f"Sequence adds {_round(out_of_route)} out-of-route miles",
                    source_ref="stop_sequence.route_out_of_route_miles",
                )
            )

        # Appointment windows: parse first, compare never as strings.
        parsed: dict[str, tuple[datetime | None, datetime | None]] = {}
        timestamps_usable = True
        for stop in ordered:
            start, start_status = parse_operational_timestamp(stop.appointment_start)
            end, end_status = parse_operational_timestamp(stop.appointment_end)
            for label, value, ts_status in (
                ("appointment_start", stop.appointment_start, start_status),
                ("appointment_end", stop.appointment_end, end_status),
            ):
                if ts_status == TIMESTAMP_MISSING:
                    timestamps_usable = False
                    findings.append(
                        CapacityFinding(
                            code="STOP_APPOINTMENT_MISSING",
                            dimension=DIMENSION_STOP_SEQUENCE,
                            severity=SEVERITY_ADVISORY,
                            message=f"Stop {stop.stop_id} has no {label}; appointment feasibility cannot be evaluated",
                            source_ref=f"stop[{stop.sequence}].{label}",
                            requires_human_review=True,
                            data_gap=True,
                        )
                    )
                elif ts_status in (TIMESTAMP_INVALID, TIMESTAMP_NAIVE):
                    timestamps_usable = False
                    detail = (
                        "is not a parseable timestamp"
                        if ts_status == TIMESTAMP_INVALID
                        else "carries no timezone, so the intended local time is ambiguous"
                    )
                    findings.append(
                        CapacityFinding(
                            code="STOP_APPOINTMENT_TIMESTAMP_UNUSABLE",
                            dimension=DIMENSION_STOP_SEQUENCE,
                            severity=SEVERITY_BLOCKING,
                            message=f"Stop {stop.stop_id} {label} {detail}: {value!r}",
                            source_ref=f"stop[{stop.sequence}].{label}",
                            requires_human_review=True,
                            data_gap=True,
                        )
                    )
            parsed[stop.stop_id] = (start, end)
            if start and end and end < start:
                findings.append(
                    CapacityFinding(
                        code="STOP_APPOINTMENT_WINDOW_INVALID",
                        dimension=DIMENSION_STOP_SEQUENCE,
                        severity=SEVERITY_BLOCKING,
                        message=f"Stop {stop.stop_id} appointment window closes ({stop.appointment_end}) before it opens ({stop.appointment_start})",
                        source_ref=f"stop[{stop.sequence}].appointment_end",
                        requires_human_review=True,
                    )
                )

        if not timestamps_usable:
            return findings, summary

        # Chronological conflicts across the sequence.
        for earlier, later in zip(ordered, ordered[1:]):
            e_start, _ = parsed[earlier.stop_id]
            l_start, _ = parsed[later.stop_id]
            if e_start and l_start and l_start < e_start:
                findings.append(
                    CapacityFinding(
                        code="STOP_APPOINTMENT_CONFLICT",
                        dimension=DIMENSION_STOP_SEQUENCE,
                        severity=SEVERITY_BLOCKING,
                        message=(
                            f"Stop {later.stop_id} (sequence {later.sequence}) opens before stop {earlier.stop_id} "
                            f"(sequence {earlier.sequence}); the route order contradicts the appointments"
                        ),
                        source_ref=f"stop[{later.sequence}].appointment_start",
                        requires_human_review=True,
                    )
                )

        # Walk the sequence forward: arrive, wait for the window, serve, drive.
        if summary["total_drive_hours"] is None or summary["total_service_hours"] is None:
            return findings, summary

        cursor = parsed[ordered[0].stop_id][0]
        if cursor is not None:
            cursor = cursor - timedelta(hours=ordered[0].drive_hours_to_stop or 0.0)
        arrivals = []
        for stop in ordered:
            start, end = parsed[stop.stop_id]
            arrival = cursor + timedelta(hours=stop.drive_hours_to_stop or 0.0)
            arrivals.append({"stop_id": stop.stop_id, "sequence": stop.sequence, "projected_arrival": arrival.isoformat()})
            if end is not None and arrival > end:
                late_hours = _round((arrival - end).total_seconds() / 3600.0)
                findings.append(
                    CapacityFinding(
                        code="STOP_APPOINTMENT_INFEASIBLE",
                        dimension=DIMENSION_STOP_SEQUENCE,
                        severity=SEVERITY_BLOCKING,
                        message=(
                            f"Stop {stop.stop_id} projected arrival {arrival.isoformat()} is {late_hours} hours after "
                            f"its window closes at {stop.appointment_end}"
                        ),
                        source_ref=f"stop[{stop.sequence}].appointment_end",
                        requires_human_review=True,
                    )
                )
            service_start = max(arrival, start) if start is not None else arrival
            cursor = service_start + timedelta(hours=stop.service_hours or 0.0)
        summary["appointments_evaluated"] = True
        summary["projected_arrivals"] = arrivals
        summary["sequence_completes_at"] = cursor.isoformat()
        return findings, summary

    def _evaluate_arrangement(
        self,
        arrangement: TruckArrangement | None,
        stops: list[Stop],
    ) -> tuple[list[CapacityFinding], dict]:
        """LIFO, access order, blocking and securement, derived from cargo geometry."""
        findings: list[CapacityFinding] = []
        lifo_required = self.cargo.multi_stop_lifo_required or (arrangement.stop_sequence_lifo if arrangement else False)

        if arrangement is None:
            if len(stops) > 1 or self.cargo.multi_stop_lifo_required:
                findings.append(
                    CapacityFinding(
                        code="CARGO_ARRANGEMENT_NOT_PROVIDED",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_ADVISORY,
                        message="Multi-stop sequence evaluated without a Truck Arrangement; LIFO and blocking cannot be derived",
                        source_ref="arrangement",
                        requires_human_review=True,
                        data_gap=True,
                    )
                )
            return findings, {"status": "NOT_EVALUATED"}

        assessment = arrangement.evaluate_arrangement()
        severity_for_unknown = SEVERITY_BLOCKING if lifo_required else SEVERITY_ADVISORY

        if assessment.lifo_status == "INFEASIBLE":
            for violation in assessment.violations:
                if violation.code in ("LIFO_ORDER_VIOLATION", "DELIVERY_SEQUENCE_MISMATCH"):
                    findings.append(
                        CapacityFinding(
                            code="CARGO_LIFO_INFEASIBLE",
                            dimension=DIMENSION_CARGO,
                            severity=SEVERITY_BLOCKING,
                            message=violation.message,
                            source_ref=f"arrangement.units[{violation.unit_id}]",
                            requires_human_review=True,
                        )
                    )
        elif assessment.lifo_status == "UNKNOWN":
            findings.append(
                CapacityFinding(
                    code="CARGO_LIFO_UNKNOWN",
                    dimension=DIMENSION_CARGO,
                    severity=severity_for_unknown,
                    message="LIFO feasibility cannot be derived: loading, unloading or delivery order was never recorded",
                    source_ref="arrangement.units",
                    requires_human_review=True,
                    data_gap=True,
                )
            )

        if assessment.access_status == "INFEASIBLE":
            for violation in assessment.violations:
                if violation.code == "ACCESS_ORDER_VIOLATION":
                    findings.append(
                        CapacityFinding(
                            code="CARGO_ACCESS_ORDER_INFEASIBLE",
                            dimension=DIMENSION_CARGO,
                            severity=SEVERITY_BLOCKING,
                            message=violation.message,
                            source_ref=f"arrangement.units[{violation.unit_id}]",
                            requires_human_review=True,
                        )
                    )
        elif assessment.access_status == "UNKNOWN":
            findings.append(
                CapacityFinding(
                    code="CARGO_ACCESS_ORDER_UNKNOWN",
                    dimension=DIMENSION_CARGO,
                    severity=severity_for_unknown,
                    message="Access order cannot be derived from the recorded cargo units",
                    source_ref="arrangement.units",
                    requires_human_review=True,
                    data_gap=True,
                )
            )

        if assessment.blocking_status == "INFEASIBLE":
            for violation in assessment.violations:
                if violation.code == "CARGO_BLOCKED":
                    findings.append(
                        CapacityFinding(
                            code="CARGO_BLOCKED",
                            dimension=DIMENSION_CARGO,
                            severity=SEVERITY_BLOCKING,
                            message=violation.message,
                            source_ref=f"arrangement.units[{violation.unit_id}]",
                            requires_human_review=True,
                        )
                    )
        elif assessment.blocking_status == "UNKNOWN":
            findings.append(
                CapacityFinding(
                    code="CARGO_BLOCKING_UNKNOWN",
                    dimension=DIMENSION_CARGO,
                    severity=severity_for_unknown,
                    message="Cargo blocking relationships cannot be derived from the recorded cargo units",
                    source_ref="arrangement.units",
                    requires_human_review=True,
                    data_gap=True,
                )
            )

        if assessment.securement_status != "VERIFIED":
            findings.append(
                CapacityFinding(
                    code="CARGO_SECUREMENT_UNVERIFIED",
                    dimension=DIMENSION_CARGO,
                    severity=SEVERITY_ADVISORY,
                    message=f"Cargo securement is {assessment.securement_status}; no actor has attested to it",
                    source_ref="arrangement.securement_status",
                    requires_human_review=True,
                )
            )

        if arrangement.requires_temperature_control and not self.physical.has_temp_control:
            findings.append(
                CapacityFinding(
                    code="EQUIPMENT_TEMP_CONTROL_MISSING",
                    dimension=DIMENSION_PHYSICAL,
                    severity=SEVERITY_BLOCKING,
                    message="Arrangement requires temperature control; the asset has none recorded",
                    source_ref="physical.has_temp_control",
                    requires_human_review=True,
                )
            )
        return findings, assessment.to_dict()

    def _evaluate_cargo_policy(
        self,
        stacking_policy: str,
        requires_floor_position: bool,
        linear_impact: ReserveImpact,
    ) -> list[CapacityFinding]:
        findings: list[CapacityFinding] = []
        if stacking_policy not in STACKING_POLICIES:
            raise ValueError(f"Invalid stacking_policy: {stacking_policy!r}. Must be one of {STACKING_POLICIES}")

        if stacking_policy == "UNKNOWN":
            findings.append(
                CapacityFinding(
                    code="CARGO_STACKING_POLICY_UNKNOWN",
                    dimension=DIMENSION_CARGO,
                    severity=SEVERITY_ADVISORY,
                    message="Incoming cargo stacking policy is unknown; stackability cannot be assumed",
                    source_ref="request.stacking_policy",
                    requires_human_review=True,
                    data_gap=True,
                )
            )
            return findings

        if stacking_policy == "NON_STACKABLE":
            if requires_floor_position and linear_impact.evaluated and linear_impact.exceeds_total:
                findings.append(
                    CapacityFinding(
                        code="CARGO_FLOOR_POSITION_UNAVAILABLE",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_BLOCKING,
                        message=(
                            f"Non-stackable freight needs {linear_impact.requested} ft of floor against "
                            f"{linear_impact.raw_remaining} ft remaining; it cannot be stacked out of the way"
                        ),
                        source_ref="physical.remaining_linear_feet",
                        requires_human_review=True,
                    )
                )
            if self.cargo.stacking_policy == "NON_STACKABLE" and self.cargo.allows_top_load is False:
                findings.append(
                    CapacityFinding(
                        code="CARGO_ARRANGEMENT_FORBIDS_PLACEMENT",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_BLOCKING,
                        message="Current arrangement is non-stackable and forbids top load; there is nowhere to place this freight",
                        source_ref="cargo.stacking_policy",
                        requires_human_review=True,
                    )
                )
        elif stacking_policy == "TOP_LOAD":
            if self.cargo.allows_top_load is None:
                findings.append(
                    CapacityFinding(
                        code="CARGO_TOP_LOAD_POLICY_UNKNOWN",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_ADVISORY,
                        message="Top-load freight offered but the current arrangement's top-load policy was never recorded",
                        source_ref="cargo.allows_top_load",
                        requires_human_review=True,
                        data_gap=True,
                    )
                )
            elif self.cargo.allows_top_load is False:
                findings.append(
                    CapacityFinding(
                        code="CARGO_TOP_LOAD_FORBIDDEN",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_BLOCKING,
                        message="Top-load freight cannot be placed on the current cargo arrangement",
                        source_ref="cargo.allows_top_load",
                        requires_human_review=True,
                    )
                )
        elif stacking_policy == "STACKABLE":
            if self.cargo.stacking_policy == "NON_STACKABLE" and self.cargo.allows_top_load is False:
                findings.append(
                    CapacityFinding(
                        code="CARGO_ARRANGEMENT_FORBIDS_PLACEMENT",
                        dimension=DIMENSION_CARGO,
                        severity=SEVERITY_BLOCKING,
                        message="Current arrangement is non-stackable and forbids top load; stackable freight still has nowhere to go",
                        source_ref="cargo.stacking_policy",
                        requires_human_review=True,
                    )
                )
        return findings

    def _evaluate_time(
        self,
        drive_hours: float,
        service_hours: float | None,
        duty_hours: float | None,
        stop_summary: dict,
        is_simulation: bool,
    ) -> tuple[dict[str, ReserveImpact], list[CapacityFinding], dict]:
        """Drive, duty, cycle, service, break and window -- each compared, not merely computed."""
        findings: list[CapacityFinding] = []
        impacts: dict[str, ReserveImpact] = {}

        stop_drive = stop_summary.get("total_drive_hours")
        stop_service = stop_summary.get("total_service_hours")

        drive_total = drive_hours
        if drive_hours <= 0 and stop_drive is not None:
            drive_total = stop_drive
        elif drive_hours > 0 and stop_drive is not None and abs(stop_drive - drive_hours) > DRIVE_TIME_DISAGREEMENT_HOURS:
            findings.append(
                CapacityFinding(
                    code="DRIVE_TIME_SOURCE_DISAGREEMENT",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_ADVISORY,
                    message=(
                        f"Requested drive time {drive_hours} hrs disagrees with the stop sequence total {stop_drive} hrs; "
                        f"the larger figure is used for the comparison"
                    ),
                    source_ref="request.drive_hours",
                    requires_human_review=True,
                )
            )
            drive_total = max(drive_hours, stop_drive)

        service_total = service_hours
        if service_total is None:
            service_total = stop_service

        time_requested = drive_total > 0 or bool(duty_hours) or (service_total or 0) > 0
        summary: dict = {
            "drive_hours_required": _round(drive_total),
            "service_hours_required": None if service_total is None else _round(service_total),
            "break_required": False,
            "break_hours": 0.0,
            "duty_hours_required": None,
            "cycle_hours_required": None,
            "hos_status": self.time.hos_status,
        }
        if not time_requested:
            return impacts, findings, summary

        hos_usable = True
        if self.time.hos_status in ("UNKNOWN", "UNAVAILABLE"):
            hos_usable = False
            findings.append(
                CapacityFinding(
                    code="HOS_STATE_UNUSABLE",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_BLOCKING,
                    message=f"Driver HOS state is {self.time.hos_status}; no hours-of-service comparison can be made",
                    source_ref="time.hos_status",
                    requires_human_review=True,
                    data_gap=True,
                )
            )
        elif self.time.hos_status == "STALE":
            # A simulation is explicitly asking "what if this snapshot held?",
            # so a stale snapshot is an accepted input there. Against Current
            # Reality it is a question for a human.
            findings.append(
                CapacityFinding(
                    code="HOS_SNAPSHOT_STALE",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_ADVISORY,
                    message="Driver HOS snapshot is stale"
                    + (" (accepted as a simulation input)" if is_simulation else ""),
                    source_ref="time.hos_status",
                    requires_human_review=not is_simulation,
                )
            )
        elif self.time.hos_status == "ESTIMATED":
            findings.append(
                CapacityFinding(
                    code="HOS_SNAPSHOT_ESTIMATED",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_ADVISORY,
                    message=f"Driver HOS is an estimate from {self.time.hos_source or 'an unnamed source'}, not a verified reading"
                    + (" (accepted as a simulation input)" if is_simulation else ""),
                    source_ref="time.hos_status",
                    requires_human_review=not is_simulation,
                )
            )

        break_hours = 0.0
        if drive_total > BREAK_TRIGGER_DRIVE_HOURS:
            break_hours = REQUIRED_BREAK_HOURS
            summary["break_required"] = True
            summary["break_hours"] = break_hours
            findings.append(
                CapacityFinding(
                    code="BREAK_REQUIRED",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_INFO,
                    message=(
                        f"{drive_total} drive hours exceeds the {BREAK_TRIGGER_DRIVE_HOURS} hour break trigger; "
                        f"{REQUIRED_BREAK_HOURS} hours of duty time added for the required break"
                    ),
                    source_ref="time.remaining_duty_hours",
                )
            )

        impact, dim_findings = evaluate_reserve_dimension(
            dimension="drive_hours",
            requested=drive_total,
            raw_remaining=self.time.remaining_drive_hours,
            reserved=self.reserve.reserved_hos_hours,
            unit="hrs",
            source_ref="time.remaining_drive_hours",
            configured=hos_usable,
            insufficient_data_message="Driver HOS state is not usable, so drive hours cannot be compared",
        )
        impacts["drive_hours"] = impact
        findings.extend(dim_findings)

        if service_total is None:
            findings.append(
                CapacityFinding(
                    code="SERVICE_TIME_UNKNOWN",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_ADVISORY,
                    message="Loading/unloading service time was never recorded, so duty and cycle impact cannot be compared",
                    source_ref="request.service_hours",
                    requires_human_review=True,
                    data_gap=True,
                )
            )
            impacts["duty_hours"] = ReserveImpact(dimension="duty_hours", unit="hrs", source_ref="time.remaining_duty_hours")
            impacts["cycle_hours"] = ReserveImpact(dimension="cycle_hours", unit="hrs", source_ref="time.remaining_cycle_hours")
            return impacts, findings, summary

        duty_required = duty_hours if duty_hours is not None else drive_total + service_total + break_hours
        summary["duty_hours_required"] = _round(duty_required)
        summary["cycle_hours_required"] = _round(duty_required)

        impact, dim_findings = evaluate_reserve_dimension(
            dimension="duty_hours",
            requested=duty_required,
            raw_remaining=self.time.remaining_duty_hours,
            reserved=0.0,
            unit="hrs",
            source_ref="time.remaining_duty_hours",
            configured=hos_usable,
            insufficient_data_message="Driver HOS state is not usable, so duty hours cannot be compared",
        )
        impacts["duty_hours"] = impact
        findings.extend(dim_findings)

        impact, dim_findings = evaluate_reserve_dimension(
            dimension="cycle_hours",
            requested=duty_required,
            raw_remaining=self.time.remaining_cycle_hours,
            reserved=0.0,
            unit="hrs",
            source_ref="time.remaining_cycle_hours",
            configured=hos_usable,
            insufficient_data_message="Driver HOS state is not usable, so cycle hours cannot be compared",
        )
        impacts["cycle_hours"] = impact
        findings.extend(dim_findings)

        # Capacity window: the calendar span this asset is actually available.
        window_start, start_status = parse_operational_timestamp(self.time.time_window_start)
        window_end, end_status = parse_operational_timestamp(self.time.time_window_end)
        if TIMESTAMP_INVALID in (start_status, end_status) or TIMESTAMP_NAIVE in (start_status, end_status):
            findings.append(
                CapacityFinding(
                    code="CAPACITY_WINDOW_TIMESTAMP_UNUSABLE",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_BLOCKING,
                    message=(
                        f"Capacity window timestamps are unusable (start={start_status}, end={end_status}); "
                        f"they cannot be compared against the requested duty time"
                    ),
                    source_ref="time.time_window_start",
                    requires_human_review=True,
                    data_gap=True,
                )
            )
        elif window_start is not None and window_end is not None:
            window_hours = (window_end - window_start).total_seconds() / 3600.0
            summary["capacity_window_hours"] = _round(window_hours)
            if duty_required > window_hours:
                findings.append(
                    CapacityFinding(
                        code="CAPACITY_WINDOW_EXCEEDED",
                        dimension=DIMENSION_TIME,
                        severity=SEVERITY_BLOCKING,
                        message=(
                            f"Work requires {_round(duty_required)} hrs but the asset's capacity window is only "
                            f"{_round(window_hours)} hrs long"
                        ),
                        source_ref="time.time_window_end",
                        requires_human_review=True,
                    )
                )
        else:
            findings.append(
                CapacityFinding(
                    code="CAPACITY_WINDOW_NOT_EVALUATED",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_INFO,
                    message="No capacity window recorded on this asset; the window comparison was not performed",
                    source_ref="time.time_window_start",
                )
            )

        # A break already owed inside the trip is duty time somebody has to plan for.
        break_due, break_status = parse_operational_timestamp(self.time.required_break_due_at)
        if break_status in (TIMESTAMP_INVALID, TIMESTAMP_NAIVE):
            findings.append(
                CapacityFinding(
                    code="BREAK_DUE_TIMESTAMP_UNUSABLE",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_ADVISORY,
                    message=f"required_break_due_at is unusable ({break_status}): {self.time.required_break_due_at!r}",
                    source_ref="time.required_break_due_at",
                    requires_human_review=True,
                    data_gap=True,
                )
            )
        elif break_due is not None:
            summary["required_break_due_at"] = break_due.isoformat()
            findings.append(
                CapacityFinding(
                    code="BREAK_ALREADY_DUE",
                    dimension=DIMENSION_TIME,
                    severity=SEVERITY_INFO,
                    message=f"A required break is already scheduled at {break_due.isoformat()} and falls inside this work",
                    source_ref="time.required_break_due_at",
                )
            )
        return impacts, findings, summary

    def evaluate(
        self,
        weight_lbs: float = 0.0,
        linear_feet: float = 0.0,
        volume_cuft: float = 0.0,
        pallets: int = 0,
        drive_hours: float = 0.0,
        requires_liftgate: bool = False,
        stacking_policy: str = "UNKNOWN",
        requires_floor_position: bool = True,
        is_simulation: bool = False,
        service_hours: float | None = None,
        duty_hours: float | None = None,
        stops: list[Stop] | None = None,
        arrangement: TruckArrangement | None = None,
    ) -> CapacityAssessment:
        """Evaluate a candidate load against this asset. Purely advisory, never mutating.

        The evaluation reads state and returns an assessment. It does not
        reserve capacity, does not record the candidate, and does not decide
        anything -- recording is a separate, explicit act
        (`record_projected_opportunity` / `record_committed_load`).
        """
        stops = list(stops or [])
        findings: list[CapacityFinding] = []
        impacts: dict[str, ReserveImpact] = {}

        findings.extend(self._evaluate_asset_configuration())

        physical_specs = (
            ("weight", weight_lbs, self.physical.remaining_weight_lbs, self.reserve.reserved_weight_lbs, "lbs",
             self.physical.max_weight_lbs > 0, "physical.max_weight_lbs"),
            ("linear_feet", linear_feet, self.physical.remaining_linear_feet, self.reserve.reserved_linear_feet, "ft",
             self.physical.max_linear_feet > 0, "physical.max_linear_feet"),
            ("volume", volume_cuft, self.physical.remaining_volume_cuft, 0.0, "cuft",
             self.physical.max_volume_cuft > 0, "physical.max_volume_cuft"),
            ("pallets", pallets, float(self.physical.remaining_pallets), 0.0, "pallets",
             self.physical.max_pallets > 0, "physical.max_pallets"),
        )
        for dimension, requested, raw_remaining, reserved, unit, configured, ref in physical_specs:
            impact, dim_findings = evaluate_reserve_dimension(
                dimension=dimension,
                requested=requested,
                raw_remaining=raw_remaining,
                reserved=reserved,
                unit=unit,
                source_ref=ref,
                configured=configured,
                insufficient_data_message=f"Asset {dimension} capacity is unconfigured, so the request cannot be evaluated",
            )
            impacts[dimension] = impact
            findings.extend(dim_findings)

        stop_findings, stop_summary = self._evaluate_stops(stops)
        findings.extend(stop_findings)

        time_impacts, time_findings, time_summary = self._evaluate_time(
            drive_hours=drive_hours,
            service_hours=service_hours,
            duty_hours=duty_hours,
            stop_summary=stop_summary,
            is_simulation=is_simulation,
        )
        impacts.update(time_impacts)
        findings.extend(time_findings)

        arrangement_findings, arrangement_summary = self._evaluate_arrangement(arrangement, stops)
        findings.extend(arrangement_findings)

        findings.extend(self._evaluate_cargo_policy(stacking_policy, requires_floor_position, impacts["linear_feet"]))

        if requires_liftgate and not self.physical.has_liftgate:
            findings.append(
                CapacityFinding(
                    code="EQUIPMENT_LIFTGATE_MISSING",
                    dimension=DIMENSION_PHYSICAL,
                    severity=SEVERITY_BLOCKING,
                    message="Load requires a liftgate; the asset has none recorded",
                    source_ref="physical.has_liftgate",
                    requires_human_review=True,
                )
            )

        # Flexibility buffer: the maneuvering margin the operation keeps on the
        # tightest physical dimension, evaluated in its own right so that
        # "we technically fit but at 97% of the trailer" is visible.
        flexibility_impact = self._evaluate_flexibility_buffer(weight_lbs, linear_feet, volume_cuft, pallets)
        impacts["flexibility_buffer"] = flexibility_impact
        if flexibility_impact.consumes_reserve:
            findings.append(
                CapacityFinding(
                    code="RESERVE_CONSUMED_FLEXIBILITY_BUFFER",
                    dimension=DIMENSION_RESERVE,
                    severity=SEVERITY_ADVISORY,
                    message=(
                        f"Projected peak utilization {flexibility_impact.requested}% eats into the "
                        f"{flexibility_impact.reserved}% flexibility buffer"
                    ),
                    source_ref="reserve.flexibility_buffer_pct",
                    requires_human_review=True,
                )
            )

        return self._assemble(findings, impacts, stop_summary, time_summary, arrangement_summary, is_simulation)

    def _evaluate_flexibility_buffer(
        self,
        weight_lbs: float,
        linear_feet: float,
        volume_cuft: float,
        pallets: int,
    ) -> ReserveImpact:
        projected_pcts = []
        for requested, used, maximum in (
            (weight_lbs, self.physical.used_weight_lbs, self.physical.max_weight_lbs),
            (linear_feet, self.physical.used_linear_feet, self.physical.max_linear_feet),
            (volume_cuft, self.physical.used_volume_cuft, self.physical.max_volume_cuft),
            (pallets, self.physical.used_pallets, self.physical.max_pallets),
        ):
            if requested > 0 and maximum > 0:
                projected_pcts.append(((used + requested) / maximum) * 100.0)
        if not projected_pcts:
            return ReserveImpact(dimension="flexibility_buffer", unit="pct", source_ref="reserve.flexibility_buffer_pct")
        impact, _ = evaluate_reserve_dimension(
            dimension="flexibility_buffer",
            requested=max(projected_pcts),
            raw_remaining=100.0,
            reserved=self.reserve.flexibility_buffer_pct,
            unit="pct",
            source_ref="reserve.flexibility_buffer_pct",
        )
        return impact

    def _assemble(
        self,
        findings: list[CapacityFinding],
        impacts: dict[str, ReserveImpact],
        stop_summary: dict,
        time_summary: dict,
        arrangement_summary: dict,
        is_simulation: bool,
    ) -> CapacityAssessment:
        """Separate the fit concepts. None means unanswerable, not 'no'."""
        requested_dims = [d for d, i in impacts.items() if i.requested > 0]
        physical_requested = [d for d in requested_dims if d in PHYSICAL_DIMENSIONS]
        physical_unevaluated = [d for d in physical_requested if not impacts[d].evaluated]

        if not physical_requested or physical_unevaluated:
            physical_fit: bool | None = None
        else:
            physical_fit = not any(impacts[d].exceeds_total for d in physical_requested)

        all_requested_unevaluated = [d for d in requested_dims if not impacts[d].evaluated]
        if not requested_dims or all_requested_unevaluated:
            baseline_fit: bool | None = None
            reserve_required: bool | None = None
        else:
            baseline_fit = all(impacts[d].status == "WITHIN_BASELINE" for d in requested_dims)
            reserve_required = any(impacts[d].consumes_reserve for d in requested_dims)

        exceeds_total = any(i.exceeds_total for i in impacts.values()) or any(
            f.code.startswith("CAPACITY_EXCEEDED_") for f in findings
        )

        assessment = CapacityAssessment(
            capacity_id=self.capacity_id,
            physical_fit=physical_fit,
            baseline_fit=baseline_fit,
            reserve_required=reserve_required,
            exceeds_total_capacity=exceeds_total,
            data_sufficient=not any(f.data_gap for f in findings),
            requires_human_review=any(f.requires_human_review for f in findings),
            findings=findings,
            reserve_impacts=impacts,
            remaining={
                "weight_lbs": self.physical.remaining_weight_lbs,
                "linear_feet": self.physical.remaining_linear_feet,
                "volume_cuft": self.physical.remaining_volume_cuft,
                "pallets": self.physical.remaining_pallets,
                "drive_hours": self.time.remaining_drive_hours,
                "duty_hours": self.time.remaining_duty_hours,
                "cycle_hours": self.time.remaining_cycle_hours,
            },
            over_capacity={d: i.over_capacity for d, i in impacts.items() if i.over_capacity > 0},
            stop_sequence=stop_summary,
            time=time_summary,
            arrangement=arrangement_summary,
            is_simulation=is_simulation,
        )
        return assessment

    def can_accommodate(self, *args, **kwargs) -> CapacityAssessment:
        """Stable name kept for existing callers; delegates to `evaluate`.

        Returns the full assessment rather than a bare boolean. It is truthy
        only when the engine has neither an objection nor an open question, and
        it still unpacks as `(fits, findings)` for older call sites.
        """
        return self.evaluate(*args, **kwargs)

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
            "committed": [c.to_dict() for c in self.committed],
            "projected": [p.to_dict() for p in self.projected],
            "projected_utilization": self.projected_utilization(),
            "updated_at": self.updated_at,
        }
