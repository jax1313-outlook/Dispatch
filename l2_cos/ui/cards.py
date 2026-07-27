"""Operations Portal — Card view logic.

A Card is the at-a-glance summary of one load: the "✅ HIGH VALUE MATCH |
Score ##" badge once its Intelligence Score clears PUBLISH_THRESHOLD, and a
🟥 red indicator whenever the Location or Broker Intelligence Libraries
carry a historical flag worth investigating before dispatch commits to the
load. Red means investigate; it is never itself a rejection.
"""

from __future__ import annotations

from pydantic import BaseModel

from l2_cos.models.intelligence import PUBLISH_THRESHOLD
from l2_cos.ui.repository import LoadBundle

HIGH_VALUE_BADGE = "✅ HIGH VALUE MATCH"
RED_INDICATOR = "🟥"
CLEAR_INDICATOR = "🟩"


class LoadCard(BaseModel):
    load_id: str
    lane: str
    equipment_type: str | None
    broker_name: str
    stage: str
    score: int
    high_value_match: bool
    badge: str
    indicator: str
    red_flag_reasons: list[str]


def is_high_value_match(score: int) -> bool:
    return score >= PUBLISH_THRESHOLD


def red_flag_reasons(bundle: LoadBundle) -> list[str]:
    """Every Location/Broker Intelligence Library flag that warrants a 🟥:
    historical facility problems, posted security requirements, and
    broker payment/contact risk flags already raised by broker_risk."""
    reasons: list[str] = []

    for role, facility in (("Pickup", bundle.facility_pickup), ("Delivery", bundle.facility_delivery)):
        if facility is None:
            continue
        for problem in facility.historical_problems:
            reasons.append(f"{role} ({facility.name}): {problem}")
        if facility.security_requirements:
            reasons.append(f"{role} ({facility.name}): {facility.security_requirements}")

    if bundle.broker is not None:
        broker_flags = bundle.intelligence.get("broker_risk", {}).get("flags", [])
        if "slow_payment_terms" in broker_flags:
            reasons.append(
                f"Broker ({bundle.broker.company_name}): slow payment terms ({bundle.broker.payment_terms})"
            )
        if "broker_contact_incomplete" in broker_flags:
            reasons.append(f"Broker ({bundle.broker.company_name}): contact record incomplete")

    return reasons


def build_card(bundle: LoadBundle) -> LoadCard:
    reasons = red_flag_reasons(bundle)
    high_value = is_high_value_match(bundle.overall_score)
    broker_name = bundle.broker.company_name if bundle.broker else (bundle.raw_load.get("broker_id") or "unassigned")
    lane = f"{bundle.raw_load.get('origin')} -> {bundle.raw_load.get('destination')}"

    return LoadCard(
        load_id=bundle.load_id,
        lane=lane,
        equipment_type=bundle.raw_load.get("equipment_type"),
        broker_name=broker_name,
        stage=bundle.load.stage.value,
        score=bundle.overall_score,
        high_value_match=high_value,
        badge=f"{HIGH_VALUE_BADGE} | Score {bundle.overall_score}" if high_value else "",
        indicator=RED_INDICATOR if reasons else CLEAR_INDICATOR,
        red_flag_reasons=reasons,
    )
