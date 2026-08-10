"""CRUD persistence layer for Dispatch Security Foundation.

Mirrors dispatch/store.py and dispatch/spine/store.py's style
(with get_connection() as conn: ...).
"""

from __future__ import annotations

import json

from dispatch.db import deserialize_json_fields, dict_from_row, get_connection
from dispatch.models import _utc_now
from dispatch.security.models import PinRecord, SecurityEvent, Session, User


# ── User ──────────────────────────────────────────────────────────────

def create_user(user: User) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO users
               (user_id, display_name, role, status, pin_record_id,
                created_at, updated_at, last_login_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user.user_id, user.display_name, user.role, user.status,
             user.pin_record_id, user.created_at, user.updated_at, user.last_login_at),
        )
    return user.to_dict()


def get_user(user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return dict_from_row(row) if row else None


def get_user_by_display_name(display_name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE display_name=?", (display_name,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_users(role: str | None = None) -> list[dict]:
    sql = "SELECT * FROM users"
    params: list = []
    if role:
        sql += " WHERE role=?"
        params.append(role)
    sql += " ORDER BY created_at ASC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def update_user(user_id: str, **fields) -> dict | None:
    existing = get_user(user_id)
    if not existing:
        return None
    allowed = {"display_name", "role", "status", "pin_record_id", "last_login_at", "updated_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    updates.setdefault("updated_at", _utc_now())
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
    return get_user(user_id)


# ── PIN Record ────────────────────────────────────────────────────────

def create_pin_record(pin: PinRecord) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pin_records
               (pin_record_id, user_id, pin_hash, salt, status, reset_required,
                failed_attempt_count, locked_until, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pin.pin_record_id, pin.user_id, pin.pin_hash, pin.salt, pin.status,
             int(pin.reset_required), pin.failed_attempt_count, pin.locked_until,
             pin.created_at, pin.updated_at),
        )
    return pin.to_dict()


def get_pin_record(pin_record_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pin_records WHERE pin_record_id=?", (pin_record_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def get_active_pin_record_for_user(user_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pin_records WHERE user_id=? AND status='active' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict_from_row(row) if row else None


def record_pin_failure(pin_record_id: str, *, lock_until: str | None) -> dict | None:
    """Increments failed_attempt_count; sets locked_until when the
    caller (dispatch.security.auth) determines the threshold was hit.
    """
    existing = get_pin_record(pin_record_id)
    if not existing:
        return None
    new_count = existing["failed_attempt_count"] + 1
    updates = {"failed_attempt_count": new_count, "updated_at": _utc_now()}
    if lock_until:
        updates["locked_until"] = lock_until
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [pin_record_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE pin_records SET {set_clause} WHERE pin_record_id=?", values)
    return get_pin_record(pin_record_id)


def reset_pin_failures(pin_record_id: str) -> dict | None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE pin_records SET failed_attempt_count=0, locked_until=NULL, "
            "updated_at=? WHERE pin_record_id=?",
            (_utc_now(), pin_record_id),
        )
    return get_pin_record(pin_record_id)


def update_pin_record(pin_record_id: str, **fields) -> dict | None:
    existing = get_pin_record(pin_record_id)
    if not existing:
        return None
    allowed = {"pin_hash", "salt", "status", "reset_required", "failed_attempt_count",
               "locked_until", "updated_at"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    if "reset_required" in updates:
        updates["reset_required"] = int(updates["reset_required"])
    updates.setdefault("updated_at", _utc_now())
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [pin_record_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE pin_records SET {set_clause} WHERE pin_record_id=?", values)
    return get_pin_record(pin_record_id)


# ── Session ───────────────────────────────────────────────────────────

def create_session(session: Session) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO sessions
               (session_id, user_id, role, started_at, last_active_at,
                status, authentication_method)
               VALUES (?,?,?,?,?,?,?)""",
            (session.session_id, session.user_id, session.role, session.started_at,
             session.last_active_at, session.status, session.authentication_method),
        )
    return session.to_dict()


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def touch_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET last_active_at=? WHERE session_id=?",
            (_utc_now(), session_id),
        )
    return get_session(session_id)


def revoke_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET status='revoked' WHERE session_id=?", (session_id,)
        )
    return get_session(session_id)


# ── Security Event ────────────────────────────────────────────────────

def create_security_event(event: SecurityEvent) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO security_events
               (event_id, event_type, user_id, timestamp, details)
               VALUES (?,?,?,?,?)""",
            (event.event_id, event.event_type, event.user_id, event.timestamp,
             json.dumps(event.details)),
        )
    return event.to_dict()


def list_security_events(user_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM security_events"
    params: list = []
    if user_id:
        sql += " WHERE user_id=?"
        params.append(user_id)
    sql += " ORDER BY timestamp DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [deserialize_json_fields(dict_from_row(r), "details") for r in rows]
