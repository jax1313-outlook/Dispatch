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
    status          TEXT NOT NULL DEFAULT 'created',
    notes           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

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
"""


def _default_db_path() -> Path:
    portal_data = os.environ.get("PORTAL_DATA_DIR")
    if portal_data:
        base = Path(portal_data)
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
