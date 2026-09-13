"""Every outbound message attempt, recorded — so a failure is visible.

`services._notify_safe()` catches every exception from every notification send
and writes one line to stderr. Twelve call sites. The reasoning is sound as far
as it goes: the load *was* invoiced, and an SMTP timeout should not turn a
committed write into a 500. But the second half was never built. A broker
notification that fails authentication produced:

    no database record   no screen indicator   no counter   no retry
    one line in an unbounded text file

Mike sees Submit succeed. The broker never hears from him. Nothing anywhere
says so, and the truth vocabulary has a word for exactly this state --
UNAVAILABLE -- which no surface was in a position to display because nothing
recorded it.

So every attempt gets a row. The row is written *before* the send, which is the
only ordering that survives the failure modes that matter: a process killed
mid-send, or a transport that hangs, both leave a QUEUED row that the next
sweep can see. A row written afterwards would record only the sends that
already worked.

**Retry is bounded and it backs off.** 1, 5, 15, 60, 240 minutes, then
ABANDONED. Retrying an authentication failure every minute forever is how an
account gets locked, and a queue that never gives up is a queue nobody reads.

**Nothing is retried automatically behind the operator's back.** `retry_due()`
returns what is owed; the launcher, a scheduled task or the Maintenance page
runs it. Dispatch does not open a background thread on a laptop to resend
freight email.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from dispatch.db import get_connection
from dispatch.observability import event, get_logger

log = get_logger("dispatch.delivery")

#: The states an attempt can hold, drawn from the program's fixed vocabulary
#: where one fits and named plainly where none does.
QUEUED = "QUEUED"        #: written, not yet attempted
SENT = "SENT"            #: a transport accepted it
FAILED = "FAILED"        #: the last attempt failed; a retry is owed
ABANDONED = "ABANDONED"  #: out of attempts; a person has to decide
SIMULATED = "SIMULATED"  #: no relay configured; written to the local outbox

OPEN_STATES = (QUEUED, FAILED)

#: Minutes before each retry. Five attempts, then a person decides.
BACKOFF_MINUTES = (1, 5, 15, 60, 240)
MAX_ATTEMPTS = len(BACKOFF_MINUTES)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS delivery_attempts (
    attempt_id     TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    subject_ref    TEXT NOT NULL DEFAULT '',
    recipient      TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    transport      TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'QUEUED',
    attempt_count  INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT NOT NULL DEFAULT '',
    receipt        TEXT NOT NULL DEFAULT '',
    next_retry_at  TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery_attempts(status);
CREATE INDEX IF NOT EXISTS idx_delivery_subject ON delivery_attempts(subject_ref);
"""


def init_delivery_schema(conn) -> None:
    conn.executescript(_SCHEMA)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class Attempt:
    attempt_id: str
    kind: str
    subject_ref: str = ""
    recipient: str = ""
    summary: str = ""
    transport: str = ""
    status: str = QUEUED
    attempt_count: int = 0
    last_error: str = ""
    receipt: str = ""
    next_retry_at: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_row(cls, row) -> "Attempt":
        return cls(**{k: row[k] for k in row.keys() if k in cls.__annotations__})

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def queue(
    kind: str,
    *,
    subject_ref: str = "",
    recipient: str = "",
    summary: str = "",
    transport: str = "",
    now: datetime | None = None,
) -> str:
    """Record the intent to send, before sending. Returns the attempt id.

    Written first on purpose. A process killed mid-send, or a transport that
    hangs past its timeout, both leave a QUEUED row that the next sweep can act
    on. A row written after a successful send records only the sends that
    already worked, which is the set nobody needs a record of.
    """
    moment = _iso(now or _now())
    attempt_id = f"DLV-{uuid.uuid4().hex[:12].upper()}"
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO delivery_attempts
                   (attempt_id, kind, subject_ref, recipient, summary, transport,
                    status, attempt_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,0,?,?)""",
            (attempt_id, kind, subject_ref, recipient, summary, transport, QUEUED, moment, moment),
        )
    return attempt_id


def mark_sent(attempt_id: str, *, receipt: str = "", transport: str = "", now: datetime | None = None) -> None:
    moment = _iso(now or _now())
    with get_connection() as conn:
        conn.execute(
            """UPDATE delivery_attempts
                  SET status=?, attempt_count=attempt_count+1, receipt=?, last_error='',
                      next_retry_at=NULL, updated_at=?,
                      transport=CASE WHEN ?='' THEN transport ELSE ? END
                WHERE attempt_id=?""",
            (SENT, receipt, moment, transport, transport, attempt_id),
        )
    event(log, logging.INFO, "delivery sent", attempt=attempt_id, receipt=receipt or "-")


def mark_simulated(attempt_id: str, *, receipt: str = "", now: datetime | None = None) -> None:
    """No relay configured. The message went to the local outbox, not to anyone.

    A distinct state rather than SENT, because "written to Archive/Outbox" and
    "a mail server accepted it" are different facts and only one of them means
    the broker heard from Mike.
    """
    moment = _iso(now or _now())
    with get_connection() as conn:
        conn.execute(
            """UPDATE delivery_attempts
                  SET status=?, attempt_count=attempt_count+1, receipt=?,
                      next_retry_at=NULL, updated_at=?
                WHERE attempt_id=?""",
            (SIMULATED, receipt, moment, attempt_id),
        )
    event(log, logging.INFO, "delivery simulated", attempt=attempt_id, receipt=receipt or "-")


def mark_failed(attempt_id: str, error: str, *, now: datetime | None = None) -> dict:
    """Count the failure, schedule the next try, or give up and say so."""
    moment = now or _now()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM delivery_attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if row is None:
            return {}
        count = row["attempt_count"] + 1
        if count >= MAX_ATTEMPTS:
            status, next_retry = ABANDONED, None
        else:
            status = FAILED
            next_retry = _iso(moment + timedelta(minutes=BACKOFF_MINUTES[count - 1]))
        conn.execute(
            """UPDATE delivery_attempts
                  SET status=?, attempt_count=?, last_error=?, next_retry_at=?, updated_at=?
                WHERE attempt_id=?""",
            (status, count, str(error)[:2000], next_retry, _iso(moment), attempt_id),
        )
    event(
        log,
        logging.ERROR if status == ABANDONED else logging.WARNING,
        "delivery failed",
        attempt=attempt_id, status=status, attempt_count=count,
        next_retry=next_retry or "none", error=str(error)[:200],
    )
    return {"status": status, "attempt_count": count, "next_retry_at": next_retry}


def get(attempt_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM delivery_attempts WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
    return Attempt.from_row(row).to_dict() if row else None


def list_attempts(*, status: str | None = None, subject_ref: str | None = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM delivery_attempts"
    clauses, params = [], []
    if status:
        clauses.append("status=?")
        params.append(status)
    if subject_ref:
        clauses.append("subject_ref=?")
        params.append(subject_ref)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Attempt.from_row(r).to_dict() for r in rows]


def open_failures(limit: int = 200) -> list[dict]:
    """Everything a person should look at: failed-and-owed, and abandoned."""
    placeholders = ",".join("?" * (len(OPEN_STATES) + 1))
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM delivery_attempts WHERE status IN ({placeholders})"
            " ORDER BY updated_at DESC LIMIT ?",
            (*OPEN_STATES, ABANDONED, limit),
        ).fetchall()
    return [Attempt.from_row(r).to_dict() for r in rows]


def retry_due(*, now: datetime | None = None, limit: int = 50) -> list[dict]:
    """Attempts whose backoff has elapsed. Returned, not sent.

    Dispatch does not open a background thread on a laptop to resend freight
    email. The launcher, a scheduled task, or the Maintenance page decides when
    this runs, so a resend is always something the operator can point at.
    """
    moment = _iso(now or _now())
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM delivery_attempts"
            " WHERE status=? AND next_retry_at IS NOT NULL AND next_retry_at <= ?"
            " ORDER BY next_retry_at ASC LIMIT ?",
            (FAILED, moment, limit),
        ).fetchall()
    return [Attempt.from_row(r).to_dict() for r in rows]


def summary(*, now: datetime | None = None) -> dict:
    """The counts a dashboard shows. Cheap enough to put on every page."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM delivery_attempts GROUP BY status"
        ).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    return {
        "counts": counts,
        "needs_attention": counts.get(FAILED, 0) + counts.get(ABANDONED, 0) + counts.get(QUEUED, 0),
        "abandoned": counts.get(ABANDONED, 0),
        "retry_due": len(retry_due(now=now, limit=1000)),
    }


def send_with_record(
    kind: str,
    send,
    *,
    subject_ref: str = "",
    recipient: str = "",
    summary_text: str = "",
    transport: str = "",
    now: datetime | None = None,
) -> dict:
    """Queue, attempt, and record the outcome. Never raises.

    Replaces the bare try/except-and-print at each notification call site. The
    exception is still swallowed -- an SMTP failure must not fail a committed
    write -- but it is swallowed *into a row somebody can see* rather than into
    a log file on a laptop.

    A receipt beginning "not sent" is the transport's own way of saying it wrote
    a local .eml instead of delivering, so it is recorded as SIMULATED. Calling
    that SENT would be the same lie one layer down.
    """
    attempt_id = queue(
        kind, subject_ref=subject_ref, recipient=recipient,
        summary=summary_text, transport=transport, now=now,
    )
    try:
        receipt = send()
    except Exception as exc:  # noqa: BLE001 - any transport failure, not just SMTP
        outcome = mark_failed(attempt_id, f"{type(exc).__name__}: {exc}", now=now)
        return {"attempt_id": attempt_id, "ok": False, **outcome}

    text = "" if receipt is None else str(receipt)
    if text.startswith("not sent"):
        mark_simulated(attempt_id, receipt=text, now=now)
        return {"attempt_id": attempt_id, "ok": True, "status": SIMULATED, "receipt": text}
    mark_sent(attempt_id, receipt=text, transport=transport, now=now)
    return {"attempt_id": attempt_id, "ok": True, "status": SENT, "receipt": text}
