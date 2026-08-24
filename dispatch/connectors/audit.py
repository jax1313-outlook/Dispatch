"""The connector audit trail — one row for every attempt, including the refusals.

Section 6.8 requires "audit records for every connector attempt". Every, not
every successful one: the attempts that never left the building are the ones
that answer the question an operator actually asks, which is not "did the
mapping provider respond" but "why is there no mileage on this load". An empty
audit table beside a blank field is indistinguishable from a provider that
answered with nothing; a row saying REFUSED / unconfigured / 14:02 is an answer.

The schema lives here, next to the code that writes it, and is installed by
``init_connector_schema(conn)`` called from ``dispatch/db.py::_init_db`` -- the
same pattern, in the same place, as ``dispatch.tokens.init_token_schema`` and
``dispatch.spine.db.init_spine_schema``. A subsystem owns its tables.

Two rules this module holds to:

**An audit write never breaks the call it is recording.** The connector call has
already happened by the time a row is written. Letting a locked database turn a
completed refusal into an exception would mean the audit trail could take
Dispatch down, so ``sqlite3.Error`` is swallowed and the boolean return says
whether the row landed. ``dispatch/tokens.py`` makes the same trade for the same
reason.

**This is the only file in the connectors package allowed to touch a database at
all.** ``dispatch/connectors/boundary.py`` enforces that by scanning the
package's imports: every other module in it is refused if it so much as imports
``sqlite3`` or ``dispatch.db``, and this one is refused if its SQL names any
table other than ``connector_audit``. That is what keeps "a connector may never
write to Current Reality" a property of the code rather than a promise about it.
"""

from __future__ import annotations

import sqlite3

from dispatch.connectors.contract import AuditRecord, ConnectorResult, ConnectorStatus

#: The only table this package writes. ``boundary.verify_package`` asserts that
#: no SQL anywhere in ``dispatch/connectors`` names anything else.
AUDIT_TABLE = "connector_audit"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS connector_audit (
    audit_id             TEXT PRIMARY KEY,
    connector_id         TEXT NOT NULL,
    provider             TEXT NOT NULL DEFAULT '',
    operation            TEXT NOT NULL,
    status               TEXT NOT NULL,
    outcome              TEXT NOT NULL,
    reason               TEXT NOT NULL DEFAULT '',
    attempts             INTEGER NOT NULL DEFAULT 0,
    source_reference     TEXT NOT NULL DEFAULT '',
    evidence_fingerprint TEXT NOT NULL DEFAULT '',
    at                   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connector_audit_connector
    ON connector_audit(connector_id, at);
"""


def init_connector_schema(conn: sqlite3.Connection) -> None:
    """Called from dispatch.db._init_db, beside the Spine's and the token
    ledger's own initializers -- the same pattern, for the same reason."""
    conn.executescript(_SCHEMA)


def record(entry: AuditRecord) -> bool:
    """Write one audit row. Returns whether it landed.

    Imported inside the function rather than at module scope so that importing
    the connectors package never pulls in the database layer as a side effect --
    the package is meant to be importable, and inspectable, by a process that
    has no Dispatch database at all.
    """
    from dispatch.db import get_connection

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO connector_audit (audit_id, connector_id, provider, operation, "
                "status, outcome, reason, attempts, source_reference, evidence_fingerprint, at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry.audit_id,
                    entry.connector_id,
                    entry.provider,
                    entry.operation,
                    entry.status.value,
                    entry.outcome,
                    entry.reason,
                    entry.attempts,
                    entry.source_reference,
                    entry.evidence_fingerprint,
                    entry.at,
                ),
            )
        return True
    except sqlite3.Error:
        # The attempt being recorded has already happened. An audit write must
        # never be the reason a completed call reports failure.
        return False


def audit_for(result: ConnectorResult, *, provider: str = "") -> AuditRecord:
    """Derive the audit row from a result, so the two cannot disagree.

    Outcome is read off the result rather than passed in: ``ok`` when a payload
    came back, ``refused`` when Dispatch declined to try (unconfigured, not
    authorized, boundary), ``failed`` when an attempt was made and did not come
    back.
    """
    refusal_kinds = {"unconfigured", "not_authorized", "refused_by_boundary"}
    if result.ok:
        outcome = "ok"
    elif result.error is not None and result.error.kind in refusal_kinds:
        outcome = "refused"
    else:
        outcome = "failed"

    source_reference = ""
    evidence_fingerprint = ""
    if result.payload is not None:
        source_reference = result.payload.provenance.source_reference
        evidence = result.payload.provenance.evidence
        if evidence is not None:
            evidence_fingerprint = evidence.response_fingerprint

    return AuditRecord(
        connector_id=result.connector_id,
        provider=provider,
        operation=result.operation,
        status=result.status,
        outcome=outcome,
        reason="" if result.ok else result.refusal_message(),
        attempts=result.retry.attempts,
        source_reference=source_reference,
        evidence_fingerprint=evidence_fingerprint,
    )


def list_audit(
    connector_id: str | None = None,
    *,
    outcome: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Read the trail back, newest first."""
    from dispatch.db import get_connection

    sql = "SELECT * FROM connector_audit"
    clauses, params = [], []
    if connector_id:
        clauses.append("connector_id=?")
        params.append(connector_id)
    if outcome:
        clauses.append("outcome=?")
        params.append(outcome)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY at DESC, rowid DESC LIMIT ?"
    params.append(int(limit))
    with get_connection() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def last_success(connector_id: str) -> dict | None:
    """The last successful communication for one connector, or None.

    The contract's ``last successful communication`` field is answered from the
    audit table rather than from connector state: an in-memory timestamp is lost
    on restart, and a connector that forgets its last success will report a
    fresher-looking health than it has earned.
    """
    rows = list_audit(connector_id, outcome="ok", limit=1)
    return rows[0] if rows else None


def status_from_last_attempt(connector_id: str) -> ConnectorStatus | None:
    """The truth word from the most recent attempt, or None if never attempted."""
    rows = list_audit(connector_id, limit=1)
    if not rows:
        return None
    try:
        return ConnectorStatus(rows[0]["status"])
    except ValueError:  # pragma: no cover - only reachable via hand-edited rows
        return None
