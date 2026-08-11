"""Adapter: portal/models/publisher.py action records -> PublisherActionCanonicalView.

Per DISPATCH_CANONICAL_ARCHITECTURE_RECONCILIATION_MATRIX_v1.md Section 3: "Publisher: Hybrid.
Tri-department governs. Dispatch proposal writer drafts." This module is read-only reporting for
Stage 4 -- it does not add the enforced approval gate itself (that is Stage 5's
`update_action_status(..., approved_by=...)` code change, not yet applied).

Pure functions only: no file I/O, no writes, no calls into portal.models.publisher's _save().
"""
from __future__ import annotations

from typing import Any, Dict, List

from reconciliation.contracts import PublisherActionCanonicalView

# Same reserved-identity set the tri-department Publisher repo enforces
# (dispatch_publisher.models.RESERVED_SYSTEM_IDENTITIES). Used here only to evaluate whether an
# existing approved_by value (on the rare record that has one) would actually pass tri-department
# rules -- this module does not enforce anything; it only reports.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}


def dispatch_action_to_canonical_view(action: Dict[str, Any]) -> PublisherActionCanonicalView:
    """Translate one Dispatch publisher action into a canonical-shaped read-only view.

    `is_approval_enforced` is always False: as of this Stage-4 adapter,
    portal/models/publisher.py::update_action_status() has no code path that requires or
    validates an approver identity (see DISPATCH_DEPARTMENT_RECONCILIATION_v1.md Section 3).
    An action can carry an `approved_by` key today only if something outside the current
    codebase set one manually -- this function reports that value if present, but does not
    claim it was verified, because nothing verified it.
    """
    approved_by = action.get("approved_by")
    return PublisherActionCanonicalView(
        action_id=action["id"],
        action_type=action["action_type"],
        status=action["status"],
        approved_by=approved_by,
        is_approval_enforced=False,
        missing_data=list(action.get("missing_data", [])),
        manifest=list(action.get("manifest", [])),
    )


def adapt_all(queue: List[Dict[str, Any]]) -> List[PublisherActionCanonicalView]:
    """Translate the full list returned by portal.models.publisher.get_queue()."""
    return [dispatch_action_to_canonical_view(action) for action in queue]


def would_pass_tri_department_gate(view: PublisherActionCanonicalView) -> bool:
    """Would this action's recorded approved_by satisfy the tri-department Publisher's
    approve_review_package() check, if that check were applied retroactively?

    This does NOT mean the action actually went through review -- it only means the string
    recorded (if any) is not empty and not a reserved system identity. Reporting-only; changes
    nothing about how the action was actually processed.
    """
    if not view.approved_by:
        return False
    return view.approved_by.strip().upper() not in RESERVED_SYSTEM_IDENTITIES
