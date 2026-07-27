"""Control Layer — human decision gate for L2-COS stage transitions.

Cloned from cin_lite/control.py (Rule 15). Unlike cin_lite's flat five-action
set, an L2-COS action maps directly onto the locked LifecycleStage chain
(l2_cos/models/state.py): each stage has exactly one legal next stage, so the
action key IS the target stage's value. A `hold_for_review` action is always
available and never mutates `Load.stage`, giving a human a way to withhold
advancement without violating the state model lock.
"""

from __future__ import annotations

from l2_cos.models.intelligence import PUBLISH_THRESHOLD, BrokerIntelligence, LocationIntelligence
from l2_cos.models.state import Load, LifecycleStage, next_stages

HOLD_ACTION = "hold_for_review"


def available_actions(load: Load) -> dict[str, str]:
    """Action key -> label for the current stage: the single legal next
    stage (if any) plus the always-available hold action."""
    actions: dict[str, str] = {}
    upcoming = next_stages(load.stage)
    if upcoming:
        target = upcoming[0]
        actions[target.value] = f"Confirm {target.value.replace('_', ' ').title()}"
    actions[HOLD_ACTION] = "Hold for review (no stage change)"
    return actions


def resolve(action: str, load: Load) -> LifecycleStage | None:
    """Return the target stage for `action`, or None for a hold.

    Raises on an action that isn't legal from the load's current stage.
    """
    actions = available_actions(load)
    if action not in actions:
        raise ValueError(
            f"Unknown or illegal action {action!r} from stage {load.stage.value}. "
            f"Valid: {', '.join(actions)}"
        )
    return None if action == HOLD_ACTION else LifecycleStage(action)


def render_email(
    load: Load,
    intelligence: dict,
    facility_pickup: LocationIntelligence | None = None,
    facility_delivery: LocationIntelligence | None = None,
    broker: BrokerIntelligence | None = None,
) -> str:
    """Render the checkbox-driven dispatch control email as plain text."""
    lines = [
        "=" * 64,
        "L2-COS — Dispatch Control Email",
        "=" * 64,
        f"Load        : {load.load_id}",
        f"Stage       : {load.stage.value}",
        f"Broker      : {broker.company_name if broker else load.broker_id}",
        f"Pickup      : {facility_pickup.name if facility_pickup else load.pickup_facility_id}",
        f"Delivery    : {facility_delivery.name if facility_delivery else load.delivery_facility_id}",
        "",
    ]

    module_notes = [f"{name}: score {r['score']}" for name, r in intelligence.items()]
    if module_notes:
        lines.append("Module scores:")
        lines.extend(f"  - {note}" for note in module_notes)
        lines.append("")

    flags = [flag for r in intelligence.values() for flag in r.get("flags", [])]
    lines.append(f"Flags raised: {', '.join(flags) if flags else 'none'}")
    lines.append("")

    if load.intelligence_score is not None:
        eligible = load.intelligence_score >= PUBLISH_THRESHOLD
        lines.append(
            f"Intelligence score: {load.intelligence_score} "
            f"({'publisher-eligible' if eligible else 'below publish threshold'})"
        )
        lines.append("")

    lines.append("Choose ONE action (reply with the key in brackets):")
    for key, label in available_actions(load).items():
        lines.append(f"  [ ] {key:<16} {label}")
    lines.append("=" * 64)
    return "\n".join(lines)


def collect(actions: dict[str, str], default: str | None = None) -> str:
    """Get the human's action. Non-interactive callers pass `default`."""
    if default is not None:
        return default
    valid = ", ".join(actions)
    while True:
        choice = input(f"\nAction [{valid}]: ").strip()
        if choice in actions:
            return choice
        print(f"  '{choice}' is not valid.")
