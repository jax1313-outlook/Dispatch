"""Dispatch Spine SQLite schema.

Reuses dispatch.db's connection/migration machinery -- same file, same
WAL-mode connection, same PRAGMA foreign_keys=ON -- rather than opening
a second connection or resolving its own file path. See
DISPATCH_STAGE4_SPINE_SCHEMA_DESIGN_v1.md Section 1.

Table creation order matters for the REFERENCES clauses below:
work_items -> events -> portal_cards -> audit_events -> approval_events
(references audit_events) -> conflict_events.
"""

from __future__ import annotations

import sqlite3

_SPINE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS work_items (
    work_item_id       TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    source_type        TEXT NOT NULL DEFAULT '',
    source_id          TEXT NOT NULL DEFAULT '',
    current_state      TEXT NOT NULL DEFAULT 'CREATED',
    priority           TEXT NOT NULL DEFAULT '',
    consequence_level  INTEGER NOT NULL DEFAULT 0,
    assigned_function  TEXT NOT NULL DEFAULT '',
    required_action    TEXT NOT NULL DEFAULT '',
    source_confidence  TEXT NOT NULL DEFAULT '',
    due_date           TEXT,
    related_files      TEXT NOT NULL DEFAULT '[]',
    source_refs        TEXT NOT NULL DEFAULT '[]',
    validation_status  TEXT NOT NULL DEFAULT '',
    scoring_status     TEXT NOT NULL DEFAULT '',
    cognitive_status   TEXT NOT NULL DEFAULT '',
    portal_card_id     TEXT,
    final_disposition  TEXT
);

CREATE INDEX IF NOT EXISTS idx_spine_work_items_state ON work_items(current_state);
CREATE INDEX IF NOT EXISTS idx_spine_work_items_source ON work_items(source_type, source_id);

CREATE TABLE IF NOT EXISTS events (
    event_id       TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    work_item_id   TEXT NOT NULL REFERENCES work_items(work_item_id),
    event_type     TEXT NOT NULL DEFAULT '',
    actor_type     TEXT NOT NULL DEFAULT '',
    actor_id       TEXT NOT NULL DEFAULT '',
    previous_state TEXT,
    new_state      TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    source_refs    TEXT NOT NULL DEFAULT '[]',
    requires_audit INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_spine_events_work_item ON events(work_item_id);

CREATE TABLE IF NOT EXISTS portal_cards (
    card_id          TEXT PRIMARY KEY,
    work_item_id     TEXT NOT NULL REFERENCES work_items(work_item_id),
    created_at       TEXT NOT NULL,
    card_level       INTEGER NOT NULL DEFAULT 0,
    card_type        TEXT NOT NULL DEFAULT '',
    title            TEXT NOT NULL DEFAULT '',
    summary          TEXT NOT NULL DEFAULT '',
    source_refs      TEXT NOT NULL DEFAULT '[]',
    recommendation   TEXT NOT NULL DEFAULT '',
    decision_needed  TEXT,
    allowed_actions  TEXT NOT NULL DEFAULT '[]',
    required_closing TEXT NOT NULL DEFAULT 'This is a recommendation only. No action is authorized. Mike decides.'
);

CREATE INDEX IF NOT EXISTS idx_spine_portal_cards_work_item ON portal_cards(work_item_id);
CREATE INDEX IF NOT EXISTS idx_spine_portal_cards_level ON portal_cards(card_level);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id       TEXT PRIMARY KEY,
    timestamp      TEXT NOT NULL,
    work_item_id   TEXT REFERENCES work_items(work_item_id),
    event_id       TEXT REFERENCES events(event_id),
    actor_type     TEXT NOT NULL DEFAULT '',
    actor_id       TEXT NOT NULL DEFAULT '',
    action         TEXT NOT NULL DEFAULT '',
    previous_state TEXT,
    new_state      TEXT,
    source_refs    TEXT NOT NULL DEFAULT '[]',
    hash           TEXT,
    notes          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_spine_audit_events_work_item ON audit_events(work_item_id);

CREATE TABLE IF NOT EXISTS approval_events (
    approval_event_id     TEXT PRIMARY KEY,
    timestamp             TEXT NOT NULL,
    session_id            TEXT,
    user_id               TEXT,
    role                  TEXT,
    work_item_id          TEXT NOT NULL REFERENCES work_items(work_item_id),
    portal_card_id        TEXT REFERENCES portal_cards(card_id),
    object_type           TEXT NOT NULL DEFAULT '',
    object_id             TEXT NOT NULL DEFAULT '',
    object_version        INTEGER NOT NULL DEFAULT 1,
    action                TEXT NOT NULL DEFAULT '',
    previous_state        TEXT,
    new_state             TEXT NOT NULL DEFAULT '',
    comments              TEXT NOT NULL DEFAULT '',
    authentication_context TEXT,
    audit_id              TEXT NOT NULL REFERENCES audit_events(audit_id)
);

CREATE INDEX IF NOT EXISTS idx_spine_approval_events_work_item ON approval_events(work_item_id);

CREATE TABLE IF NOT EXISTS conflict_events (
    conflict_id           TEXT PRIMARY KEY,
    timestamp             TEXT NOT NULL,
    work_item_id          TEXT NOT NULL REFERENCES work_items(work_item_id),
    conflict_type         TEXT NOT NULL DEFAULT '',
    affected_layer        TEXT NOT NULL DEFAULT '',
    affected_function     TEXT NOT NULL DEFAULT '',
    trigger               TEXT NOT NULL DEFAULT '',
    details               TEXT NOT NULL DEFAULT '',
    options               TEXT NOT NULL DEFAULT '[]',
    recommended_path      TEXT NOT NULL DEFAULT '',
    human_decision_needed INTEGER NOT NULL DEFAULT 1,
    current_state         TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_spine_conflict_events_work_item ON conflict_events(work_item_id);
"""


def init_spine_schema(conn: sqlite3.Connection) -> None:
    """Idempotent -- safe to call on every connection open, matching
    dispatch.db._init_db()'s own CREATE-TABLE-IF-NOT-EXISTS pattern.
    Called from dispatch.db._init_db() so Spine tables live in the same
    file, same connection, same migration pass as every other table.
    """
    conn.executescript(_SPINE_SCHEMA)
