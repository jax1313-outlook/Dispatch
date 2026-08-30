"""Publisher action card management.

Publisher produces documents from approved inputs only.
Publisher must not invent facts.

Governance gate (Stage 5 of DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md,
Claude-3 repo, Hard Conflict List item 2): `human_approval_required` was previously a static
flag nothing checked. `update_action_status()` now enforces it in code for the `APPROVED`
transition specifically, mirroring tri-department Publisher's `approve_review_package()` --
Publisher (or any other system identity) may not approve its own action.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir, atomic_write_json

# Identities that may never be used as an approver -- Publisher may not approve itself. Matches
# dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES from the tri-department build.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}


class PublisherApprovalError(ValueError):
    """Raised when an action is moved to APPROVED without a valid external approver identity."""


# Stage 2 of DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md (Claude-3 repo): the Integration Bridge
# action type -- bridges Publisher to cin_lite's proposal_writer.py. See _trigger_govcon_draft().
GOVCON_PROPOSAL_ACTION_TYPE = "GovCon Proposal Draft Required"

ACTION_TYPES = [
    "Broker Packet Required",
    "Direct Shipper Packet Required",
    "Rate Sheet Request",
    "Rate Confirmation Package Required",
    "DocuSign Package Ready",
    "Arrival Notice Draft",
    "POD/BOL Document Package Draft",
    "Detention Evidence Draft",
    GOVCON_PROPOSAL_ACTION_TYPE,
]

PUBLISHER_STATUSES = ["PENDING", "DRAFT", "READY", "APPROVED", "ARCHIVED"]

BROKER_PACKET_MANIFEST = ["Business Card", "W-9", "Insurance", "Authority", "Rate Sheet", "Terms"]
DIRECT_SHIPPER_MANIFEST = ["Business Card", "Capabilities Summary", "Insurance", "Rate Sheet", "Terms"]
RATE_CONFIRMATION_MANIFEST = [
    "Thank-you Cover Letter",
    "Rate Confirmation",
    "Terms",
    "Supporting Documents",
    "DocuSign-ready Marker",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _publisher_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "publisher_queue.json"


def _load() -> list[dict]:
    path = _publisher_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    path = _publisher_path()
    atomic_write_json(path, data)


def get_queue() -> list[dict]:
    return _load()


def _manifest_for(action_type: str) -> list[str]:
    if "Broker Packet" in action_type:
        return list(BROKER_PACKET_MANIFEST)
    if "Direct Shipper" in action_type:
        return list(DIRECT_SHIPPER_MANIFEST)
    if "Rate Confirmation" in action_type:
        return list(RATE_CONFIRMATION_MANIFEST)
    return []


def create_action(
    action_type: str,
    sandbox_id: str,
    trigger_reason: str,
    available_data: list[str] | None = None,
    missing_data: list[str] | None = None,
    contract_id: str | None = None,
) -> dict:
    queue = _load()
    now = _utc_now()
    manifest = _manifest_for(action_type)

    action = {
        "id": f"PUB-{len(queue) + 1:04d}",
        "action_type": action_type,
        "sandbox_id": sandbox_id,
        "status": "PENDING",
        "trigger_reason": trigger_reason,
        "available_data": available_data or [],
        "missing_data": missing_data or [],
        "manifest": manifest,
        "recommended_product": action_type,
        "human_approval_required": True,
        "created_at": now,
        "updated_at": now,
    }
    if contract_id is not None:
        action["contract_id"] = contract_id
    queue.append(action)
    _save(queue)
    return action


def update_action_status(action_id: str, new_status: str, approved_by: str | None = None) -> dict:
    """Update a Publisher action's status.

    `approved_by` is required and validated only for the `APPROVED` transition: it must be a
    real, external, non-system identity (Publisher may not approve itself). All other
    transitions (PENDING/DRAFT/READY/ARCHIVED) are unaffected -- this is additive, not a
    behavior change for any transition except the one that was previously ungated.
    """
    if new_status not in PUBLISHER_STATUSES:
        raise ValueError(f"Invalid publisher status: {new_status}")

    if new_status == "APPROVED":
        if not approved_by or approved_by.strip().upper() in RESERVED_SYSTEM_IDENTITIES:
            raise PublisherApprovalError(
                "Publisher action cannot be marked APPROVED without a real, external, "
                "non-system approved_by identity (Publisher may not approve itself)."
            )

    queue = _load()
    for action in queue:
        if action["id"] == action_id:
            if new_status == "DRAFT" and action.get("action_type") == GOVCON_PROPOSAL_ACTION_TYPE:
                action["proposal_reference_id"] = _trigger_govcon_draft(action)
            if new_status == "APPROVED":
                action["approved_by"] = approved_by
                action["approved_at"] = _utc_now()
            action["status"] = new_status
            action["updated_at"] = _utc_now()
            _save(queue)
            return action
    raise KeyError(f"Publisher action not found: {action_id}")


def _trigger_govcon_draft(action: dict) -> str:
    """Stage 2 of DISPATCH_END_TO_END_DEPLOYMENT_PLAN_v1.md (Claude-3 repo): drafting a
    GovCon Proposal Draft Required action calls cin_lite's existing proposal-trigger pipeline
    via pipeline.resolve_decision(contract_id, "approve_proposal") -- the same function
    cin_lite's email-decision "Approve Proposal" link calls, reused unmodified. This is a
    second, independent path into that pipeline; cin_lite's HMAC-token email flow and
    proposal_writer.py itself are untouched.

    Requires the contract still be pending in cin_lite's own decision queue
    (cin_lite.pending) -- raises ValueError if it is not, which the caller (the
    /api/publisher/update route) already surfaces as a 400, matching every other
    ValueError-raising gate in this module.
    """
    contract_id = action.get("contract_id")
    if not contract_id:
        raise ValueError(
            "GovCon Proposal Draft Required actions must have a contract_id set at creation "
            "time before they can be drafted."
        )
    from cin_lite import pipeline as cin_pipeline

    result = cin_pipeline.resolve_decision(contract_id, "approve_proposal")
    return result["proposal"]["proposal_id"]
