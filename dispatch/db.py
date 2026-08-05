"""SQLite database setup and connection management.

Single dispatch.db file; schema created on first connection.
Uses stdlib sqlite3 — no external dependency.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS loads (
    load_id         TEXT PRIMARY KEY,
    customer        TEXT NOT NULL DEFAULT '',
    broker_shipper  TEXT NOT NULL DEFAULT '',
    pickup_location TEXT NOT NULL DEFAULT '',
    delivery_location TEXT NOT NULL DEFAULT '',
    pickup_datetime TEXT NOT NULL DEFAULT '',
    delivery_datetime TEXT NOT NULL DEFAULT '',
    equipment       TEXT NOT NULL DEFAULT '',
    driver          TEXT NOT NULL DEFAULT '',
    driver_id       TEXT NOT NULL DEFAULT '',
    equipment_id    TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'created',
    source          TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_loads_source ON loads(source);

CREATE TABLE IF NOT EXISTS visibility (
    load_id                TEXT PRIMARY KEY REFERENCES loads(load_id),
    current_status         TEXT NOT NULL DEFAULT 'created',
    last_milestone         TEXT,
    next_expected_milestone TEXT,
    exception_flag         INTEGER NOT NULL DEFAULT 0,
    customer_note          TEXT NOT NULL DEFAULT '',
    internal_note          TEXT NOT NULL DEFAULT '',
    updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS milestones (
    milestone_id      TEXT PRIMARY KEY,
    load_id           TEXT NOT NULL REFERENCES loads(load_id),
    event_type        TEXT NOT NULL,
    event_time        TEXT NOT NULL,
    location          TEXT NOT NULL DEFAULT '',
    source            TEXT NOT NULL DEFAULT 'dispatcher',
    note              TEXT NOT NULL DEFAULT '',
    entered_by        TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id          TEXT PRIMARY KEY,
    load_id              TEXT NOT NULL REFERENCES loads(load_id),
    related_milestone_id TEXT,
    evidence_type        TEXT NOT NULL DEFAULT 'document',
    file_path            TEXT,
    original_filename    TEXT NOT NULL DEFAULT '',
    file_size            INTEGER NOT NULL DEFAULT 0,
    mime_type            TEXT NOT NULL DEFAULT '',
    capture_time         TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    uploaded_by          TEXT NOT NULL DEFAULT '',
    checksum             TEXT
);

CREATE TABLE IF NOT EXISTS exceptions (
    exception_id         TEXT PRIMARY KEY,
    load_id              TEXT NOT NULL REFERENCES loads(load_id),
    related_milestone_id TEXT,
    exception_type       TEXT NOT NULL DEFAULT 'other',
    severity             TEXT NOT NULL DEFAULT 'medium',
    description          TEXT NOT NULL DEFAULT '',
    first_reported       TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'open',
    resolution_note      TEXT NOT NULL DEFAULT '',
    resolved_at          TEXT
);

CREATE TABLE IF NOT EXISTS pod_packages (
    pod_id        TEXT PRIMARY KEY,
    load_id       TEXT NOT NULL REFERENCES loads(load_id),
    evidence_ids  TEXT NOT NULL DEFAULT '[]',
    generated_at  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'draft',
    recipient     TEXT NOT NULL DEFAULT '',
    file_path     TEXT,
    notes         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS retention (
    archive_id        TEXT PRIMARY KEY,
    load_id           TEXT NOT NULL REFERENCES loads(load_id),
    final_status      TEXT NOT NULL DEFAULT 'completed',
    pod_package_id    TEXT,
    evidence_index    TEXT NOT NULL DEFAULT '[]',
    financial_summary TEXT NOT NULL DEFAULT '{}',
    archive_location  TEXT NOT NULL DEFAULT '',
    retention_status  TEXT NOT NULL DEFAULT 'active',
    archived_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_confirmations (
    confirmation_id TEXT PRIMARY KEY,
    load_id         TEXT NOT NULL REFERENCES loads(load_id),
    rate_amount     REAL NOT NULL DEFAULT 0,
    rate_type       TEXT NOT NULL DEFAULT 'flat',
    distance_miles  REAL NOT NULL DEFAULT 0,
    confirmed_by    TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    confirmed_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    expense_id          TEXT PRIMARY KEY,
    load_id             TEXT NOT NULL REFERENCES loads(load_id),
    category            TEXT NOT NULL DEFAULT 'other',
    description         TEXT NOT NULL DEFAULT '',
    amount              REAL NOT NULL DEFAULT 0,
    incurred_at         TEXT NOT NULL,
    receipt_evidence_id TEXT,
    notes               TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settlements (
    settlement_id   TEXT PRIMARY KEY,
    load_id         TEXT NOT NULL UNIQUE REFERENCES loads(load_id),
    invoice_number  TEXT NOT NULL DEFAULT '',
    invoice_amount  REAL NOT NULL DEFAULT 0,
    invoice_date    TEXT NOT NULL,
    due_date        TEXT NOT NULL DEFAULT '',
    payment_status  TEXT NOT NULL DEFAULT 'draft',
    payment_amount  REAL NOT NULL DEFAULT 0,
    payment_date    TEXT NOT NULL DEFAULT '',
    payment_method  TEXT NOT NULL DEFAULT '',
    factoring_fee   REAL NOT NULL DEFAULT 0,
    notes           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL DEFAULT '',
    license_number  TEXT NOT NULL DEFAULT '',
    license_class   TEXT NOT NULL DEFAULT '',
    phone           TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    hire_date       TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id    TEXT PRIMARY KEY,
    unit_number     TEXT NOT NULL DEFAULT '',
    equipment_type  TEXT NOT NULL DEFAULT 'dry_van',
    make            TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
    year            TEXT NOT NULL DEFAULT '',
    vin             TEXT NOT NULL DEFAULT '',
    license_plate   TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activities (
    activity_id     TEXT PRIMARY KEY,
    load_id         TEXT NOT NULL REFERENCES loads(load_id),
    activity_type   TEXT NOT NULL DEFAULT 'comment',
    message         TEXT NOT NULL DEFAULT '',
    author          TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT 'user',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_milestones_load ON milestones(load_id);
CREATE INDEX IF NOT EXISTS idx_evidence_load ON evidence(load_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_load ON exceptions(load_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_status ON exceptions(status);
CREATE INDEX IF NOT EXISTS idx_loads_status ON loads(status);
CREATE INDEX IF NOT EXISTS idx_rate_conf_load ON rate_confirmations(load_id);
CREATE INDEX IF NOT EXISTS idx_expenses_load ON expenses(load_id);
CREATE INDEX IF NOT EXISTS idx_settlements_status ON settlements(payment_status);
CREATE INDEX IF NOT EXISTS idx_drivers_status ON drivers(status);
CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status);
CREATE INDEX IF NOT EXISTS idx_equipment_type ON equipment(equipment_type);
CREATE INDEX IF NOT EXISTS idx_activities_load ON activities(load_id);

CREATE TABLE IF NOT EXISTS detention_events (
    detention_id    TEXT PRIMARY KEY,
    load_id         TEXT NOT NULL REFERENCES loads(load_id),
    location_type   TEXT NOT NULL DEFAULT 'pickup',
    started_at      TEXT NOT NULL,
    ended_at        TEXT NOT NULL DEFAULT '',
    free_hours      REAL NOT NULL DEFAULT 2.0,
    hourly_rate     REAL NOT NULL DEFAULT 75.0,
    status          TEXT NOT NULL DEFAULT 'active',
    notes           TEXT NOT NULL DEFAULT '',
    expense_id      TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_detention_load ON detention_events(load_id);
CREATE INDEX IF NOT EXISTS idx_detention_status ON detention_events(status);

CREATE TABLE IF NOT EXISTS lane_templates (
    template_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    customer        TEXT NOT NULL DEFAULT '',
    broker_shipper  TEXT NOT NULL DEFAULT '',
    pickup_location TEXT NOT NULL DEFAULT '',
    delivery_location TEXT NOT NULL DEFAULT '',
    equipment       TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    usage_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ifta_trip_legs (
    leg_id          TEXT PRIMARY KEY,
    load_id         TEXT NOT NULL DEFAULT '',
    jurisdiction    TEXT NOT NULL,
    miles           REAL NOT NULL DEFAULT 0,
    date            TEXT NOT NULL,
    vehicle_id      TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ifta_legs_date ON ifta_trip_legs(date);
CREATE INDEX IF NOT EXISTS idx_ifta_legs_jurisdiction ON ifta_trip_legs(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_ifta_legs_vehicle ON ifta_trip_legs(vehicle_id);

CREATE TABLE IF NOT EXISTS ifta_fuel_purchases (
    purchase_id     TEXT PRIMARY KEY,
    jurisdiction    TEXT NOT NULL,
    date            TEXT NOT NULL,
    gallons         REAL NOT NULL DEFAULT 0,
    amount          REAL NOT NULL DEFAULT 0,
    vehicle_id      TEXT NOT NULL DEFAULT '',
    vendor          TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    evidence_id     TEXT
);

CREATE INDEX IF NOT EXISTS idx_ifta_fuel_date ON ifta_fuel_purchases(date);
CREATE INDEX IF NOT EXISTS idx_ifta_fuel_jurisdiction ON ifta_fuel_purchases(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_ifta_fuel_vehicle ON ifta_fuel_purchases(vehicle_id);

CREATE TABLE IF NOT EXISTS ifta_fuel_evidence (
    evidence_id       TEXT PRIMARY KEY,
    purchase_id       TEXT NOT NULL REFERENCES ifta_fuel_purchases(purchase_id),
    original_filename TEXT NOT NULL DEFAULT '',
    file_path         TEXT,
    file_size         INTEGER NOT NULL DEFAULT 0,
    mime_type         TEXT NOT NULL DEFAULT '',
    checksum          TEXT,
    description       TEXT NOT NULL DEFAULT '',
    uploaded_by       TEXT NOT NULL DEFAULT '',
    capture_time      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ifta_fuel_evidence_purchase ON ifta_fuel_evidence(purchase_id);

CREATE TABLE IF NOT EXISTS ifta_report_approvals (
    approval_id         TEXT PRIMARY KEY,
    year                INTEGER NOT NULL,
    quarter             INTEGER NOT NULL,
    vehicle_id          TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'draft',
    snapshot_json       TEXT NOT NULL,
    recommendation_json TEXT,
    submitted_at        TEXT NOT NULL,
    sealed_at           TEXT,
    approved_by         TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ifta_approvals_period ON ifta_report_approvals(year, quarter, vehicle_id);

CREATE TABLE IF NOT EXISTS ifta_exceptions (
    exception_id        TEXT PRIMARY KEY,
    approval_id         TEXT NOT NULL REFERENCES ifta_report_approvals(approval_id),
    exception_type      TEXT NOT NULL,
    detail              TEXT NOT NULL DEFAULT '',
    related_record_ids  TEXT NOT NULL DEFAULT '[]',
    detected_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ifta_exceptions_approval ON ifta_exceptions(approval_id);

CREATE TABLE IF NOT EXISTS broker_contacts (
    broker_id       TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    contact_name    TEXT NOT NULL DEFAULT '',
    phone           TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    mc_number       TEXT NOT NULL DEFAULT '',
    dot_number      TEXT NOT NULL DEFAULT '',
    address         TEXT NOT NULL DEFAULT '',
    payment_terms   TEXT NOT NULL DEFAULT '',
    notes           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_broker_contacts_company ON broker_contacts(company_name);
CREATE INDEX IF NOT EXISTS idx_broker_contacts_mc ON broker_contacts(mc_number);
CREATE INDEX IF NOT EXISTS idx_broker_contacts_status ON broker_contacts(status);

CREATE TABLE IF NOT EXISTS driver_pay (
    pay_id      TEXT PRIMARY KEY,
    driver_id   TEXT NOT NULL,
    load_id     TEXT NOT NULL DEFAULT '',
    pay_type    TEXT NOT NULL DEFAULT 'per_mile',
    description TEXT NOT NULL DEFAULT '',
    amount      REAL NOT NULL DEFAULT 0,
    rate        REAL NOT NULL DEFAULT 0,
    miles       REAL NOT NULL DEFAULT 0,
    hours       REAL NOT NULL DEFAULT 0,
    percentage  REAL NOT NULL DEFAULT 0,
    pay_period  TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    paid_date   TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_driver_pay_driver ON driver_pay(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_pay_load ON driver_pay(load_id);
CREATE INDEX IF NOT EXISTS idx_driver_pay_status ON driver_pay(status);
CREATE INDEX IF NOT EXISTS idx_driver_pay_period ON driver_pay(pay_period);

CREATE TABLE IF NOT EXISTS maintenance_schedules (
    schedule_id       TEXT PRIMARY KEY,
    equipment_id      TEXT NOT NULL,
    service_type      TEXT NOT NULL DEFAULT 'other',
    description       TEXT NOT NULL DEFAULT '',
    interval_miles    REAL NOT NULL DEFAULT 0,
    interval_days     INTEGER NOT NULL DEFAULT 0,
    last_service_date TEXT NOT NULL DEFAULT '',
    last_service_miles REAL NOT NULL DEFAULT 0,
    next_due_date     TEXT NOT NULL DEFAULT '',
    next_due_miles    REAL NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'scheduled',
    cost_estimate     REAL NOT NULL DEFAULT 0,
    vendor            TEXT NOT NULL DEFAULT '',
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maint_equipment ON maintenance_schedules(equipment_id);
CREATE INDEX IF NOT EXISTS idx_maint_status ON maintenance_schedules(status);
CREATE INDEX IF NOT EXISTS idx_maint_due_date ON maintenance_schedules(next_due_date);

CREATE TABLE IF NOT EXISTS compliance_documents (
    doc_id            TEXT PRIMARY KEY,
    entity_type       TEXT NOT NULL DEFAULT 'company',
    entity_id         TEXT NOT NULL DEFAULT '',
    doc_type          TEXT NOT NULL DEFAULT 'other',
    title             TEXT NOT NULL DEFAULT '',
    issuing_authority TEXT NOT NULL DEFAULT '',
    doc_number        TEXT NOT NULL DEFAULT '',
    issue_date        TEXT NOT NULL DEFAULT '',
    expiry_date       TEXT NOT NULL DEFAULT '',
    alert_days        INTEGER NOT NULL DEFAULT 30,
    status            TEXT NOT NULL DEFAULT 'active',
    notes             TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comp_entity ON compliance_documents(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_comp_status ON compliance_documents(status);
CREATE INDEX IF NOT EXISTS idx_comp_expiry ON compliance_documents(expiry_date);
"""


def _default_db_path() -> Path:
    portal_data = os.environ.get("PORTAL_DATA_DIR")
    if portal_data:
        base = Path(portal_data)
    else:
        ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
        if ops_root:
            base = Path(ops_root) / "Current Workspace" / "PortalData"
        else:
            base = Path(__file__).resolve().parent.parent / "portal" / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "dispatch.db"


_db_path_override: Path | None = None


def set_db_path(path: Path | None) -> None:
    global _db_path_override
    _db_path_override = path


def get_db_path() -> Path:
    if _db_path_override is not None:
        return _db_path_override
    return _default_db_path()


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    _apply_migrations(conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Idempotent ALTER TABLEs for columns added to tables that may
    already exist from before the column was introduced. `CREATE TABLE
    IF NOT EXISTS` in `_SCHEMA` above is a no-op against an existing
    table, so a new column on an existing table needs its own statement
    here -- guarded so re-running it against a database that already has
    the column is a harmless no-op.
    """
    try:
        conn.execute("ALTER TABLE ifta_fuel_purchases ADD COLUMN evidence_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE ifta_fuel_purchases ADD COLUMN extraction_confidence REAL")
    except sqlite3.OperationalError:
        pass


@contextmanager
def get_connection():
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_db(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def dict_from_row(row: sqlite3.Row) -> dict:
    return dict(row)


def deserialize_json_fields(d: dict, *fields: str) -> dict:
    for f in fields:
        if f in d and isinstance(d[f], str):
            d[f] = json.loads(d[f])
    return d
