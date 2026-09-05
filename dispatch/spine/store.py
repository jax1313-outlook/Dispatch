"""CRUD persistence layer for the Dispatch Spine's six schemas.

Mirrors dispatch/store.py's style (with get_connection() as conn: ...).
`apply_transition()` is the only function that may change
`work_items.current_state` -- see dispatch.spine.state.
"""

from __future__ import annotations

import json

from dispatch.db import deserialize_json_fields, dict_from_row, get_connection
from dispatch.models import _gen_id, _utc_now
from dispatch.spine.models import (
    ApprovalEvent,
    AuditEvent,
    ConflictEvent,
    Event,
    PortalCard,
    WorkItem,
)
from dispatch.spine.state import transition

_JSON_FIELDS = {
    "work_items": ("related_files", "source_refs"),
    "events": ("source_refs",),
    "portal_cards": ("source_refs", "allowed_actions"),
    "approval_events": ("authentication_context",),
    "conflict_events": ("options",),
    "audit_events": ("source_refs",),
}


# ── Work Item ─────────────────────────────────────────────────────────

def create_work_item(item: WorkItem) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO work_items
               (work_item_id, created_at, updated_at, source_type, source_id,
                current_state, priority, consequence_level, assigned_function,
                required_action, source_confidence, due_date, related_files,
                source_refs, validation_status, scoring_status, cognitive_status,
                portal_card_id, final_disposition)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item.work_item_id, item.created_at, item.updated_at, item.source_type,
             item.source_id, item.current_state, item.priority, item.consequence_level,
             item.assigned_function, item.required_action, item.source_confidence,
             item.due_date, json.dumps(item.related_files), json.dumps(item.source_refs),
             item.validation_status, item.scoring_status, item.cognitive_status,
             item.portal_card_id, item.final_disposition),
        )
    return item.to_dict()


def get_work_item(work_item_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM work_items WHERE work_item_id=?", (work_item_id,)
        ).fetchone()
    if not row:
        return None
    return deserialize_json_fields(dict_from_row(row), *_JSON_FIELDS["work_items"])


def list_work_items(current_state: str | None = None) -> list[dict]:
    sql = "SELECT * FROM work_items"
    params: list = []
    if current_state:
        sql += " WHERE current_state=?"
        params.append(current_state)
    sql += " ORDER BY updated_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["work_items"]) for r in rows]


# ── Event ─────────────────────────────────────────────────────────────

def _insert_event(conn, event: Event) -> None:
    conn.execute(
        """INSERT INTO events
           (event_id, timestamp, work_item_id, event_type, actor_type, actor_id,
            previous_state, new_state, summary, source_refs, requires_audit)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (event.event_id, event.timestamp, event.work_item_id, event.event_type,
         event.actor_type, event.actor_id, event.previous_state, event.new_state,
         event.summary, json.dumps(event.source_refs), int(event.requires_audit)),
    )


def create_event(event: Event) -> dict:
    with get_connection() as conn:
        _insert_event(conn, event)
    return event.to_dict()


def list_events(work_item_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE work_item_id=? ORDER BY timestamp ASC",
            (work_item_id,),
        ).fetchall()
    return [deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["events"]) for r in rows]


# ── State transition (the only path that may change current_state) ────

def apply_transition(
    work_item_id: str,
    new_state: str,
    *,
    actor_type: str,
    actor_id: str,
    summary: str = "",
    source_refs: list | None = None,
) -> dict:
    """Validate and persist a work item state transition plus its Event,
    in one connection/transaction. This is the only function in the
    codebase that may update `work_items.current_state` -- everything
    else about the state machine depends on that remaining true.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM work_items WHERE work_item_id=?", (work_item_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown work_item_id: {work_item_id!r}")
        work_item = dict_from_row(row)
        event = transition(
            work_item,
            new_state,
            actor_type=actor_type,
            actor_id=actor_id,
            summary=summary,
            source_refs=source_refs,
        )
        conn.execute(
            "UPDATE work_items SET current_state=?, updated_at=? WHERE work_item_id=?",
            (new_state, event.timestamp, work_item_id),
        )
        _insert_event(conn, event)
    return get_work_item(work_item_id)


# ── Portal Card ───────────────────────────────────────────────────────

def create_portal_card(card: PortalCard) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO portal_cards
               (card_id, work_item_id, created_at, card_level, card_type, title,
                summary, source_refs, recommendation, decision_needed,
                allowed_actions, required_closing)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (card.card_id, card.work_item_id, card.created_at, card.card_level,
             card.card_type, card.title, card.summary, json.dumps(card.source_refs),
             card.recommendation, card.decision_needed, json.dumps(card.allowed_actions),
             card.required_closing),
        )
    return card.to_dict()


def get_portal_card(card_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM portal_cards WHERE card_id=?", (card_id,)
        ).fetchone()
    if not row:
        return None
    return deserialize_json_fields(dict_from_row(row), *_JSON_FIELDS["portal_cards"])


def list_portal_cards(
    work_item_id: str | None = None, card_level: int | None = None
) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if work_item_id:
        clauses.append("work_item_id=?")
        params.append(work_item_id)
    if card_level is not None:
        clauses.append("card_level=?")
        params.append(card_level)
    sql = "SELECT * FROM portal_cards"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["portal_cards"]) for r in rows]


# ── Audit Event ───────────────────────────────────────────────────────

def _insert_audit_event(conn, audit: AuditEvent) -> None:
    conn.execute(
        """INSERT INTO audit_events
           (audit_id, timestamp, work_item_id, event_id, actor_type, actor_id,
            action, previous_state, new_state, source_refs, hash, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (audit.audit_id, audit.timestamp, audit.work_item_id, audit.event_id,
         audit.actor_type, audit.actor_id, audit.action, audit.previous_state,
         audit.new_state, json.dumps(audit.source_refs), audit.hash, audit.notes),
    )


def create_audit_event(audit: AuditEvent) -> dict:
    with get_connection() as conn:
        _insert_audit_event(conn, audit)
    return audit.to_dict()


def list_audit_events(work_item_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE work_item_id=? ORDER BY timestamp ASC",
            (work_item_id,),
        ).fetchall()
    return [deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["audit_events"]) for r in rows]


# ── Approval Event ────────────────────────────────────────────────────

def create_approval_event(approval: ApprovalEvent, *, audit: AuditEvent | None = None) -> dict:
    """Creates the linked Audit Event first (same transaction) if one
    isn't already supplied, then the Approval Event referencing it --
    `approval_events.audit_id` is NOT NULL, so this ordering is required.
    See DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md Section 2.4, including
    the interim-identity note: `session_id`/`user_id`/`role` stay
    whatever the caller passed (nullable, unauthenticated) until Stage 7.
    """
    if audit is None:
        audit = AuditEvent(
            work_item_id=approval.work_item_id,
            actor_type="DISPATCH_SPINE",
            actor_id="approval_event",
            action=approval.action,
            new_state=approval.new_state,
            notes="Audit record for the linked approval_event.",
        )
    if not approval.approval_event_id:
        approval.approval_event_id = _gen_id("APV")
    if not approval.timestamp:
        approval.timestamp = _utc_now()
    approval.audit_id = audit.audit_id
    with get_connection() as conn:
        _insert_audit_event(conn, audit)
        conn.execute(
            """INSERT INTO approval_events
               (approval_event_id, timestamp, session_id, user_id, role,
                work_item_id, portal_card_id, object_type, object_id,
                object_version, action, previous_state, new_state, comments,
                authentication_context, audit_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (approval.approval_event_id, approval.timestamp, approval.session_id,
             approval.user_id, approval.role, approval.work_item_id,
             approval.portal_card_id, approval.object_type, approval.object_id,
             approval.object_version, approval.action, approval.previous_state,
             approval.new_state, approval.comments,
             json.dumps(approval.authentication_context)
             if approval.authentication_context else None,
             approval.audit_id),
        )
    return approval.to_dict()


def list_approval_events(work_item_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM approval_events WHERE work_item_id=? ORDER BY timestamp ASC",
            (work_item_id,),
        ).fetchall()
    return [
        deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["approval_events"])
        for r in rows
    ]


# ── Conflict Event ────────────────────────────────────────────────────

def create_conflict_event(conflict: ConflictEvent) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO conflict_events
               (conflict_id, timestamp, work_item_id, conflict_type, affected_layer,
                affected_function, trigger, details, options, recommended_path,
                human_decision_needed, current_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (conflict.conflict_id, conflict.timestamp, conflict.work_item_id,
             conflict.conflict_type, conflict.affected_layer, conflict.affected_function,
             conflict.trigger, conflict.details, json.dumps(conflict.options),
             conflict.recommended_path, int(conflict.human_decision_needed),
             conflict.current_state),
        )
    return conflict.to_dict()


def list_conflict_events(work_item_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conflict_events WHERE work_item_id=? ORDER BY timestamp ASC",
            (work_item_id,),
        ).fetchall()
    return [
        deserialize_json_fields(dict_from_row(r), *_JSON_FIELDS["conflict_events"])
        for r in rows
    ]
