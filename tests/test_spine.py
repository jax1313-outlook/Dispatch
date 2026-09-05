"""Tests for the Dispatch Spine (dispatch/spine/) -- schemas, persistence,
and the state-transition guard. Stage 4 of the Migration Plan defined in
Claude-3's DISPATCH_INTEGRATED_BLUEPRINT_v1.md; see
DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md for the approved design.
"""

from __future__ import annotations

import inspect

import pytest

from dispatch import db
from dispatch.spine import store as spine_store
from dispatch.spine.models import (
    ApprovalEvent,
    AuditEvent,
    ConflictEvent,
    Event,
    PortalCard,
    STATE_LIST,
    WorkItem,
)
from dispatch.spine.state import ALLOWED_TRANSITIONS, InvalidTransitionError, is_allowed


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path, monkeypatch):
    """Redirect dispatch database to a per-test temp directory -- same
    pattern as tests/test_dispatch.py, since Spine tables live in the
    same dispatch.db file (Stage 4's Open Question 1)."""
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


@pytest.fixture
def work_item() -> dict:
    return spine_store.create_work_item(
        WorkItem(
            source_type="government_opportunity",
            source_id="SAM-TEST-001",
            priority="MEDIUM",
            consequence_level=2,
            assigned_function="Intelligence Analyst",
            required_action="Analyze opportunity requirements",
            source_confidence="SOURCE_PRESENT",
        )
    )


# ── Schema creation ───────────────────────────────────────────────────

def test_spine_tables_created_alongside_existing_schema():
    """Opening a connection creates the six Spine tables in the same
    dispatch.db file as every existing table, per Stage 4's Open
    Question 1 (same file, not a separate database)."""
    with db.get_connection() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    for expected in (
        "work_items",
        "events",
        "portal_cards",
        "approval_events",
        "conflict_events",
        "audit_events",
    ):
        assert expected in tables
    # existing domain tables are untouched, not replaced
    assert "loads" in tables
    assert "activities" in tables


def test_spine_schema_init_is_idempotent():
    """Opening a second connection against the same file must not error --
    dispatch.db._init_db() re-runs CREATE TABLE IF NOT EXISTS on every
    connection open."""
    with db.get_connection():
        pass
    with db.get_connection():
        pass  # would raise on a non-idempotent schema script


# ── Work Item round-trip ──────────────────────────────────────────────

def test_create_and_get_work_item_round_trips_json_fields(work_item):
    fetched = spine_store.get_work_item(work_item["work_item_id"])
    assert fetched is not None
    assert fetched["current_state"] == "CREATED"
    assert fetched["source_type"] == "government_opportunity"
    assert fetched["related_files"] == []
    assert fetched["source_refs"] == []


def test_work_item_rejects_unknown_state():
    with pytest.raises(ValueError):
        WorkItem(current_state="NOT_A_REAL_STATE")


def test_list_work_items_filters_by_state(work_item):
    other = spine_store.create_work_item(WorkItem(source_type="load_or_route_evaluation"))
    only_created = spine_store.list_work_items(current_state="CREATED")
    ids = {w["work_item_id"] for w in only_created}
    assert work_item["work_item_id"] in ids
    assert other["work_item_id"] in ids  # both start CREATED


# ── Portal Card ───────────────────────────────────────────────────────

def test_portal_card_required_closing_defaults_correctly(work_item):
    card = spine_store.create_portal_card(
        PortalCard(
            work_item_id=work_item["work_item_id"],
            card_level=3,
            card_type="DECISION",
            title="High Value Match",
            recommendation="Pursue this opportunity",
        )
    )
    assert card["required_closing"] == (
        "This is a recommendation only. No action is authorized. Mike decides."
    )
    fetched = spine_store.get_portal_card(card["card_id"])
    assert fetched["card_level"] == 3


def test_portal_card_rejects_invalid_level(work_item):
    with pytest.raises(ValueError):
        PortalCard(work_item_id=work_item["work_item_id"], card_level=6)


# ── Conflict Event ────────────────────────────────────────────────────

def test_conflict_event_round_trips(work_item):
    conflict = spine_store.create_conflict_event(
        ConflictEvent(
            work_item_id=work_item["work_item_id"],
            conflict_type="MISSING_SOURCE",
            affected_layer="Deterministic",
            affected_function="Intelligence Analyst",
            trigger="No source document attached",
            details="Opportunity has no linked source file.",
            recommended_path="Request source before proceeding.",
        )
    )
    fetched = spine_store.list_conflict_events(work_item["work_item_id"])
    assert len(fetched) == 1
    assert fetched[0]["conflict_id"] == conflict["conflict_id"]
    assert fetched[0]["human_decision_needed"] == 1


def test_conflict_event_rejects_unknown_type(work_item):
    with pytest.raises(ValueError):
        ConflictEvent(work_item_id=work_item["work_item_id"], conflict_type="NOT_REAL")


# ── Approval Event + linked Audit Event ──────────────────────────────

def test_approval_event_creates_linked_audit_event(work_item):
    approval = spine_store.create_approval_event(
        ApprovalEvent(
            work_item_id=work_item["work_item_id"],
            action="APPROVE_LOAD_PURSUIT",
            new_state="MIKE_APPROVED",
            object_type="work_item",
            object_id=work_item["work_item_id"],
        )
    )
    assert approval["audit_id"]
    audits = spine_store.list_audit_events(work_item["work_item_id"])
    assert len(audits) == 1
    assert audits[0]["audit_id"] == approval["audit_id"]


def test_approval_event_interim_identity_gap_is_nullable(work_item):
    """Stage 7 hasn't landed -- session_id/user_id/role must be allowed
    to stay unset without the write failing. See Stage 4 design doc
    Section 2.4."""
    approval = spine_store.create_approval_event(
        ApprovalEvent(
            work_item_id=work_item["work_item_id"],
            action="APPROVE_DRAFT",
            new_state="MIKE_APPROVED",
        )
    )
    assert approval["user_id"] is None
    assert approval["session_id"] is None


def test_approval_event_rejects_unknown_action(work_item):
    with pytest.raises(ValueError):
        ApprovalEvent(work_item_id=work_item["work_item_id"], action="DO_ANYTHING")


# ── State transition guard ────────────────────────────────────────────

def test_every_state_has_a_transitions_entry():
    assert set(ALLOWED_TRANSITIONS) == set(STATE_LIST)


def test_apply_transition_happy_path(work_item):
    updated = spine_store.apply_transition(
        work_item["work_item_id"],
        "VALIDATION_PENDING",
        actor_type="DISPATCH_SPINE",
        actor_id="validator",
    )
    assert updated["current_state"] == "VALIDATION_PENDING"
    events = spine_store.list_events(work_item["work_item_id"])
    assert len(events) == 1
    assert events[0]["previous_state"] == "CREATED"
    assert events[0]["new_state"] == "VALIDATION_PENDING"
    assert events[0]["requires_audit"] == 1


def test_apply_transition_rejects_invalid_move(work_item):
    with pytest.raises(InvalidTransitionError):
        spine_store.apply_transition(
            work_item["work_item_id"],
            "COMPLETED",  # CREATED -> COMPLETED is not allowed
            actor_type="DISPATCH_SPINE",
            actor_id="validator",
        )
    # rejected transition must not have moved the state or logged an event
    unchanged = spine_store.get_work_item(work_item["work_item_id"])
    assert unchanged["current_state"] == "CREATED"
    assert spine_store.list_events(work_item["work_item_id"]) == []


def test_apply_transition_unknown_work_item_raises():
    with pytest.raises(ValueError):
        spine_store.apply_transition(
            "WI-DOES-NOT-EXIST",
            "VALIDATION_PENDING",
            actor_type="DISPATCH_SPINE",
            actor_id="validator",
        )


@pytest.mark.parametrize(
    "current_state,new_state,expected",
    [
        ("CREATED", "VALIDATION_PENDING", True),
        ("CREATED", "COMPLETED", False),
        ("WAITING_FOR_MIKE", "MIKE_APPROVED", True),
        ("WAITING_FOR_MIKE", "SCORED", False),
        ("ARCHIVED", "CREATED", False),
    ],
)
def test_is_allowed_matrix(current_state, new_state, expected):
    assert is_allowed(current_state, new_state) is expected


def test_full_happy_path_walk_to_completion(work_item):
    """Mirrors the load/opportunity review loop described in
    DISPATCH_FINAL_BLUEPRINT_v1.md Section 25's cleanest first
    prototype: CREATED through to MIKE_APPROVED and COMPLETED."""
    wid = work_item["work_item_id"]
    path = [
        "VALIDATION_PENDING",
        "VALIDATED",
        "PORTAL_CARD_PENDING",
        "PORTAL_CARD_CREATED",
        "WAITING_FOR_MIKE",
        "MIKE_APPROVED",
        "COMPLETED",
    ]
    for state in path:
        spine_store.apply_transition(
            wid, state, actor_type="DISPATCH_SPINE", actor_id="test"
        )
    final = spine_store.get_work_item(wid)
    assert final["current_state"] == "COMPLETED"
    assert len(spine_store.list_events(wid)) == len(path)


# ── Structural guard: current_state is written in exactly one place ───

def test_only_apply_transition_writes_current_state():
    source = inspect.getsource(spine_store)
    occurrences = source.count("SET current_state=")
    assert occurrences == 1, (
        "work_items.current_state must be written in exactly one place "
        f"(apply_transition); found {occurrences} occurrence(s) in "
        "dispatch/spine/store.py"
    )
    assert "SET current_state=" in inspect.getsource(spine_store.apply_transition)
