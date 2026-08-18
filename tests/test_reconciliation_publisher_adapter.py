"""Tests for reconciliation.adapters.publisher_adapter (Stage 4 — pure translation, no I/O)."""
from __future__ import annotations

from reconciliation.adapters.publisher_adapter import (
    adapt_all,
    dispatch_action_to_canonical_view,
    would_pass_tri_department_gate,
)


def _action(**overrides):
    base = {
        "id": "PUB-0001",
        "action_type": "Broker Packet Required",
        "sandbox_id": "SBX-DISPATCH-1",
        "status": "PENDING",
        "trigger_reason": "Manual trigger",
        "available_data": [],
        "missing_data": ["W-9"],
        "manifest": ["Business Card", "W-9", "Insurance", "Authority", "Rate Sheet", "Terms"],
        "recommended_product": "Broker Packet Required",
        "human_approval_required": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_view_reports_approval_enforcement_now_exists():
    # Hard Conflict List item 2 is closed: portal/models/publisher.py::update_action_status()
    # now raises PublisherApprovalError on the APPROVED transition without a real, external,
    # non-system approved_by identity (see docs/CANONICAL_RECONCILIATION_INTEGRATION.md,
    # "Approval Chain Safety Gate"). This is the concrete evidence that the gate is real:
    # is_approval_enforced now reports True.
    view = dispatch_action_to_canonical_view(_action(status="APPROVED"))
    assert view.is_approval_enforced is True


def test_view_reports_enforcement_regardless_of_status():
    # is_approval_enforced is a fact about the code path (does update_action_status() enforce
    # the gate at all), not about whether *this* action has already been approved -- a still
    # PENDING action is equally protected by the gate if/when it is later moved to APPROVED.
    view = dispatch_action_to_canonical_view(_action(status="PENDING"))
    assert view.is_approval_enforced is True


def test_view_reports_missing_approved_by_honestly():
    view = dispatch_action_to_canonical_view(_action(status="APPROVED"))
    assert view.approved_by is None


def test_view_reports_enforcement_even_with_reserved_identity_approved_by():
    # is_approval_enforced reports the code-path fact, not a per-record validity check on this
    # particular dict -- a hand-built/historical record can still carry a reserved system
    # identity that the real gate would have rejected. That per-record question is answered
    # separately by would_pass_tri_department_gate(), not by is_approval_enforced.
    action = _action(status="APPROVED")
    action["approved_by"] = "PUBLISHER"
    view = dispatch_action_to_canonical_view(action)
    assert view.approved_by == "PUBLISHER"
    assert view.is_approval_enforced is True
    assert would_pass_tri_department_gate(view) is False


def test_view_reports_approved_by_when_present_alongside_enforcement_fact():
    action = _action(status="APPROVED")
    action["approved_by"] = "Mike Zachary"
    view = dispatch_action_to_canonical_view(action)
    assert view.approved_by == "Mike Zachary"
    assert view.is_approval_enforced is True
    assert would_pass_tri_department_gate(view) is True


def test_would_pass_tri_department_gate_rejects_missing_approver():
    view = dispatch_action_to_canonical_view(_action())
    assert would_pass_tri_department_gate(view) is False


def test_would_pass_tri_department_gate_rejects_system_identity():
    action = _action()
    action["approved_by"] = "PUBLISHER"
    view = dispatch_action_to_canonical_view(action)
    assert would_pass_tri_department_gate(view) is False


def test_would_pass_tri_department_gate_accepts_real_external_identity():
    action = _action()
    action["approved_by"] = "Mike Zachary"
    view = dispatch_action_to_canonical_view(action)
    assert would_pass_tri_department_gate(view) is True


def test_adapt_all_translates_full_queue():
    queue = [_action(id="PUB-0001"), _action(id="PUB-0002", action_type="Rate Sheet Request")]
    views = adapt_all(queue)
    assert len(views) == 2
    assert {v.action_id for v in views} == {"PUB-0001", "PUB-0002"}
