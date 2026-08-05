"""CRUD persistence layer — SQLite-backed operations for all seven objects."""

from __future__ import annotations

import json
import math

from dispatch.db import deserialize_json_fields, dict_from_row, get_connection
from dispatch.models import (
    DetentionEvent,
    Driver,
    Equipment,
    EvidenceItem,
    ExceptionNotice,
    Expense,
    BrokerContact,
    IFTAFuelEvidence,
    IFTAFuelPurchase,
    IFTAReportApproval,
    IFTATripLeg,
    Load,
    LoadActivity,
    LoadVisibilityRecord,
    MilestoneEvent,
    PODPackage,
    RateConfirmation,
    RetentionArchive,
    Settlement,
)

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


def _paginate(
    sql: str,
    params: list,
    conn,
    *,
    page: int | None = None,
    per_page: int | None = None,
    row_mapper=dict_from_row,
):
    if page is None:
        rows = conn.execute(sql, params).fetchall()
        return [row_mapper(r) for r in rows]

    count_sql = f"SELECT COUNT(*) FROM ({sql})"
    total = conn.execute(count_sql, params).fetchone()[0]

    pp = min(per_page or DEFAULT_PER_PAGE, MAX_PER_PAGE)
    pp = max(pp, 1)
    p = max(page, 1)
    offset = (p - 1) * pp

    paged_sql = f"{sql} LIMIT ? OFFSET ?"
    rows = conn.execute(paged_sql, params + [pp, offset]).fetchall()
    return {
        "items": [row_mapper(r) for r in rows],
        "total": total,
        "page": p,
        "per_page": pp,
        "pages": math.ceil(total / pp) if total else 0,
    }


# ── Load ──────────────────────────────────────────────────────────────

def create_load(load: Load) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO loads
               (load_id, customer, broker_shipper, pickup_location,
                delivery_location, pickup_datetime, delivery_datetime,
                equipment, driver, driver_id, equipment_id,
                status, source, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (load.load_id, load.customer, load.broker_shipper,
             load.pickup_location, load.delivery_location,
             load.pickup_datetime, load.delivery_datetime,
             load.equipment, load.driver, load.driver_id,
             load.equipment_id, load.status, load.source,
             load.notes, load.created_at, load.updated_at),
        )
    return load.to_dict()


def get_load(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM loads WHERE load_id=?", (load_id,)).fetchone()
    return dict_from_row(row) if row else None


def list_loads(
    status: str | None = None,
    customer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if customer:
        clauses.append("customer LIKE ?")
        params.append(f"%{customer}%")
    if date_from:
        clauses.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("created_at <= ?")
        params.append(date_to + "T23:59:59Z" if "T" not in date_to else date_to)
    where = " AND ".join(clauses)
    sql = "SELECT * FROM loads"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY updated_at DESC"
    with get_connection() as conn:
        return _paginate(sql, params, conn, page=page, per_page=per_page)


def get_lane_history(
    pickup_location: str,
    delivery_location: str,
    exclude_load_id: str = "",
    limit: int = 10,
) -> list[dict]:
    if not pickup_location or not delivery_location:
        return []
    sql = (
        "SELECT * FROM loads "
        "WHERE pickup_location=? AND delivery_location=? AND load_id!=? "
        "ORDER BY created_at DESC LIMIT ?"
    )
    with get_connection() as conn:
        rows = conn.execute(
            sql, (pickup_location, delivery_location, exclude_load_id, limit)
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_load(load_id: str, **fields) -> dict | None:
    existing = get_load(load_id)
    if not existing:
        return None
    allowed = {
        "customer", "broker_shipper", "pickup_location", "delivery_location",
        "pickup_datetime", "delivery_datetime", "equipment", "driver",
        "driver_id", "equipment_id", "status", "source", "notes", "updated_at",
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
    _CHILD_TABLES = [
        "visibility", "milestones", "evidence", "exceptions",
        "pod_packages", "retention", "rate_confirmations",
        "expenses", "settlements", "activities", "detention_events",
    ]
    with get_connection() as conn:
        for table in _CHILD_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE load_id=?", (load_id,))
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


def update_visibility_notes(load_id: str, **fields) -> dict | None:
    existing = get_visibility(load_id)
    if not existing:
        return None
    allowed = {"customer_note", "internal_note"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [load_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE visibility SET {set_clause} WHERE load_id=?", values
        )
    return get_visibility(load_id)


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


def update_milestone(milestone_id: str, **fields) -> dict | None:
    existing = get_milestone(milestone_id)
    if not existing:
        return None
    allowed = {"validation_status", "note", "location"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [milestone_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE milestones SET {set_clause} WHERE milestone_id=?", values
        )
    return get_milestone(milestone_id)


def get_recent_activity(limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT m.*, l.customer, l.status AS load_status
               FROM milestones m
               JOIN loads l ON m.load_id = l.load_id
               ORDER BY m.event_time DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


# ── EvidenceItem ──────────────────────────────────────────────────────

def create_evidence(ev: EvidenceItem) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO evidence
               (evidence_id, load_id, related_milestone_id, evidence_type,
                file_path, original_filename, file_size, mime_type,
                capture_time, description, uploaded_by, checksum)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ev.evidence_id, ev.load_id, ev.related_milestone_id,
             ev.evidence_type, ev.file_path, ev.original_filename,
             ev.file_size, ev.mime_type, ev.capture_time,
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


def update_evidence(evidence_id: str, **fields) -> dict | None:
    existing = get_evidence(evidence_id)
    if not existing:
        return None
    allowed = {
        "evidence_type", "description", "uploaded_by",
        "file_path", "original_filename", "file_size", "mime_type", "checksum",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [evidence_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE evidence SET {set_clause} WHERE evidence_id=?", values
        )
    return get_evidence(evidence_id)


def delete_evidence(evidence_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM evidence WHERE evidence_id=?", (evidence_id,)
        )
    return cur.rowcount > 0


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


def list_exceptions(
    load_id: str | None = None,
    status: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
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
    with get_connection() as conn:
        return _paginate(sql, params, conn, page=page, per_page=per_page)


def update_exception(exception_id: str, **fields) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM exceptions WHERE exception_id=?", (exception_id,)
        ).fetchone()
    if not row:
        return None
    allowed = {"status", "resolution_note", "resolved_at", "severity",
                "exception_type", "description"}
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
                evidence_index, financial_summary, archive_location,
                retention_status, archived_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ret.archive_id, ret.load_id, ret.final_status,
             ret.pod_package_id, json.dumps(ret.evidence_index),
             json.dumps(ret.financial_summary),
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
    return deserialize_json_fields(d, "evidence_index", "financial_summary")


def get_retention_by_load(load_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM retention WHERE load_id=?", (load_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    return deserialize_json_fields(d, "evidence_index", "financial_summary")


def list_retentions() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM retention ORDER BY archived_at DESC"
        ).fetchall()
    results = []
    for r in rows:
        d = dict_from_row(r)
        results.append(deserialize_json_fields(d, "evidence_index", "financial_summary"))
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


def list_settlements(
    payment_status: str | None = None,
    customer: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    invoice_number: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    clauses: list[str] = []
    params: list = []
    if payment_status:
        clauses.append("s.payment_status=?")
        params.append(payment_status)
    if customer:
        clauses.append("l.customer LIKE ?")
        params.append(f"%{customer}%")
    if date_from:
        clauses.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("s.invoice_date <= ?")
        params.append(date_to + "T23:59:59" if "T" not in date_to else date_to)
    if invoice_number:
        clauses.append("s.invoice_number LIKE ?")
        params.append(f"%{invoice_number}%")
    where = " AND ".join(clauses)
    needs_join = customer is not None
    if needs_join:
        sql = "SELECT s.* FROM settlements s JOIN loads l ON s.load_id = l.load_id"
    else:
        sql = "SELECT s.* FROM settlements s"
    if where:
        sql += " WHERE " + where
    sql += " ORDER BY s.invoice_date DESC"

    def settlement_mapper(r):
        d = dict_from_row(r)
        return Settlement(**d).to_dict()

    with get_connection() as conn:
        return _paginate(sql, params, conn, page=page, per_page=per_page, row_mapper=settlement_mapper)


# ── Driver ──────────────────────────────────────────────────────────

def create_driver(drv: Driver) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO drivers
               (driver_id, name, license_number, license_class, phone,
                email, status, hire_date, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (drv.driver_id, drv.name, drv.license_number,
             drv.license_class, drv.phone, drv.email,
             drv.status, drv.hire_date, drv.notes,
             drv.created_at, drv.updated_at),
        )
    return drv.to_dict()


def get_driver(driver_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM drivers WHERE driver_id=?", (driver_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_drivers(
    status: str | None = None,
    name: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if name:
        clauses.append("name LIKE ?")
        params.append(f"%{name}%")
    sql = "SELECT * FROM drivers"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY name ASC"
    with get_connection() as conn:
        return _paginate(sql, params, conn, page=page, per_page=per_page)


def update_driver(driver_id: str, **fields) -> dict | None:
    existing = get_driver(driver_id)
    if not existing:
        return None
    allowed = {
        "name", "license_number", "license_class", "phone",
        "email", "status", "hire_date", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [driver_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE drivers SET {set_clause} WHERE driver_id=?", values
        )
    return get_driver(driver_id)


def delete_driver(driver_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM drivers WHERE driver_id=?", (driver_id,)
        )
    return cur.rowcount > 0


# ── Equipment ───────────────────────────────────────────────────────

def create_equipment(eqp: Equipment) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO equipment
               (equipment_id, unit_number, equipment_type, make, model,
                year, vin, license_plate, status, notes,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eqp.equipment_id, eqp.unit_number, eqp.equipment_type,
             eqp.make, eqp.model, eqp.year, eqp.vin,
             eqp.license_plate, eqp.status, eqp.notes,
             eqp.created_at, eqp.updated_at),
        )
    return eqp.to_dict()


def get_equipment(equipment_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM equipment WHERE equipment_id=?", (equipment_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_equipment(
    status: str | None = None,
    equipment_type: str | None = None,
    unit_number: str | None = None,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> list[dict] | dict:
    clauses: list[str] = []
    params: list = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if equipment_type:
        clauses.append("equipment_type=?")
        params.append(equipment_type)
    if unit_number:
        clauses.append("unit_number LIKE ?")
        params.append(f"%{unit_number}%")
    sql = "SELECT * FROM equipment"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY unit_number ASC"
    with get_connection() as conn:
        return _paginate(sql, params, conn, page=page, per_page=per_page)


_TERMINAL_STATUSES = ("completed", "archived", "cancelled")


def get_active_load_for_driver(driver_id: str) -> dict | None:
    placeholders = ",".join("?" for _ in _TERMINAL_STATUSES)
    sql = (
        f"SELECT * FROM loads WHERE driver_id=? AND status NOT IN ({placeholders}) "
        "ORDER BY updated_at DESC LIMIT 1"
    )
    with get_connection() as conn:
        row = conn.execute(sql, (driver_id, *_TERMINAL_STATUSES)).fetchone()
    return dict_from_row(row) if row else None


def get_active_load_for_equipment(equipment_id: str) -> dict | None:
    placeholders = ",".join("?" for _ in _TERMINAL_STATUSES)
    sql = (
        f"SELECT * FROM loads WHERE equipment_id=? AND status NOT IN ({placeholders}) "
        "ORDER BY updated_at DESC LIMIT 1"
    )
    with get_connection() as conn:
        row = conn.execute(sql, (equipment_id, *_TERMINAL_STATUSES)).fetchone()
    return dict_from_row(row) if row else None


def get_loads_for_driver(driver_id: str) -> list[dict]:
    sql = "SELECT * FROM loads WHERE driver_id=? ORDER BY updated_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, (driver_id,)).fetchall()
    return [dict_from_row(r) for r in rows]


def get_loads_for_equipment(equipment_id: str) -> list[dict]:
    sql = "SELECT * FROM loads WHERE equipment_id=? ORDER BY updated_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, (equipment_id,)).fetchall()
    return [dict_from_row(r) for r in rows]


def get_fleet_assignments() -> dict:
    placeholders = ",".join("?" for _ in _TERMINAL_STATUSES)
    sql = (
        f"SELECT load_id, driver_id, equipment_id, customer, status "
        f"FROM loads WHERE status NOT IN ({placeholders}) "
        "AND (driver_id != '' OR equipment_id != '')"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, _TERMINAL_STATUSES).fetchall()
    driver_loads: dict[str, dict] = {}
    equip_loads: dict[str, dict] = {}
    for row in rows:
        r = dict_from_row(row)
        if r["driver_id"]:
            driver_loads[r["driver_id"]] = r
        if r["equipment_id"]:
            equip_loads[r["equipment_id"]] = r
    return {"driver_loads": driver_loads, "equipment_loads": equip_loads}


def update_equipment(equipment_id: str, **fields) -> dict | None:
    existing = get_equipment(equipment_id)
    if not existing:
        return None
    allowed = {
        "unit_number", "equipment_type", "make", "model", "year",
        "vin", "license_plate", "status", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [equipment_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE equipment SET {set_clause} WHERE equipment_id=?", values
        )
    return get_equipment(equipment_id)


def delete_equipment(equipment_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM equipment WHERE equipment_id=?", (equipment_id,)
        )
    return cur.rowcount > 0


# ── Activities ─────────────────────────────────────────────────────────


def create_activity(activity: LoadActivity) -> dict:
    d = activity.to_dict()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO activities
               (activity_id, load_id, activity_type, message, author,
                source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (d["activity_id"], d["load_id"], d["activity_type"],
             d["message"], d["author"], d["source"], d["created_at"]),
        )
    return d


def list_activities(
    load_id: str,
    activity_type: str | None = None,
) -> list[dict]:
    clauses = ["load_id=?"]
    params: list = [load_id]
    if activity_type:
        clauses.append("activity_type=?")
        params.append(activity_type)
    sql = f"SELECT * FROM activities WHERE {' AND '.join(clauses)} ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict_from_row(r) for r in rows]


def delete_activity(activity_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM activities WHERE activity_id=?", (activity_id,)
        )
    return cur.rowcount > 0


# ── Detention Events ────────────────────────────────────────────────


def create_detention(det: DetentionEvent) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO detention_events
               (detention_id, load_id, location_type, started_at, ended_at,
                free_hours, hourly_rate, status, notes, expense_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (det.detention_id, det.load_id, det.location_type,
             det.started_at, det.ended_at, det.free_hours,
             det.hourly_rate, det.status, det.notes,
             det.expense_id, det.created_at),
        )
    return det.to_dict()


def get_detention(detention_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM detention_events WHERE detention_id=?",
            (detention_id,),
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    det = DetentionEvent(**d)
    return det.to_dict()


def list_detentions(load_id: str | None = None, status: str | None = None) -> list[dict]:
    clauses: list[str] = []
    params: list = []
    if load_id:
        clauses.append("load_id=?")
        params.append(load_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    sql = "SELECT * FROM detention_events"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY started_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    results = []
    for r in rows:
        d = dict_from_row(r)
        det = DetentionEvent(**d)
        results.append(det.to_dict())
    return results


def update_detention(detention_id: str, **fields) -> dict | None:
    existing = get_detention(detention_id)
    if not existing:
        return None
    allowed = {"ended_at", "free_hours", "hourly_rate", "status", "notes", "expense_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [detention_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE detention_events SET {set_clause} WHERE detention_id=?",
            values,
        )
    return get_detention(detention_id)


def delete_detention(detention_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM detention_events WHERE detention_id=?",
            (detention_id,),
        )
    return cur.rowcount > 0


# ── Lane Templates ──────────────────────────────────────────────────

def create_lane_template(tpl: "LaneTemplate") -> dict:  # noqa: F821
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO lane_templates
               (template_id, name, customer, broker_shipper,
                pickup_location, delivery_location, equipment,
                notes, usage_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (tpl.template_id, tpl.name, tpl.customer,
             tpl.broker_shipper, tpl.pickup_location,
             tpl.delivery_location, tpl.equipment,
             tpl.notes, tpl.usage_count,
             tpl.created_at, tpl.updated_at),
        )
    return tpl.to_dict()


def get_lane_template(template_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM lane_templates WHERE template_id=?",
            (template_id,),
        ).fetchone()
    return dict_from_row(row) if row else None


def list_lane_templates() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM lane_templates ORDER BY usage_count DESC, name"
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_lane_template(template_id: str, **fields) -> dict | None:
    existing = get_lane_template(template_id)
    if not existing:
        return None
    allowed = {
        "name", "customer", "broker_shipper", "pickup_location",
        "delivery_location", "equipment", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [template_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE lane_templates SET {set_clause} WHERE template_id=?",
            values,
        )
    return get_lane_template(template_id)


def delete_lane_template(template_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM lane_templates WHERE template_id=?",
            (template_id,),
        )
    return cur.rowcount > 0


def increment_lane_template_usage(template_id: str) -> None:
    from dispatch.models import _utc_now
    with get_connection() as conn:
        conn.execute(
            "UPDATE lane_templates SET usage_count=usage_count+1, updated_at=? WHERE template_id=?",
            (_utc_now(), template_id),
        )


# ── Broker Scorecard ────────────────────────────────────────────────


def get_broker_scorecards() -> list[dict]:
    sql = """\
    SELECT
        l.broker_shipper,
        COUNT(*) AS total_loads,
        SUM(CASE WHEN l.status IN ('completed','archived') THEN 1 ELSE 0 END) AS completed_loads,
        SUM(CASE WHEN l.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_loads,
        COALESCE(SUM(
            CASE WHEN rc.rate_type = 'per_mile' THEN rc.rate_amount * rc.distance_miles
                 ELSE rc.rate_amount END
        ), 0) AS total_revenue,
        CASE WHEN COUNT(rc.confirmation_id) > 0
             THEN ROUND(SUM(
                 CASE WHEN rc.rate_type = 'per_mile' THEN rc.rate_amount * rc.distance_miles
                      ELSE rc.rate_amount END
             ) / COUNT(rc.confirmation_id), 2)
             ELSE 0 END AS avg_rate,
        COUNT(rc.confirmation_id) AS loads_with_rate,
        SUM(CASE WHEN s.payment_status = 'paid' THEN 1 ELSE 0 END) AS paid_count,
        SUM(CASE WHEN s.payment_status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
        SUM(CASE WHEN s.payment_status = 'disputed' THEN 1 ELSE 0 END) AS disputed_count,
        MIN(l.created_at) AS first_load_date,
        MAX(l.created_at) AS last_load_date
    FROM loads l
    LEFT JOIN rate_confirmations rc ON rc.load_id = l.load_id
    LEFT JOIN settlements s ON s.load_id = l.load_id
    WHERE l.broker_shipper != ''
    GROUP BY l.broker_shipper
    ORDER BY total_loads DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        total = d["total_loads"]
        completed = d["completed_loads"]
        paid = d["paid_count"]
        overdue = d["overdue_count"]
        disputed = d["disputed_count"]
        settled = paid + overdue + disputed
        d["completion_rate"] = round(completed / total * 100, 1) if total else 0
        d["payment_reliability"] = round(paid / settled * 100, 1) if settled else 0
        results.append(d)
    return results


def get_broker_loads(broker_shipper: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM loads WHERE broker_shipper=? ORDER BY created_at DESC",
            (broker_shipper,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


# ── Global Search ────────────────────────────────────────────────────

def global_search(query: str, limit: int = 50) -> dict:
    q = f"%{query}%"
    results: dict[str, list[dict]] = {
        "loads": [], "drivers": [], "equipment": [], "settlements": [],
    }
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM loads WHERE "
            "load_id LIKE ? OR customer LIKE ? OR broker_shipper LIKE ? "
            "OR pickup_location LIKE ? OR delivery_location LIKE ? OR driver LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (q, q, q, q, q, q, limit),
        ).fetchall()
        results["loads"] = [dict_from_row(r) for r in rows]

        rows = conn.execute(
            "SELECT * FROM drivers WHERE "
            "driver_id LIKE ? OR name LIKE ? OR phone LIKE ? OR email LIKE ? "
            "ORDER BY name ASC LIMIT ?",
            (q, q, q, q, limit),
        ).fetchall()
        results["drivers"] = [dict_from_row(r) for r in rows]

        rows = conn.execute(
            "SELECT * FROM equipment WHERE "
            "equipment_id LIKE ? OR unit_number LIKE ? OR make LIKE ? "
            "OR model LIKE ? OR vin LIKE ? OR license_plate LIKE ? "
            "ORDER BY unit_number ASC LIMIT ?",
            (q, q, q, q, q, q, limit),
        ).fetchall()
        results["equipment"] = [dict_from_row(r) for r in rows]

        rows = conn.execute(
            "SELECT * FROM settlements WHERE "
            "settlement_id LIKE ? OR invoice_number LIKE ? OR load_id LIKE ? "
            "ORDER BY invoice_date DESC LIMIT ?",
            (q, q, q, limit),
        ).fetchall()
        stl_results = []
        for r in rows:
            d = dict_from_row(r)
            stl_results.append(Settlement(**d).to_dict())
        results["settlements"] = stl_results

    return results


# ── Uninvoiced Loads ────────────────────────────────────────────────

def list_uninvoiced_loads() -> list[dict]:
    sql = (
        "SELECT l.* FROM loads l "
        "LEFT JOIN settlements s ON l.load_id = s.load_id "
        "WHERE s.load_id IS NULL "
        "AND l.status IN ('delivered', 'completed') "
        "ORDER BY l.updated_at DESC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict_from_row(r) for r in rows]


# ── IFTA Trip Legs ─────────────────────────────────────────────────

def create_ifta_trip_leg(leg: IFTATripLeg) -> dict:
    d = leg.to_dict()
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO ifta_trip_legs ({cols}) VALUES ({placeholders})",
            list(d.values()),
        )
    return d


def get_ifta_trip_leg(leg_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ifta_trip_legs WHERE leg_id = ?", (leg_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_ifta_trip_legs(
    date_from: str | None = None,
    date_to: str | None = None,
    jurisdiction: str | None = None,
    vehicle_id: str | None = None,
    load_id: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[str] = []
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    if jurisdiction:
        clauses.append("jurisdiction = ?")
        params.append(jurisdiction)
    if vehicle_id:
        clauses.append("vehicle_id = ?")
        params.append(vehicle_id)
    if load_id:
        clauses.append("load_id = ?")
        params.append(load_id)
    where = " AND ".join(clauses) if clauses else "1=1"
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM ifta_trip_legs WHERE {where} ORDER BY date DESC",
            params,
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_ifta_trip_leg(leg_id: str, updates: dict) -> dict | None:
    existing = get_ifta_trip_leg(leg_id)
    if not existing:
        return None
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [leg_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE ifta_trip_legs SET {sets} WHERE leg_id = ?", vals
        )
    return get_ifta_trip_leg(leg_id)


def delete_ifta_trip_leg(leg_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM ifta_trip_legs WHERE leg_id = ?", (leg_id,)
        )
    return cur.rowcount > 0


# ── IFTA Fuel Purchases ───────────────────────────────────────────

def create_ifta_fuel_purchase(purchase: IFTAFuelPurchase) -> dict:
    d = purchase.to_dict()
    d.pop("price_per_gallon", None)
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO ifta_fuel_purchases ({cols}) VALUES ({placeholders})",
            list(d.values()),
        )
    return purchase.to_dict()


def get_ifta_fuel_purchase(purchase_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ifta_fuel_purchases WHERE purchase_id = ?",
            (purchase_id,),
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    return IFTAFuelPurchase(**d).to_dict()


def list_ifta_fuel_purchases(
    date_from: str | None = None,
    date_to: str | None = None,
    jurisdiction: str | None = None,
    vehicle_id: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[str] = []
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    if jurisdiction:
        clauses.append("jurisdiction = ?")
        params.append(jurisdiction)
    if vehicle_id:
        clauses.append("vehicle_id = ?")
        params.append(vehicle_id)
    where = " AND ".join(clauses) if clauses else "1=1"
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM ifta_fuel_purchases WHERE {where} ORDER BY date DESC",
            params,
        ).fetchall()
    return [IFTAFuelPurchase(**dict_from_row(r)).to_dict() for r in rows]


def delete_ifta_fuel_purchase(purchase_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM ifta_fuel_purchases WHERE purchase_id = ?",
            (purchase_id,),
        )
    return cur.rowcount > 0


def update_ifta_fuel_purchase(purchase_id: str, updates: dict) -> dict | None:
    existing = get_ifta_fuel_purchase(purchase_id)
    if not existing:
        return None
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [purchase_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE ifta_fuel_purchases SET {sets} WHERE purchase_id = ?", vals
        )
    return get_ifta_fuel_purchase(purchase_id)


# ── IFTA Fuel Purchase Evidence ───────────────────────────────────────

def create_ifta_fuel_evidence(ev: IFTAFuelEvidence) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO ifta_fuel_evidence
               (evidence_id, purchase_id, original_filename, file_path,
                file_size, mime_type, checksum, description, uploaded_by,
                capture_time)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (ev.evidence_id, ev.purchase_id, ev.original_filename, ev.file_path,
             ev.file_size, ev.mime_type, ev.checksum, ev.description,
             ev.uploaded_by, ev.capture_time),
        )
    return ev.to_dict()


def get_ifta_fuel_evidence(evidence_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ifta_fuel_evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()
    return dict_from_row(row) if row else None


def list_ifta_fuel_evidence(purchase_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ifta_fuel_evidence WHERE purchase_id = ? ORDER BY capture_time ASC",
            (purchase_id,),
        ).fetchall()
    return [dict_from_row(r) for r in rows]


# ── IFTA Report Approvals ────────────────────────────────────────────


def _deserialize_approval(d: dict) -> dict:
    return deserialize_json_fields(d, "snapshot_json", "recommendation_json")


def create_ifta_report_approval(approval: IFTAReportApproval) -> dict:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO ifta_report_approvals
               (approval_id, year, quarter, vehicle_id, status, snapshot_json,
                recommendation_json, submitted_at, sealed_at, approved_by, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (approval.approval_id, approval.year, approval.quarter, approval.vehicle_id,
             approval.status, json.dumps(approval.snapshot),
             json.dumps(approval.recommendation) if approval.recommendation else None,
             approval.submitted_at, approval.sealed_at, approval.approved_by,
             approval.created_at),
        )
    return get_ifta_report_approval(approval.approval_id)


def get_ifta_report_approval(approval_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ifta_report_approvals WHERE approval_id = ?", (approval_id,)
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    d["snapshot_json"] = json.loads(d["snapshot_json"])
    d["recommendation_json"] = (
        json.loads(d["recommendation_json"]) if d["recommendation_json"] else None
    )
    return d


def get_latest_ifta_report_approval(year: int, quarter: int, vehicle_id: str = "") -> dict | None:
    """Most recently submitted approval for this period, or None. Used to
    refuse a second submission while one is already outstanding, and to
    check whether a period has already been sealed."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM ifta_report_approvals
               WHERE year = ? AND quarter = ? AND vehicle_id = ?
               ORDER BY submitted_at DESC LIMIT 1""",
            (year, quarter, vehicle_id),
        ).fetchone()
    if not row:
        return None
    d = dict_from_row(row)
    d["snapshot_json"] = json.loads(d["snapshot_json"])
    d["recommendation_json"] = (
        json.loads(d["recommendation_json"]) if d["recommendation_json"] else None
    )
    return d


def list_ifta_report_approvals() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM ifta_report_approvals ORDER BY submitted_at DESC"
        ).fetchall()
    results = []
    for row in rows:
        d = dict_from_row(row)
        d["snapshot_json"] = json.loads(d["snapshot_json"])
        d["recommendation_json"] = (
            json.loads(d["recommendation_json"]) if d["recommendation_json"] else None
        )
        results.append(d)
    return results


def update_ifta_report_approval(approval_id: str, updates: dict) -> dict | None:
    existing = get_ifta_report_approval(approval_id)
    if not existing:
        return None
    serialized = dict(updates)
    if "snapshot_json" in serialized and not isinstance(serialized["snapshot_json"], str):
        serialized["snapshot_json"] = json.dumps(serialized["snapshot_json"])
    if "recommendation_json" in serialized and not isinstance(serialized["recommendation_json"], str):
        serialized["recommendation_json"] = json.dumps(serialized["recommendation_json"])
    sets = ", ".join(f"{k} = ?" for k in serialized)
    vals = list(serialized.values()) + [approval_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE ifta_report_approvals SET {sets} WHERE approval_id = ?", vals
        )
    return get_ifta_report_approval(approval_id)


# ── Broker Contacts ──────────────────────────────────────────────────


def create_broker_contact(broker: BrokerContact) -> dict:
    d = broker.to_dict()
    cols = ", ".join(d.keys())
    placeholders = ", ".join("?" for _ in d)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO broker_contacts ({cols}) VALUES ({placeholders})",
            list(d.values()),
        )
    return d


def get_broker_contact(broker_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM broker_contacts WHERE broker_id = ?", (broker_id,)
        ).fetchone()
    return dict_from_row(row) if row else None


def list_broker_contacts(
    status: str | None = None,
    search: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    params: list[str] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if search:
        clauses.append(
            "(company_name LIKE ? OR contact_name LIKE ? OR mc_number LIKE ? "
            "OR phone LIKE ? OR email LIKE ?)"
        )
        q = f"%{search}%"
        params.extend([q, q, q, q, q])
    where = " AND ".join(clauses) if clauses else "1=1"
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM broker_contacts WHERE {where} ORDER BY company_name",
            params,
        ).fetchall()
    return [dict_from_row(r) for r in rows]


def update_broker_contact(broker_id: str, updates: dict) -> dict | None:
    existing = get_broker_contact(broker_id)
    if not existing:
        return None
    allowed = {
        "company_name", "contact_name", "phone", "email",
        "mc_number", "dot_number", "address", "payment_terms",
        "notes", "status", "updated_at",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed}
    if not filtered:
        return existing
    from dispatch.models import _utc_now
    filtered["updated_at"] = _utc_now()
    sets = ", ".join(f"{k} = ?" for k in filtered)
    vals = list(filtered.values()) + [broker_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE broker_contacts SET {sets} WHERE broker_id = ?", vals
        )
    return get_broker_contact(broker_id)


def delete_broker_contact(broker_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM broker_contacts WHERE broker_id = ?", (broker_id,)
        )
    return cur.rowcount > 0


def find_broker_by_name(company_name: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM broker_contacts WHERE company_name = ?",
            (company_name,),
        ).fetchone()
    return dict_from_row(row) if row else None


# ── Load Profitability ───────────────────────────────────────────────


def get_load_profitability_data(
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
) -> list[dict]:
    sql = """\
    SELECT
        l.load_id,
        l.customer,
        l.broker_shipper,
        l.pickup_location,
        l.delivery_location,
        l.status,
        l.created_at,
        COALESCE(
            CASE WHEN rc.rate_type = 'per_mile'
                 THEN rc.rate_amount * rc.distance_miles
                 ELSE rc.rate_amount END,
            0
        ) AS revenue,
        rc.distance_miles,
        COALESCE(exp_total.total_expenses, 0) AS total_expenses
    FROM loads l
    LEFT JOIN rate_confirmations rc ON rc.load_id = l.load_id
    LEFT JOIN (
        SELECT load_id, SUM(amount) AS total_expenses
        FROM expenses GROUP BY load_id
    ) exp_total ON exp_total.load_id = l.load_id
    WHERE 1=1
    """
    params: list = []
    if date_from:
        sql += " AND l.created_at >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND l.created_at <= ?"
        params.append(date_to)
    if status:
        sql += " AND l.status = ?"
        params.append(status)
    sql += " ORDER BY l.created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        revenue = d["revenue"]
        expenses = d["total_expenses"]
        profit = revenue - expenses
        margin = (profit / revenue * 100) if revenue > 0 else 0.0
        rpm = (revenue / d["distance_miles"]) if d.get("distance_miles") and d["distance_miles"] > 0 else 0.0
        d["profit"] = round(profit, 2)
        d["margin_pct"] = round(margin, 1)
        d["revenue_per_mile"] = round(rpm, 2)
        d["revenue"] = round(revenue, 2)
        d["total_expenses"] = round(expenses, 2)
        results.append(d)
    return results


# ── Driver Pay ──────────────────────────────────────────────────────


def create_driver_pay(pay) -> dict:
    d = pay.to_dict()
    cols = [
        "pay_id", "driver_id", "load_id", "pay_type", "description",
        "amount", "rate", "miles", "hours", "percentage",
        "pay_period", "status", "paid_date", "notes", "created_at",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO driver_pay ({col_str}) VALUES ({placeholders})",
            [d[c] for c in cols],
        )
    return d


def get_driver_pay(pay_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM driver_pay WHERE pay_id = ?", (pay_id,)
        ).fetchone()
    return dict(row) if row else None


def list_driver_pay(
    driver_id: str | None = None,
    load_id: str | None = None,
    status: str | None = None,
    pay_period: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM driver_pay WHERE 1=1"
    params: list = []
    if driver_id:
        sql += " AND driver_id = ?"
        params.append(driver_id)
    if load_id:
        sql += " AND load_id = ?"
        params.append(load_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if pay_period:
        sql += " AND pay_period = ?"
        params.append(pay_period)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_driver_pay(pay_id: str, **fields) -> dict | None:
    existing = get_driver_pay(pay_id)
    if not existing:
        return None
    allowed = {
        "pay_type", "description", "amount", "rate", "miles", "hours",
        "percentage", "pay_period", "status", "paid_date", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [pay_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE driver_pay SET {set_clause} WHERE pay_id = ?", vals
        )
    return get_driver_pay(pay_id)


def delete_driver_pay(pay_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM driver_pay WHERE pay_id = ?", (pay_id,))
    return cur.rowcount > 0


def get_driver_pay_summary(
    driver_id: str,
    pay_period: str | None = None,
) -> dict:
    sql = """\
    SELECT
        COUNT(*) AS entry_count,
        COALESCE(SUM(CASE WHEN pay_type != 'deduction' THEN amount ELSE 0 END), 0) AS gross_pay,
        COALESCE(SUM(CASE WHEN pay_type = 'deduction' THEN amount ELSE 0 END), 0) AS deductions,
        COALESCE(SUM(CASE WHEN status = 'paid' AND pay_type != 'deduction' THEN amount ELSE 0 END), 0) AS paid_amount,
        COALESCE(SUM(CASE WHEN status = 'pending' AND pay_type != 'deduction' THEN amount ELSE 0 END), 0) AS pending_amount
    FROM driver_pay WHERE driver_id = ?
    """
    params: list = [driver_id]
    if pay_period:
        sql += " AND pay_period = ?"
        params.append(pay_period)
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
    d = dict(row)
    d["net_pay"] = round(d["gross_pay"] - d["deductions"], 2)
    d["gross_pay"] = round(d["gross_pay"], 2)
    d["deductions"] = round(d["deductions"], 2)
    d["paid_amount"] = round(d["paid_amount"], 2)
    d["pending_amount"] = round(d["pending_amount"], 2)
    return d


# ── Maintenance Schedules ───────────────────────────────────────────


def create_maintenance_schedule(sched) -> dict:
    d = sched.to_dict()
    cols = [
        "schedule_id", "equipment_id", "service_type", "description",
        "interval_miles", "interval_days", "last_service_date",
        "last_service_miles", "next_due_date", "next_due_miles",
        "status", "cost_estimate", "vendor", "notes",
        "created_at", "updated_at",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO maintenance_schedules ({col_str}) VALUES ({placeholders})",
            [d[c] for c in cols],
        )
    return d


def get_maintenance_schedule(schedule_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM maintenance_schedules WHERE schedule_id = ?",
            (schedule_id,),
        ).fetchone()
    return dict(row) if row else None


def list_maintenance_schedules(
    equipment_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM maintenance_schedules WHERE 1=1"
    params: list = []
    if equipment_id:
        sql += " AND equipment_id = ?"
        params.append(equipment_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY next_due_date ASC, created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_maintenance_schedule(schedule_id: str, **fields) -> dict | None:
    existing = get_maintenance_schedule(schedule_id)
    if not existing:
        return None
    allowed = {
        "service_type", "description", "interval_miles", "interval_days",
        "last_service_date", "last_service_miles", "next_due_date",
        "next_due_miles", "status", "cost_estimate", "vendor", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [schedule_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE maintenance_schedules SET {set_clause} WHERE schedule_id = ?",
            vals,
        )
    return get_maintenance_schedule(schedule_id)


def delete_maintenance_schedule(schedule_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM maintenance_schedules WHERE schedule_id = ?",
            (schedule_id,),
        )
    return cur.rowcount > 0


def get_upcoming_maintenance(days_ahead: int = 7) -> list[dict]:
    from dispatch.models import _utc_now
    today = _utc_now()[:10]
    from datetime import datetime, timedelta
    cutoff = (datetime.fromisoformat(today) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    sql = """\
    SELECT ms.*, e.unit_number, e.equipment_type, e.make, e.model
    FROM maintenance_schedules ms
    JOIN equipment e ON e.equipment_id = ms.equipment_id
    WHERE ms.status IN ('scheduled', 'due', 'overdue')
      AND ms.next_due_date != ''
      AND ms.next_due_date <= ?
    ORDER BY ms.next_due_date ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def get_overdue_maintenance() -> list[dict]:
    from dispatch.models import _utc_now
    today = _utc_now()[:10]
    sql = """\
    SELECT ms.*, e.unit_number, e.equipment_type, e.make, e.model
    FROM maintenance_schedules ms
    JOIN equipment e ON e.equipment_id = ms.equipment_id
    WHERE ms.status IN ('scheduled', 'due')
      AND ms.next_due_date != ''
      AND ms.next_due_date < ?
    ORDER BY ms.next_due_date ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (today,)).fetchall()
    return [dict(r) for r in rows]


# ── Compliance Documents ──────────────────────────────────────────


def create_compliance_document(doc) -> dict:
    d = doc.to_dict()
    cols = [
        "doc_id", "entity_type", "entity_id", "doc_type", "title",
        "issuing_authority", "doc_number", "issue_date", "expiry_date",
        "alert_days", "status", "notes", "created_at", "updated_at",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_str = ", ".join(cols)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO compliance_documents ({col_str}) VALUES ({placeholders})",
            [d[c] for c in cols],
        )
    return d


def get_compliance_document(doc_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM compliance_documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    _enrich_compliance_doc(d)
    return d


def list_compliance_documents(
    entity_type: str | None = None,
    entity_id: str | None = None,
    doc_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM compliance_documents WHERE 1=1"
    params: list = []
    if entity_type:
        sql += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id = ?"
        params.append(entity_id)
    if doc_type:
        sql += " AND doc_type = ?"
        params.append(doc_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY expiry_date ASC, created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        _enrich_compliance_doc(d)
        results.append(d)
    return results


def update_compliance_document(doc_id: str, **fields) -> dict | None:
    existing = get_compliance_document(doc_id)
    if not existing:
        return None
    allowed = {
        "entity_type", "entity_id", "doc_type", "title",
        "issuing_authority", "doc_number", "issue_date", "expiry_date",
        "alert_days", "status", "notes",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return existing
    from dispatch.models import _utc_now
    updates["updated_at"] = _utc_now()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [doc_id]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE compliance_documents SET {set_clause} WHERE doc_id = ?",
            vals,
        )
    return get_compliance_document(doc_id)


def delete_compliance_document(doc_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM compliance_documents WHERE doc_id = ?",
            (doc_id,),
        )
    return cur.rowcount > 0


def _enrich_compliance_doc(d: dict) -> None:
    from dispatch.models import _utc_now
    from datetime import datetime
    expiry = d.get("expiry_date", "")
    today = _utc_now()[:10]
    if expiry:
        d["is_expired"] = expiry < today
        try:
            delta = (datetime.fromisoformat(expiry) - datetime.fromisoformat(today)).days
            d["days_until_expiry"] = delta
            d["needs_alert"] = delta <= d.get("alert_days", 30)
        except ValueError:
            d["days_until_expiry"] = None
            d["needs_alert"] = False
    else:
        d["is_expired"] = False
        d["days_until_expiry"] = None
        d["needs_alert"] = False


def get_expiring_compliance_documents(days_ahead: int = 30) -> list[dict]:
    from dispatch.models import _utc_now
    from datetime import datetime, timedelta
    today = _utc_now()[:10]
    cutoff = (datetime.fromisoformat(today) + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    sql = """\
    SELECT * FROM compliance_documents
    WHERE status IN ('active', 'expiring_soon')
      AND expiry_date != ''
      AND expiry_date <= ?
    ORDER BY expiry_date ASC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        _enrich_compliance_doc(d)
        results.append(d)
    return results
