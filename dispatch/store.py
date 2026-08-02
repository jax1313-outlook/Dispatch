"""CRUD persistence layer — SQLite-backed operations for all seven objects."""

from __future__ import annotations

import json

from dispatch.db import deserialize_json_fields, dict_from_row, get_connection
from dispatch.models import (
    EvidenceItem,
    ExceptionNotice,
    Expense,
    Load,
    LoadVisibilityRecord,
    MilestoneEvent,
    PODPackage,
    RateConfirmation,
    RetentionArchive,
    Settlement,
)


# ── Load ──────────────────────────────────────────────────────────────

def create_load(load: Load) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO loads
               (load_id, customer, broker_shipper, pickup_location,
                delivery_location, pickup_datetime, delivery_datetime,
                equipment, driver, status, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (load.load_id, load.customer, load.broker_shipper,
             load.pickup_location, load.delivery_location,
             load.pickup_datetime, load.delivery_datetime,
             load.equipment, load.driver, load.status,
             load.notes, load.created_at, load.updated_at),
        )
    return load.to_dict()


def get_load(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM loads WHERE load_id=?", (load_id,)).fetchone()
    return dict_from_row(row) if row else None


def list_loads(status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM loads WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM loads ORDER BY updated_at DESC"
            ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_load(load_id: str, **fields) -> dict | None:
    existing = get_load(load_id)
    if not existing:
        return None
    allowed = {
        "customer", "broker_shipper", "pickup_location", "delivery_location",
        "pickup_datetime", "delivery_datetime", "equipment", "driver",
        "status", "notes", "updated_at",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates.setdefault("updated_at", _utc_now())
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [load_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE loads SET {set_clause} WHERE load_id=?", values)
    return get_load(load_id)


def delete_load(load_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM loads WHERE load_id=?", (load_id,))
    return cur.rowcount > 0


# ── LoadVisibilityRecord ──────────────────────────────────────────────

def upsert_visibility(vis: LoadVisibilityRecord) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO visibility
               (load_id, current_status, last_milestone, next_expected_milestone,
                exception_flag, customer_note, internal_note, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(load_id) DO UPDATE SET
                current_status=excluded.current_status,
                last_milestone=excluded.last_milestone,
                next_expected_milestone=excluded.next_expected_milestone,
                exception_flag=excluded.exception_flag,
                customer_note=excluded.customer_note,
                internal_note=excluded.internal_note,
                updated_at=excluded.updated_at""",
            (vis.load_id, vis.current_status, vis.last_milestone,
             vis.next_expected_milestone, int(vis.exception_flag),
             vis.customer_note, vis.internal_note, vis.updated_at),
        )
    return vis.to_dict()


def get_visibility(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM visibility WHERE load_id=?", (load_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    d["exception_flag"] = bool(d["exception_flag"])
    return d


# ── MilestoneEvent ────────────────────────────────────────────────────

def create_milestone(ms: MilestoneEvent) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO milestones
               (milestone_id, load_id, event_type, event_time, location,
                source, note, entered_by, validation_status)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ms.milestone_id, ms.load_id, ms.event_type, ms.event_time,
             ms.location, ms.source, ms.note, ms.entered_by,
             ms.validation_status),
        )
    return ms.to_dict()


def list_milestones(load_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM milestones WHERE load_id=? ORDER BY event_time ASC",
            (load_id,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def get_milestone(milestone_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM milestones WHERE milestone_id=?", (milestone_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


# ── EvidenceItem ──────────────────────────────────────────────────────

def create_evidence(ev: EvidenceItem) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO evidence
               (evidence_id, load_id, related_milestone_id, evidence_type,
                file_path, capture_time, description, uploaded_by, checksum)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ev.evidence_id, ev.load_id, ev.related_milestone_id,
             ev.evidence_type, ev.file_path, ev.capture_time,
             ev.description, ev.uploaded_by, ev.checksum),
        )
    return ev.to_dict()


def list_evidence(load_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM evidence WHERE load_id=? ORDER BY capture_time ASC",
            (load_id,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def get_evidence(evidence_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


# ── ExceptionNotice ───────────────────────────────────────────────────

def create_exception(exc: ExceptionNotice) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO exceptions
               (exception_id, load_id, related_milestone_id, exception_type,
                severity, description, first_reported, status,
                resolution_note, resolved_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (exc.exception_id, exc.load_id, exc.related_milestone_id,
             exc.exception_type, exc.severity, exc.description,
             exc.first_reported, exc.status, exc.resolution_note,
             exc.resolved_at),
        )
    return exc.to_dict()


def list_exceptions(load_id: str | None = None, status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        clauses: list[str] = []
        params: list[str] = []
        if load_id:
            clauses.append("load_id=?")
            params.append(load_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        where = " AND ".join(clauses)
        sql = "SELECT * FROM exceptions"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY first_reported DESC"
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def update_exception(exception_id: str, **fields) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM exceptions WHERE exception_id=?", (exception_id,)
        ).fetchone()
    if not row:
        return None
    allowed = {"status", "resolution_note", "resolved_at", "severity"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return dict_from_row(row)
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [exception_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE exceptions SET {set_clause} WHERE exception_id=?", values
        )
        row = conn.execute(
            "SELECT * FROM exceptions WHERE exception_id=?", (exception_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


# ── PODPackage ────────────────────────────────────────────────────────

def create_pod(pod: PODPackage) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO pod_packages
               (pod_id, load_id, evidence_ids, generated_at, status,
                recipient, file_path, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (pod.pod_id, pod.load_id, json.dumps(pod.evidence_ids),
             pod.generated_at, pod.status, pod.recipient,
             pod.file_path, pod.notes),
        )
    return pod.to_dict()


def get_pod(pod_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM pod_packages WHERE pod_id=?", (pod_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    return deserialize_json_fields(d, "evidence_ids")


def list_pods(load_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pod_packages WHERE load_id=? ORDER BY generated_at DESC",
            (load_id,),
        ).fetchall()
    results = []
    for r in rows:
        d = dict_from_row(r)
        results.append(deserialize_json_fields(d, "evidence_ids"))
    return results


def update_pod(pod_id: str, **fields) -> dict | None:
    existing = get_pod(pod_id)
    if not existing:
        return None
    allowed = {"status", "recipient", "file_path", "notes", "evidence_ids"}
    updates = {}
    for k, v in fields.items():
        if k in allowed:
            updates[k] = json.dumps(v) if k == "evidence_ids" else v
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [pod_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE pod_packages SET {set_clause} WHERE pod_id=?", values
        )
    return get_pod(pod_id)


# ── RetentionArchive ──────────────────────────────────────────────────

def create_retention(ret: RetentionArchive) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO retention
               (archive_id, load_id, final_status, pod_package_id,
                evidence_index, archive_location, retention_status, archived_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (ret.archive_id, ret.load_id, ret.final_status,
             ret.pod_package_id, json.dumps(ret.evidence_index),
             ret.archive_location, ret.retention_status, ret.archived_at),
        )
    return ret.to_dict()


def get_retention(archive_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM retention WHERE archive_id=?", (archive_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    return deserialize_json_fields(d, "evidence_index")


def get_retention_by_load(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM retention WHERE load_id=?", (load_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    return deserialize_json_fields(d, "evidence_index")


def list_retentions() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM retention ORDER BY archived_at DESC"
        ).fetchall()
    results = []
    for r in rows:
        d = dict_from_row(r)
        results.append(deserialize_json_fields(d, "evidence_index"))
    return results


# ── RateConfirmation ─────────────────────────────────────────────────

def create_rate_confirmation(rc: RateConfirmation) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO rate_confirmations
               (confirmation_id, load_id, rate_amount, rate_type,
                distance_miles, confirmed_by, notes, confirmed_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (rc.confirmation_id, rc.load_id, rc.rate_amount,
             rc.rate_type, rc.distance_miles, rc.confirmed_by,
             rc.notes, rc.confirmed_at),
        )
    return rc.to_dict()


def get_rate_confirmation(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM rate_confirmations WHERE load_id=?", (load_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    rc = RateConfirmation(**d)
    return rc.to_dict()


def update_rate_confirmation(load_id: str, **fields) -> dict | None:
    existing = get_rate_confirmation(load_id)
    if not existing:
        return None
    allowed = {"rate_amount", "rate_type", "distance_miles", "confirmed_by", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [load_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE rate_confirmations SET {set_clause} WHERE load_id=?", values
        )
    return get_rate_confirmation(load_id)


def delete_rate_confirmation(load_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM rate_confirmations WHERE load_id=?", (load_id,)
        )
    return cur.rowcount > 0


# ── Expense ──────────────────────────────────────────────────────────

def create_expense(exp: Expense) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO expenses
               (expense_id, load_id, category, description, amount,
                incurred_at, receipt_evidence_id, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (exp.expense_id, exp.load_id, exp.category,
             exp.description, exp.amount, exp.incurred_at,
             exp.receipt_evidence_id, exp.notes),
        )
    return exp.to_dict()


def get_expense(expense_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM expenses WHERE expense_id=?", (expense_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_expenses(load_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE load_id=? ORDER BY incurred_at ASC",
            (load_id,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_expense(expense_id: str, **fields) -> dict | None:
    existing = get_expense(expense_id)
    if not existing:
        return None
    allowed = {"category", "description", "amount", "receipt_evidence_id", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [expense_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE expenses SET {set_clause} WHERE expense_id=?", values
        )
    return get_expense(expense_id)


def delete_expense(expense_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM expenses WHERE expense_id=?", (expense_id,)
        )
    return cur.rowcount > 0


# ── Settlement ───────────────────────────────────────────────────────

def create_settlement(stl: Settlement) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO settlements
               (settlement_id, load_id, invoice_number, invoice_amount,
                invoice_date, due_date, payment_status, payment_amount,
                payment_date, payment_method, factoring_fee, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (stl.settlement_id, stl.load_id, stl.invoice_number,
             stl.invoice_amount, stl.invoice_date, stl.due_date,
             stl.payment_status, stl.payment_amount, stl.payment_date,
             stl.payment_method, stl.factoring_fee, stl.notes),
        )
    return stl.to_dict()


def get_settlement(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM settlements WHERE load_id=?", (load_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    stl = Settlement(**d)
    return stl.to_dict()


def update_settlement(load_id: str, **fields) -> dict | None:
    existing = get_settlement(load_id)
    if not existing:
        return None
    allowed = {
        "invoice_amount", "due_date", "payment_status", "payment_amount",
        "payment_date", "payment_method", "factoring_fee", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [load_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE settlements SET {set_clause} WHERE load_id=?", values
        )
    return get_settlement(load_id)


def list_settlements(payment_status: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if payment_status:
            rows = conn.execute(
                "SELECT * FROM settlements WHERE payment_status=? ORDER BY invoice_date DESC",
                (payment_status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM settlements ORDER BY invoice_date DESC"
            ).fetchall()
    results = []
    for r in rows:
        d = dict_from_row(r)
        stl = Settlement(**d)
        results.append(stl.to_dict())
    return results
