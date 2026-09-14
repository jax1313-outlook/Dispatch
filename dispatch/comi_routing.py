"""COMI Routing Foundation -- Communication & Operational Messaging Intelligence.

Provides read-only classification, role-based visibility rules, and routing decisions
for operational triggers (milestone updates, route risks, exceptions, closeout).
Does NOT send real emails/SMS, bypass Publisher, or invent unverified facts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


INTERNAL_ROLES = {"operations", "dispatcher", "admin", "mike"}
EXTERNAL_ROLES = {"driver", "broker", "shipper", "customer", "consignee"}
ALL_ROLES = INTERNAL_ROLES | EXTERNAL_ROLES

INTERNAL_ONLY_KEYS = {
    "internal_note",
    "profit",
    "margin_pct",
    "total_expenses",
    "expense_breakdown",
    "internal_score",
    "cognitive_analysis",
    "private_reasoning",
    "recovery_word",
    "pin",
    "driver_phone",
    "driver_email",
    "license_number",
}


#: Trigger: COMMIT opened Mission Visibility for the customer (playbook Section 4A).
MISSION_VISIBILITY_OPENED = "mission_visibility_opened"
#: Trigger: customer-facing mission evidence (securement / freight condition photos) was added.
MISSION_EVIDENCE_ADDED = "mission_evidence_added"
#: Triggers that tell the customer by email (Customer Alerts = push visibility).
CUSTOMER_EMAIL_TRIGGERS = (MISSION_VISIBILITY_OPENED, MISSION_EVIDENCE_ADDED)
#: Channel: an email to the customer, sent by Email Helper.
CUSTOMER_EMAIL = "customer_email"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_payload_for_role(payload: dict, role: str) -> dict:
    """Sanitizes operational data payloads based on recipient role.

    Internal roles see full operational details.
    External roles (driver, broker, shipper, customer, consignee) have internal-only
    fields (profit margins, internal notes, sensitive credentials, driver contact details)
    stripped out fail-closed.
    """
    if not isinstance(payload, dict):
        return payload

    clean_role = (role or "").strip().lower()
    if clean_role in INTERNAL_ROLES:
        return dict(payload)

    sanitized = {}
    for key, value in payload.items():
        if key in INTERNAL_ONLY_KEYS:
            continue
        if isinstance(value, dict):
            sanitized[key] = sanitize_payload_for_role(value, clean_role)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_payload_for_role(item, clean_role) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def evaluate_comi_routing(
    load_id: str,
    trigger_type: str,
    consequence_level: int = 1,
    source_refs: dict | None = None,
    custom_notes: dict | None = None,
) -> dict:
    """Evaluates communication triggers and generates a COMI routing decision structure.

    Answers:
    1. Why does this communication exist? (trigger_type description)
    2. What triggered it? (trigger_type & source_refs)
    3. Who needs to know? (recipient_roles)
    4. What role does each recipient have? (recipient_roles classification)
    5. What should each recipient see / not see? (handled via sanitize_payload_for_role)
    6. Does Publisher / Mission Visibility / Driver Portal / Stakeholder Portal / Operations Feed need updates?
    """
    consequence_level = max(0, min(5, int(consequence_level)))
    source_refs = source_refs or {}
    custom_notes = custom_notes or {}

    recipient_roles = ["operations"]
    publisher_required = False
    mission_visibility_update_required = False
    driver_alert_required = False
    stakeholder_update_required = False
    operations_review_required = consequence_level >= 2

    if trigger_type == "route_risk_event":
        mission_visibility_update_required = True
        if consequence_level >= 1:
            driver_alert_required = True
            recipient_roles.append("driver")
        if consequence_level >= 3:
            stakeholder_update_required = True
            publisher_required = True
            recipient_roles.extend(["broker", "customer"])
    elif trigger_type == "milestone_update":
        mission_visibility_update_required = True
        recipient_roles.append("driver")
        if consequence_level >= 2:
            stakeholder_update_required = True
            recipient_roles.extend(["broker", "customer"])
    elif trigger_type == "exception_opened":
        mission_visibility_update_required = True
        operations_review_required = True
        if consequence_level >= 3:
            stakeholder_update_required = True
            publisher_required = True
            recipient_roles.extend(["broker", "shipper", "customer"])
        if consequence_level >= 2:
            driver_alert_required = True
            recipient_roles.append("driver")
    elif trigger_type == "closeout_ready":
        publisher_required = True
        stakeholder_update_required = True
        recipient_roles.extend(["broker", "customer"])
    elif trigger_type == "manual_notice":
        if consequence_level >= 2:
            stakeholder_update_required = True
            recipient_roles.extend(["broker", "customer"])
    elif trigger_type in CUSTOMER_EMAIL_TRIGGERS:
        # COMMIT gave the customer a Mission Visibility Key, or customer-facing mission evidence
        # arrived; the customer is told by email.
        mission_visibility_update_required = True
        publisher_required = True
        stakeholder_update_required = True
        recipient_roles.append("customer")

    # Deduplicate roles preserving order
    unique_roles = list(dict.fromkeys(recipient_roles))

    recommended_channel = "operations_feed_only"
    if trigger_type in CUSTOMER_EMAIL_TRIGGERS:
        recommended_channel = CUSTOMER_EMAIL
    elif publisher_required:
        recommended_channel = "publisher_draft"
    elif stakeholder_update_required:
        recommended_channel = "stakeholder_portal_update"
    elif driver_alert_required:
        recommended_channel = "driver_portal_alert"

    event_id = f"comi-{uuid.uuid4().hex[:10]}"

    return {
        "communication_event_id": event_id,
        "load_id": load_id,
        "trigger_type": trigger_type,
        "consequence_level": consequence_level,
        "recipient_roles": unique_roles,
        "recommended_channel": recommended_channel,
        "publisher_required": publisher_required,
        "mission_visibility_update_required": mission_visibility_update_required,
        "driver_alert_required": driver_alert_required,
        "stakeholder_update_required": stakeholder_update_required,
        "operations_review_required": operations_review_required,
        "status": "evaluated",
        "source_refs": source_refs,
        "evaluated_at": _utc_now(),
    }


def route_communication(evaluation: dict, publisher_action: dict) -> dict:
    """COMI routes a communication Publisher created. Decides; sends nothing.

    Routed only when the evaluation calls for a customer email, Publisher's card is ready (or
    approved, when approval is required), and there is somewhere to send it. The payload is
    sanitized for the recipient's role.
    """
    communication = publisher_action.get("communication") or {}
    role = communication.get("recipient_role") or "customer"
    base = {"communication_event_id": evaluation.get("communication_event_id"),
            "publisher_action_id": publisher_action.get("id"), "recipient_role": role,
            "routed_at": _utc_now()}

    def not_routed(reason):
        return dict(base, status="not_routed", reason=reason)

    if evaluation.get("recommended_channel") != CUSTOMER_EMAIL:
        return not_routed(f"COMI recommends {evaluation.get('recommended_channel')}, not a customer email")
    if role not in evaluation.get("recipient_roles", []):
        return not_routed(f"{role} is not a recipient of this communication")
    ready = "APPROVED" if publisher_action.get("human_approval_required") else "READY"
    if publisher_action.get("status") not in (ready, "APPROVED"):
        return not_routed(f"Publisher's communication is {publisher_action.get('status')}, not {ready}")
    if not communication.get("to"):
        return not_routed("there is no address to send it to")
    payload = sanitize_payload_for_role(
        {"subject": communication.get("subject", ""), "body": communication.get("body", "")}, role)
    return dict(base, status="routed", channel=CUSTOMER_EMAIL, to=[communication["to"]], **payload)
