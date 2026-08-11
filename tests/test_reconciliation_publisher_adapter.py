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


def test_view_reports_no_approval_enforcement_today():
    # This is the concrete evidence for Hard Conflict List item 2: the flag exists
    # (human_approval_required) but nothing in Dispatch's real code checks it.
    view = dispatch_action_to_canonical_view(_action(status="APPROVED"))
    assert view.is_approval_enforced is False


def test_view_reports_missing_approved_by_honestly():
    view = dispatch_action_to_canonical_view(_action(status="APPROVED"))
    assert view.approved_by is None


def test_view_reports_approved_by_when_present_without_claiming_it_was_verified():
    action = _action(status="APPROVED")
    action["approved_by"] = "Mike Zachary"
    view = dispatch_action_to_canonical_view(action)
    assert view.approved_by == "Mike Zachary"
    assert view.is_approval_enforced is False  # reported, not verified


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
