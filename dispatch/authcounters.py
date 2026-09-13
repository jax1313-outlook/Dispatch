"""Failed-attempt counters and lockouts, held where a transaction protects them.

Both PIN registries -- Authority's (`portal/models/identity.py`) and the
driver's (`portal/models/driver_pin_registry.py`) -- kept `failed_attempt_count`
inside their JSON store, and every JSON store in this program does
read-modify-write: `_load()` reads the whole file, the caller mutates it,
`_save()` writes it back. `portal/models/__init__.py` says so in its own words:
"Two processes doing read-modify-write against the same store still lose one
update; the last os.replace wins." That was accepted deliberately, and for
durability it is a reasonable trade.

It stops being reasonable the moment a lockout counter lives in one of those
files, because the lost update is no longer a cosmetic race -- it is the
brute-force protection.

    attempt A reads count=0 ─┐
    attempt B reads count=0 ─┤ both write count=1
    attempt C reads count=0 ─┘

Fire the guesses concurrently and the counter never reaches MAX_FAILED_ATTEMPTS.
The lockout is defeated by the one thing an attacker fully controls: how many
requests to send at once. Nothing in the registry, the audit log, or any screen
would show it; the count simply stays low.

So the counter moves here, to `auth_attempt_state`, and the increment is
`UPDATE ... SET failed_attempt_count = failed_attempt_count + 1` -- one
statement, inside one transaction, where SQLite serialises it. The PIN hash, the
recovery word hash and everything else about a card stay exactly where they
were: this module deliberately owns the one field that was unsafe, not the
credential, so nothing about how a card is created, reset or revoked changes.

Time is passed in rather than read here. A lockout that expires is the only
thing in this module that depends on "now", and a test that has to sleep fifteen
minutes to prove an expiry is a test nobody runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dispatch.db import get_connection

#: Subject kinds. A driver card and an Authority identity can share an id space
#: without sharing a lockout, which is why the key is a pair.
KIND_DRIVER = "driver"
KIND_AUTHORITY = "authority"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_attempt_state (
    subject_kind         TEXT NOT NULL,
    subject_id           TEXT NOT NULL,
    failed_attempt_count INTEGER NOT NULL DEFAULT 0,
    locked_until         TEXT,
    last_failure_at      TEXT,
    last_success_at      TEXT,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (subject_kind, subject_id)
);
"""


def init_auth_counter_schema(conn) -> None:
    conn.executescript(_SCHEMA)


def _utc_now() -> datetime:
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


def _row_to_state(row) -> dict:
    return {
        "failed_attempt_count": row["failed_attempt_count"],
        "locked_until": row["locked_until"],
        "last_failure_at": row["last_failure_at"],
        "last_success_at": row["last_success_at"],
    }


EMPTY_STATE = {
    "failed_attempt_count": 0,
    "locked_until": None,
    "last_failure_at": None,
    "last_success_at": None,
}


def get_state(kind: str, subject_id: str) -> dict:
    """What the registry displays. Never creates a row."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM auth_attempt_state WHERE subject_kind=? AND subject_id=?",
            (kind, subject_id),
        ).fetchone()
    return _row_to_state(row) if row else dict(EMPTY_STATE)


def is_locked(kind: str, subject_id: str, *, now: datetime | None = None) -> bool:
    """True while a lockout is in force. An expired lockout is not a lockout."""
    locked_until = _parse(get_state(kind, subject_id)["locked_until"])
    if locked_until is None:
        return False
    return (now or _utc_now()) < locked_until


def record_failure(
    kind: str,
    subject_id: str,
    *,
    max_attempts: int,
    lockout_minutes: int,
    now: datetime | None = None,
) -> dict:
    """Count one failed attempt and lock the subject out if that was the last one.

    The increment reads and writes in a single statement so that two concurrent
    attempts produce two, not one. `INSERT ... ON CONFLICT DO UPDATE` makes the
    first attempt and the fiftieth the same code path, which matters because the
    "first" one is exactly where a read-then-write race is easiest to win.

    Returns the state after the attempt, so the caller can log the number it
    actually reached rather than the number it believed it was setting.
    """
    moment = now or _utc_now()
    stamp = _iso(moment)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO auth_attempt_state
                   (subject_kind, subject_id, failed_attempt_count,
                    locked_until, last_failure_at, updated_at)
               VALUES (?, ?, 1, NULL, ?, ?)
               ON CONFLICT(subject_kind, subject_id) DO UPDATE SET
                   failed_attempt_count = auth_attempt_state.failed_attempt_count + 1,
                   last_failure_at = excluded.last_failure_at,
                   updated_at = excluded.updated_at""",
            (kind, subject_id, stamp, stamp),
        )
        # Lock in the same transaction as the increment. Deciding the lockout in
        # a second statement against a re-read count is the same race again, one
        # layer up.
        conn.execute(
            """UPDATE auth_attempt_state
                  SET locked_until = ?
                WHERE subject_kind = ? AND subject_id = ?
                  AND failed_attempt_count >= ?
                  AND (locked_until IS NULL OR locked_until < ?)""",
            (
                _iso(moment + timedelta(minutes=lockout_minutes)),
                kind,
                subject_id,
                max_attempts,
                stamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM auth_attempt_state WHERE subject_kind=? AND subject_id=?",
            (kind, subject_id),
        ).fetchone()
    return _row_to_state(row)


def record_success(kind: str, subject_id: str, *, now: datetime | None = None) -> dict:
    """Clear the count and any lockout. A correct PIN ends the sequence."""
    stamp = _iso(now or _utc_now())
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO auth_attempt_state
                   (subject_kind, subject_id, failed_attempt_count,
                    locked_until, last_success_at, updated_at)
               VALUES (?, ?, 0, NULL, ?, ?)
               ON CONFLICT(subject_kind, subject_id) DO UPDATE SET
                   failed_attempt_count = 0,
                   locked_until = NULL,
                   last_success_at = excluded.last_success_at,
                   updated_at = excluded.updated_at""",
            (kind, subject_id, stamp, stamp),
        )
    return get_state(kind, subject_id)


def clear(kind: str, subject_id: str, *, now: datetime | None = None) -> dict:
    """A deliberate reset -- Mike issuing a new PIN, or a recovery-word reset.

    Identical to `record_success` in effect and separate in name on purpose: the
    audit trail should be able to tell "they got the PIN right" from "somebody
    with authority cleared it".
    """
    return record_success(kind, subject_id, now=now)


def forget(kind: str, subject_id: str) -> None:
    """Drop the row entirely -- used when the card or identity is deleted."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM auth_attempt_state WHERE subject_kind=? AND subject_id=?",
            (kind, subject_id),
        )
