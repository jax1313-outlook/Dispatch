"""Dispatch Security Foundation SQLite schema.

Reuses dispatch.db's connection/migration machinery -- same file, same
WAL-mode connection, same PRAGMA foreign_keys=ON -- rather than opening
a second connection, following the exact pattern dispatch/spine/db.py
established in Stage 4. See DISPATCH_STAGE7_SECURITY_FOUNDATION_DESIGN_v1.md.
"""

from __future__ import annotations

import sqlite3

_SECURITY_SCHEMA = """\
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    role           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active',
    pin_record_id  TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    last_login_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_security_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_security_users_status ON users(status);

CREATE TABLE IF NOT EXISTS pin_records (
    pin_record_id      TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL REFERENCES users(user_id),
    pin_hash           TEXT NOT NULL,
    salt               TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active',
    reset_required     INTEGER NOT NULL DEFAULT 0,
    failed_attempt_count INTEGER NOT NULL DEFAULT 0,
    locked_until       TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_pin_records_user ON pin_records(user_id);

CREATE TABLE IF NOT EXISTS sessions (
    session_id            TEXT PRIMARY KEY,
    user_id                TEXT NOT NULL REFERENCES users(user_id),
    role                   TEXT NOT NULL,
    started_at             TEXT NOT NULL,
    last_active_at         TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'active',
    authentication_method  TEXT NOT NULL DEFAULT 'DISPATCH_PIN'
);

CREATE INDEX IF NOT EXISTS idx_security_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_security_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS security_events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    user_id     TEXT,
    timestamp   TEXT NOT NULL,
    details     TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_security_events_user ON security_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
"""


def init_security_schema(conn: sqlite3.Connection) -> None:
    """Idempotent -- safe to call on every connection open, matching
    dispatch.db._init_db()'s own CREATE-TABLE-IF-NOT-EXISTS pattern.
    Called from dispatch.db._init_db() so Security tables live in the
    same file, same connection, same migration pass as every other
    table (Spine included).
    """
    conn.executescript(_SECURITY_SCHEMA)
