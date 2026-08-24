"""Route Risk Connector — collection only, with the evaluation layer kept separate.

Section 6.5 is emphatic that Route Risk "is an **Operational Intelligence
function**, not a weather/traffic feed", and the split this module implements is
what that sentence means in code:

    the connector COLLECTS conditions        (this file, top half)
    the evaluation layer PRODUCES findings   (this file, bottom half — interface
                                              and one advisory reference impl)
    COMI routes the communications           (dispatch/comi_routing.py)
    Spine and Mike change reality            (dispatch/spine/, a human)

Why they are separated rather than fused into one "get the route risk" call: a
fused version has no place to stand between "the National Weather Service says
there is ice on I-75" and "this load will be late", and the second statement is
an operational judgment about *this* mission that a feed cannot make. Keeping
them apart also means a provider swap changes only the collection half, and a
change to how consequence is judged changes only the evaluation half.

**What the evaluation layer may never do**, and what the test suite proves it
cannot: accept or cancel a load, or change Current Reality without a governed
Spine event or human authority. :class:`RouteRiskAssessment` has no field that
could carry an acceptance or a cancellation, the reference evaluator is a pure
function of its payload, and ``tests/test_connector_boundary.py`` runs it inside
``boundary.sealed()`` -- which refuses every database connection -- to prove the
absence rather than assert it.

**Relationship to what already exists.** ``route_risk/engine.py`` and
``dispatch/route_risk.py`` already record Route Risk events, already label them
"(Internal/Stubbed - No live external API)", and already carry ``is_live_data:
False``. Nothing here replaces or duplicates that: this connector is the
*inbound* side those modules never had -- where an external condition would
arrive from, once a provider exists -- and :func:`assessment_to_event_kwargs`
hands a finding to the existing engine in the shape it already accepts, so the
recording path stays exactly where it is.

Today there is no provider. ``fetch`` refuses with ``UNCONFIGURED`` and names the
keys it would need. The mock in ``dispatch/connectors/mock.py`` produces
``SIMULATED`` conditions in this same normalized shape, which is what the
evaluation layer is exercised against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    NormalizedPayload,
    utc_now,
)

#: The condition classes Section 6.5 permits this connector to collect. A closed
#: list because "what does Route Risk look at" is a doctrine question, and a
#: connector that could quietly widen it would be setting doctrine.
ROUTE_RISK_COLLECTIBLES: tuple[str, ...] = (
    "weather",
    "traffic",
    "dot_restrictions",
    "law_enforcement_conditions",
    "port_conditions",
    "disaster_conditions",
    "fuel_conditions",
    "security_conditions",
    "road_restrictions",
    "mission_advisories",
)

#: The payload kind every Route Risk collection carries, mock or real.
PAYLOAD_KIND = "route_risk_conditions"


@dataclass(frozen=True)
class RouteCondition:
    """One collected condition, normalized, before anyone has judged it.

    ``severity_hint`` is the *provider's* word for how bad it is -- "winter
    storm warning", "moderate congestion" -- deliberately not a Dispatch
    consequence level. Turning a provider's severity into a consequence for this
    mission is the evaluation layer's job, and letting the provider's number
    through under a Dispatch name is how an external feed starts making
    operational judgments.
    """

    kind: str
    summary: str
    observed_at: str = ""
    affected_area: str = ""
    affected_corridor: str = ""
    severity_hint: str = ""
    source_reference: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ROUTE_RISK_COLLECTIBLES:
            raise ValueError(
                f"{self.kind!r} is not a Route Risk condition class. Section 6.5 lists: "
                f"{', '.join(ROUTE_RISK_COLLECTIBLES)}."
            )
        if not self.summary:
            raise ValueError("A route condition needs a summary a human can read.")

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "observed_at": self.observed_at,
            "affected_area": self.affected_area,
            "affected_corridor": self.affected_corridor,
            "severity_hint": self.severity_hint,
            "source_reference": self.source_reference,
        }


def normalize_conditions(conditions: Sequence[RouteCondition], *, load_id: str = "") -> dict:
    """The normalized payload body every Route Risk provider must produce.

    Fixed shape, so the evaluation layer never learns a provider's vocabulary
    and a second provider can be added without touching it.
    """
    return {
        "load_id": load_id,
        "condition_count": len(conditions),
        "conditions": [c.to_dict() for c in conditions],
        "collected_at": utc_now(),
    }


class RouteRiskConnector(BaseConnector):
    """Collects route conditions from an external provider. None is selected."""

    connector_id = "route_risk"
    connector_name = "Route Risk Connector"
    required_config_keys = ("DISPATCH_ROUTE_RISK_API_URL", "DISPATCH_ROUTE_RISK_API_KEY")
    credential_keys = ("DISPATCH_ROUTE_RISK_API_KEY",)
    auth_method = "api_key"
    capability_declaration = CapabilityDeclaration(
        collects=ROUTE_RISK_COLLECTIBLES,
        produces=("normalized route conditions for the Route Risk evaluation layer",),
        notes=(
            "Collection only. Findings, consequence levels, COMI notification requirements "
            "and Mission Visibility updates are produced by the evaluation layer, which is "
            "a separate object with no persistence of its own."
        ),
    )

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        """No provider is selected, so this refuses and says what is missing.

        The refusal is deliberately not softened into an empty condition list. A
        connector that answers "no conditions" when it has not looked is telling
        a dispatcher the road is clear.
        """
        return self.unconfigured(
            request,
            extra=(
                "Route Risk conditions are not available from any external system. "
                "Internal and manual Route Risk events recorded through "
                "dispatch/route_risk.py are unaffected and remain labelled as internal."
            ),
        )


# --------------------------------------------------------------------------- evaluation


#: Section 6.5's consequence scale, matching route_risk/engine.py's 0-5.
MIN_CONSEQUENCE, MAX_CONSEQUENCE = 0, 5


@dataclass(frozen=True)
class RouteRiskFinding:
    """One judged condition: what it is, where, and what it costs this mission."""

    condition_kind: str
    affected_area: str
    affected_corridor: str
    consequence_level: int
    rationale: str
    estimated_delay_minutes: int = 0

    def __post_init__(self) -> None:
        if not MIN_CONSEQUENCE <= self.consequence_level <= MAX_CONSEQUENCE:
            raise ValueError(
                f"Consequence level {self.consequence_level} is outside 0-5, the scale "
                "route_risk/engine.py and COMI both already use."
            )

    def to_dict(self) -> dict:
        return {
            "condition_kind": self.condition_kind,
            "affected_area": self.affected_area,
            "affected_corridor": self.affected_corridor,
            "consequence_level": self.consequence_level,
            "rationale": self.rationale,
            "estimated_delay_minutes": self.estimated_delay_minutes,
        }


@dataclass(frozen=True)
class RouteRiskAssessment:
    """What the evaluation layer produces. Advisory, always, by construction.

    Note what is not here. There is no ``accept``, no ``cancel``, no
    ``new_status``, no ``load_update``. The absence is the design: an assessment
    that could carry an acceptance would eventually be applied by something, and
    Section 6.5 puts that authority with Spine and with Mike. What it carries
    instead are *requirements* -- COMI should notify, Mission Visibility should
    update, a stakeholder communication is warranted -- each of which is an input
    to a system that has the authority to act.

    ``status`` travels from the payload that produced it. An assessment built
    from SIMULATED conditions is a SIMULATED assessment, and says so on every
    surface that shows it.
    """

    status: ConnectorStatus
    findings: tuple[RouteRiskFinding, ...] = ()
    consequence_level: int = 0
    comi_notification_required: bool = False
    mission_visibility_update_required: bool = False
    stakeholder_communication_input: str = ""
    map_visual_required: bool = False
    evaluated_at: str = field(default_factory=utc_now)
    advisory: bool = True

    def __post_init__(self) -> None:
        if not self.advisory:
            raise ValueError(
                "A Route Risk assessment is advisory. Route Risk must not accept or cancel "
                "loads and must not change Current Reality without a governed Spine event or "
                "human authority (Section 6.5)."
            )

    @property
    def label(self) -> str:
        return f"{self.status.value} — Route Risk assessment"

    def to_display_dict(self) -> dict:
        """Includes ``connector_status`` so ``assert_labeled_display`` accepts it."""
        return {
            "connector_status": self.status.value,
            "connector_label": self.label,
            "advisory": self.advisory,
            "consequence_level": self.consequence_level,
            "findings": [f.to_dict() for f in self.findings],
            "comi_notification_required": self.comi_notification_required,
            "mission_visibility_update_required": self.mission_visibility_update_required,
            "stakeholder_communication_input": self.stakeholder_communication_input,
            "map_visual_required": self.map_visual_required,
            "evaluated_at": self.evaluated_at,
        }


@runtime_checkable
class RouteRiskEvaluator(Protocol):
    """The evaluation layer's interface: payload in, assessment out.

    One method, no constructor requirements, no persistence. An implementation
    that needed a database would not fit this signature without smuggling one in
    through its own state, and ``boundary.sealed()`` refuses that at runtime.
    """

    def evaluate(self, payload: NormalizedPayload) -> RouteRiskAssessment: ...


#: How a provider's severity word maps onto Dispatch's 0-5 consequence scale.
#: Deliberately coarse and deliberately visible: the mapping is a doctrine
#: decision, so it belongs in one readable table rather than inside a formula.
_SEVERITY_CONSEQUENCE: dict[str, int] = {
    "informational": 1,
    "advisory": 2,
    "watch": 2,
    "warning": 3,
    "severe": 4,
    "emergency": 5,
}

#: Condition classes that raise consequence on their own, whatever the provider
#: called the severity: a closed road is a closed road.
_STRUCTURAL_CONDITIONS: frozenset[str] = frozenset(
    {"road_restrictions", "dot_restrictions", "disaster_conditions", "security_conditions"}
)


class AdvisoryRouteRiskEvaluator:
    """A deterministic reference evaluator. Pure, and provably unable to persist.

    It exists for two reasons: to give the interface a working implementation
    the tests can exercise end to end, and to pin down what "evaluation" means
    here -- reading normalized conditions, assigning a consequence level, and
    stating which communications the result requires. It reads nothing but its
    argument and writes nothing at all.

    Deterministic on purpose, matching the repository's rule that rule logic
    stays deterministic (CLAUDE.md). A model could be asked to judge a condition
    later; it would be a different implementation of this same interface, and it
    would still produce an advisory assessment.
    """

    def evaluate(self, payload: NormalizedPayload) -> RouteRiskAssessment:
        conditions = payload.data.get("conditions", []) if payload.data else []
        findings: list[RouteRiskFinding] = []

        for raw in conditions:
            kind = str(raw.get("kind", ""))
            severity = str(raw.get("severity_hint", "")).strip().lower()
            level = _SEVERITY_CONSEQUENCE.get(severity, 1)
            if kind in _STRUCTURAL_CONDITIONS:
                level = min(MAX_CONSEQUENCE, level + 1)
            findings.append(
                RouteRiskFinding(
                    condition_kind=kind,
                    affected_area=str(raw.get("affected_area", "")),
                    affected_corridor=str(raw.get("affected_corridor", "")),
                    consequence_level=level,
                    rationale=(
                        f"{raw.get('summary', '')} "
                        f"(provider severity {severity or 'unstated'}"
                        f"{', structural condition' if kind in _STRUCTURAL_CONDITIONS else ''})"
                    ).strip(),
                    estimated_delay_minutes=int(raw.get("estimated_delay_minutes", 0) or 0),
                )
            )

        overall = max((f.consequence_level for f in findings), default=0)
        return RouteRiskAssessment(
            status=payload.status,
            findings=tuple(findings),
            consequence_level=overall,
            # Thresholds match dispatch/comi_routing.py's own route_risk_event
            # rules so the two layers agree about when a communication exists.
            comi_notification_required=overall >= 3,
            mission_visibility_update_required=overall >= 1,
            stakeholder_communication_input=(
                f"{len(findings)} route condition(s) assessed at consequence level {overall}."
                if findings
                else ""
            ),
            map_visual_required=any(f.affected_corridor or f.affected_area for f in findings),
        )


def assessment_to_event_kwargs(
    assessment: RouteRiskAssessment,
    *,
    load_id: str,
    source_label: str,
) -> dict[str, Any]:
    """Shape an assessment for ``dispatch.route_risk.record_route_risk_event``.

    A translation, not a call. This module does not record anything -- it cannot,
    since recording goes through ``dispatch.store`` and the boundary forbids the
    import -- so it hands back keyword arguments and lets a caller that *does*
    have that authority decide whether to record them. The status word is
    carried into ``condition_summary`` so a stored event built from SIMULATED
    conditions still says so in the text a dispatcher reads.
    """
    worst = max(assessment.findings, key=lambda f: f.consequence_level, default=None)
    summary = (
        f"[{assessment.status.value}] "
        + (worst.rationale if worst else "No route conditions reported.")
    )
    return {
        "load_id": load_id,
        "condition_summary": summary,
        "consequence_level": assessment.consequence_level,
        "estimated_delay_minutes": worst.estimated_delay_minutes if worst else 0,
        "source_type": "connector",
        "source_label": f"{source_label} [{assessment.status.value}]",
        "affected_area": worst.affected_area if worst else "",
        "affected_corridor": worst.affected_corridor if worst else "",
        "has_map_visual": assessment.map_visual_required,
    }


def evaluation_inputs(payload: NormalizedPayload) -> Mapping[str, Any]:
    """The payload body an evaluator will read, kept behind one accessor.

    Small on purpose: it is the single place that reaches for ``payload.data``,
    so if the payload shape changes there is one call site to fix rather than
    one per evaluator.
    """
    return dict(payload.data or {})
