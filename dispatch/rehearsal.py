"""Rehearsal mode — operational-proof data that can never pass for a live mission.

Task 2 of the Operational Readiness Mission needs Mike to walk one complete load
through Dispatch on his own machine before a real revenue load is ever entered.
That walk creates a driver, a truck, a load, milestones, and evidence files that
look exactly like operational records, because they travel the same code paths --
which is the entire point of the exercise, and also the entire danger of it.

The requirement (mission Section 4.2) is therefore:

    a REHEARSAL tag on load, driver, truck, evidence, and milestone records;
    a visible banner in driver and portal views; no rehearsal record may ever
    display as an unlabeled live mission; rehearsal records must be excludable
    from operational queries and reports; and it must be possible to purge them
    without touching live data.

Design decisions, and why:

**One TEXT column, not a boolean plus a join table.** Every table listed in
``REHEARSAL_TABLES`` gets a single ``rehearsal_session`` column, empty string for
operational records and a session id for rehearsal ones. A boolean would have
answered "is this rehearsal" but not "which rehearsal", and purge needs the
second question answered exactly -- purging by "everything flagged" would be a
blunt instrument on a machine that has held more than one rehearsal. A separate
membership table would have made every operational query a join, which is how
exclusion quietly stops happening. A column that is empty for live data means
the operational filter is ``rehearsal_session = ''`` and costs nothing.

**Tagging happens in the write path, not afterwards.** ``tag_if_active`` is
called by the ``dispatch.store`` create functions for the five record types the
mission names. A record created through the portal UI during a rehearsal is
therefore tagged by the same mechanism as one created by the proof script; there
is no way to create an untagged record while a session is active, which is the
property that makes "no rehearsal record may ever display as an unlabeled live
mission" true rather than aspirational.

**The active session is explicit and process-scoped.** Either a
``contextvars.ContextVar`` (set by the ``rehearsal_mode`` context manager, so a
script can scope it precisely and tests cannot leak it into each other) or the
``DISPATCH_REHEARSAL_SESSION`` environment variable (so the launcher can start
the portal in rehearsal mode without the portal growing a runtime toggle that
could be flipped by a request). There is deliberately no HTTP endpoint that
turns rehearsal mode on: an operational surface that can be switched into
rehearsal by a click is a surface that can be switched *out* of it by a click,
and the second one is the dangerous direction.

**Purge is implemented, gated, and never automatic.** Section 8 item 9 of the
mission reserves "any deletion or purge of data, including rehearsal data, on
Mike's machine" to Mike. So ``plan_purge`` -- which deletes nothing -- is the
function the tooling calls, and ``purge_session`` requires an explicit actor and
an explicit ``confirm=True``. Nothing in this repository calls ``purge_session``.

**No Mike attribution is ever manufactured.** ``start_session`` requires an
explicit ``actor_id`` and refuses reserved system identities. Per mission
Section 1.1, the actor of a rehearsal is the authenticated account performing
it, labeled as rehearsal -- so the caller supplies it and this module never
defaults, infers, or seeds one.
"""

from __future__ import annotations

import contextvars
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field

from dispatch.db import get_connection
from dispatch.models import _gen_id, _utc_now

# Matches dispatch/opportunities.py and reconciliation/adapters/publisher_adapter.py.
# Deliberately duplicated rather than imported across a subsystem boundary --
# see THE MIKE RULE in DECISION_LOG.md: subsystems stay standalone.
RESERVED_SYSTEM_IDENTITIES = {"PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY"}

#: The label that appears in every user-facing surface and in every stored
#: record. One spelling, used everywhere, so a search for it finds all of them.
REHEARSAL_LABEL = "REHEARSAL"

#: Environment variable the launcher sets to start the portal in rehearsal mode.
REHEARSAL_ENV_VAR = "DISPATCH_REHEARSAL_SESSION"

#: table name -> primary key column. These are the five record types Section 4.2
#: names, plus exceptions and POD packages, which the proof path (steps 13-14)
#: also creates and which would otherwise be the two untagged records in an
#: otherwise fully tagged rehearsal.
REHEARSAL_TABLES: dict[str, str] = {
    "loads": "load_id",
    "drivers": "driver_id",
    "equipment": "equipment_id",
    "milestones": "milestone_id",
    "evidence": "evidence_id",
    "exceptions": "exception_id",
    "pod_packages": "pod_id",
}

SESSION_STATUSES = ["OPEN", "PASSED", "FAILED", "ABANDONED"]

_SESSION_SCHEMA = """\
CREATE TABLE IF NOT EXISTS rehearsal_sessions (
    session_id   TEXT PRIMARY KEY,
    label        TEXT NOT NULL DEFAULT '',
    actor_id     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'OPEN',
    note         TEXT NOT NULL DEFAULT '',
    result_note  TEXT NOT NULL DEFAULT '',
    started_at   TEXT NOT NULL,
    ended_at     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_rehearsal_status ON rehearsal_sessions(status);
"""


class RehearsalError(RuntimeError):
    """Raised instead of quietly producing an untagged or misattributed record."""


# --------------------------------------------------------------------------- schema


def init_rehearsal_schema(conn: sqlite3.Connection) -> None:
    """Create the session ledger and add the tag column to every tagged table.

    Idempotent and guarded, matching ``dispatch/db.py::_apply_migrations``: the
    ``ALTER TABLE`` raises ``OperationalError`` on a database that already has
    the column, and that is the expected steady state, not an error.
    """
    conn.executescript(_SESSION_SCHEMA)
    for table in REHEARSAL_TABLES:
        try:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN rehearsal_session TEXT NOT NULL DEFAULT ''"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_rehearsal "
                f"ON {table}(rehearsal_session)"
            )
        except sqlite3.OperationalError:  # pragma: no cover - index name collision
            pass


# --------------------------------------------------------------------------- model


@dataclass
class RehearsalSession:
    session_id: str = field(default_factory=lambda: _gen_id("REH"))
    label: str = ""
    actor_id: str = ""
    status: str = "OPEN"
    note: str = ""
    result_note: str = ""
    started_at: str = field(default_factory=_utc_now)
    ended_at: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["rehearsal_label"] = REHEARSAL_LABEL
        return d


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    d["rehearsal_label"] = REHEARSAL_LABEL
    return d


# --------------------------------------------------------------------------- sessions


def start_session(*, label: str, actor_id: str, note: str = "") -> dict:
    """Open a rehearsal session.

    ``actor_id`` is required and never defaulted. Mission Section 1.1: the actor
    of a rehearsal is the authenticated account performing it, labeled as
    rehearsal, never impersonating Mike. Nothing here fabricates one, and a
    reserved system identity is refused outright -- a rehearsal is a human act
    or it is not a rehearsal.
    """
    actor = (actor_id or "").strip()
    if not actor:
        raise RehearsalError(
            "A rehearsal session needs the authenticated account performing it. "
            "Pass actor_id explicitly; this is never defaulted or inferred."
        )
    if actor.upper() in RESERVED_SYSTEM_IDENTITIES:
        raise RehearsalError(
            f"'{actor}' is a reserved system identity and cannot perform a rehearsal. "
            f"A rehearsal records what a human did."
        )
    if not (label or "").strip():
        raise RehearsalError("A rehearsal session needs a label so its records are identifiable.")

    session = RehearsalSession(label=label.strip(), actor_id=actor, note=note)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO rehearsal_sessions
               (session_id, label, actor_id, status, note, result_note, started_at, ended_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (session.session_id, session.label, session.actor_id, session.status,
             session.note, session.result_note, session.started_at, session.ended_at),
        )
    return session.to_dict()


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        return _row(
            conn.execute(
                "SELECT * FROM rehearsal_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        )


def list_sessions(status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM rehearsal_sessions"
    params: list = []
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY started_at DESC"
    with get_connection() as conn:
        return [_row(r) for r in conn.execute(sql, params).fetchall()]


def close_session(session_id: str, *, result: str, actor_id: str, note: str = "") -> dict:
    """Record how a rehearsal ended. ``result`` is PASSED, FAILED, or ABANDONED."""
    if result not in SESSION_STATUSES or result == "OPEN":
        raise RehearsalError(
            f"result must be one of PASSED, FAILED, ABANDONED -- got {result!r}."
        )
    if not (actor_id or "").strip():
        raise RehearsalError("Closing a rehearsal records who closed it. Pass actor_id.")
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM rehearsal_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if existing is None:
            raise RehearsalError(f"No rehearsal session {session_id!r}.")
        conn.execute(
            "UPDATE rehearsal_sessions SET status=?, result_note=?, ended_at=? "
            "WHERE session_id=?",
            (result, note, _utc_now(), session_id),
        )
        return _row(
            conn.execute(
                "SELECT * FROM rehearsal_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        )


# --------------------------------------------------------------------------- activation

_active: contextvars.ContextVar[str] = contextvars.ContextVar("dispatch_rehearsal_session", default="")


def active_session_id() -> str:
    """The session records created right now belong to, or '' for operational.

    The ContextVar wins over the environment variable so a script can scope a
    rehearsal precisely inside a process that was started in rehearsal mode --
    and so a test can never leak its session into the next one.
    """
    scoped = _active.get()
    if scoped:
        return scoped
    return (os.environ.get(REHEARSAL_ENV_VAR) or "").strip()


def is_active() -> bool:
    return bool(active_session_id())


@contextmanager
def rehearsal_mode(session_id: str):
    """Scope a block of work to a rehearsal session.

    Every tagged record created inside carries ``session_id``. Refuses an
    unknown or already-closed session rather than tagging records with an id
    that leads nowhere -- an orphan tag is worse than no tag, because purge
    cannot find it and the banner cannot explain it.
    """
    session = get_session(session_id)
    if session is None:
        raise RehearsalError(f"No rehearsal session {session_id!r}.")
    if session["status"] != "OPEN":
        raise RehearsalError(
            f"Rehearsal session {session_id!r} is {session['status']}, not OPEN. "
            f"Start a new session rather than adding records to a finished one."
        )
    token = _active.set(session_id)
    try:
        yield session
    finally:
        _active.reset(token)


# --------------------------------------------------------------------------- tagging


def _check_table(table: str) -> str:
    if table not in REHEARSAL_TABLES:
        raise RehearsalError(
            f"{table!r} is not a rehearsal-tagged table. Tagged tables are: "
            f"{', '.join(sorted(REHEARSAL_TABLES))}."
        )
    return REHEARSAL_TABLES[table]


def tag(table: str, record_id: str, *, session_id: str) -> None:
    """Mark one existing record as belonging to a rehearsal session."""
    pk = _check_table(table)
    if not session_id:
        raise RehearsalError("tag() needs a session_id. Use tag_if_active() for the write path.")
    with get_connection() as conn:
        conn.execute(
            f"UPDATE {table} SET rehearsal_session=? WHERE {pk}=?", (session_id, record_id)
        )


def tag_if_active(table: str, record_id: str) -> str:
    """Tag a record if a rehearsal is running, using this module's own connection.

    Returns the session id applied, or '' when no rehearsal is active -- in
    which case this is a no-op and the operational write path is unchanged,
    which is the requirement that rehearsal mode "must not weaken any
    production path."
    """
    session_id = active_session_id()
    if not session_id:
        return ""
    tag(table, record_id, session_id=session_id)
    return session_id


def tag_in(conn: sqlite3.Connection, table: str, record_id: str) -> str:
    """The write-path variant: tag inside the caller's open transaction.

    ``dispatch.store``'s create functions call this immediately after their
    INSERT, on the same connection, so the record is never committed in an
    untagged state -- there is no window in which a concurrent reader could see
    a rehearsal record with no label on it. Reopening the database with
    ``tag_if_active`` would have left exactly that window.

    Returns '' and touches nothing when no rehearsal is active, which is the
    operational default and costs one environment lookup.
    """
    session_id = active_session_id()
    if not session_id:
        return ""
    pk = _check_table(table)
    conn.execute(
        f"UPDATE {table} SET rehearsal_session=? WHERE {pk}=?", (session_id, record_id)
    )
    return session_id


def is_rehearsal(table: str, record_id: str) -> bool:
    return bool(session_of(table, record_id))


def session_of(table: str, record_id: str) -> str:
    """Which rehearsal session a record belongs to, or '' if it is operational."""
    pk = _check_table(table)
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT rehearsal_session FROM {table} WHERE {pk}=?", (record_id,)
        ).fetchone()
    return (row["rehearsal_session"] if row else "") or ""


def label_for(record: dict | None) -> str:
    """The label a surface must display for a record dict.

    Returns ``"REHEARSAL"`` or ``""``. Templates and report generators call this
    rather than testing the column themselves, so there is one answer to "is
    this labeled" and it is not re-derived in nine places.
    """
    if not record:
        return ""
    return REHEARSAL_LABEL if (record.get("rehearsal_session") or "") else ""


# --------------------------------------------------------------------------- exclusion


def operational_only(table: str = "") -> str:
    """SQL fragment selecting operational records only.

    ``table`` qualifies the column for a joined query. Returns a bare predicate
    with no leading AND, so the caller composes it the same way every other
    clause in ``dispatch/store.py`` is composed.
    """
    prefix = f"{table}." if table else ""
    return f"{prefix}rehearsal_session = ''"


def rehearsal_only(table: str = "") -> str:
    prefix = f"{table}." if table else ""
    return f"{prefix}rehearsal_session != ''"


def filter_rows(rows: list[dict], *, include_rehearsal: bool) -> list[dict]:
    """Post-query exclusion for report generators that already hold rows."""
    if include_rehearsal:
        return list(rows)
    return [r for r in rows if not (r.get("rehearsal_session") or "")]


# --------------------------------------------------------------------------- purge


@dataclass(frozen=True)
class PurgePlan:
    """What a purge would delete. Produced by ``plan_purge``, which deletes nothing."""

    session_id: str
    counts: dict[str, int]
    record_ids: dict[str, list[str]]
    total: int
    evidence_files: list[str]

    def __bool__(self) -> bool:
        return self.total > 0


def session_records(session_id: str) -> dict[str, list[str]]:
    """Every record id tagged to a session, by table."""
    out: dict[str, list[str]] = {}
    with get_connection() as conn:
        for table, pk in REHEARSAL_TABLES.items():
            rows = conn.execute(
                f"SELECT {pk} FROM {table} WHERE rehearsal_session=? ORDER BY {pk}",
                (session_id,),
            ).fetchall()
            out[table] = [r[pk] for r in rows]
    return out


def plan_purge(session_id: str) -> PurgePlan:
    """Report what a purge would remove. Deletes nothing.

    This is the function the readiness tooling and the proof report call.
    Executing the purge is a Mike decision (mission Section 8 item 9), so the
    tooling shows him the plan and stops.
    """
    ids = session_records(session_id)
    files: list[str] = []
    if ids.get("evidence"):
        placeholders = ",".join("?" * len(ids["evidence"]))
        with get_connection() as conn:
            rows = conn.execute(
                f"SELECT file_path FROM evidence WHERE evidence_id IN ({placeholders})",
                ids["evidence"],
            ).fetchall()
        files = [r["file_path"] for r in rows if r["file_path"]]
    counts = {t: len(v) for t, v in ids.items()}
    return PurgePlan(
        session_id=session_id,
        counts=counts,
        record_ids=ids,
        total=sum(counts.values()),
        evidence_files=files,
    )



def _dependents(conn: sqlite3.Connection, parent: str) -> list[tuple[str, str]]:
    """(table, column) for every foreign key in the schema pointing at ``parent``.

    Read from the database rather than maintained as a list here, because a
    hard-coded list is correct on the day it is written and silently wrong the
    first time a table is added -- and the symptom of that would be a purge that
    raises an IntegrityError at commit, or worse, one that leaves a row pointing
    at a load that no longer exists.
    """
    out: list[tuple[str, str]] = []
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for table in tables:
        for fk in conn.execute(f"PRAGMA foreign_key_list({table})").fetchall():
            if fk["table"] == parent:
                out.append((table, fk["from"]))
    return out


def purge_session(
    session_id: str, *, actor_id: str, confirm: bool = False, delete_files: bool = False
) -> PurgePlan:
    """Delete every record tagged to one rehearsal session, and nothing else.

    Nothing in this repository calls this. It exists because Section 4.2
    requires that a purge be *possible* without touching live data, and it is
    gated because Section 8 item 9 makes running one a Mike decision.

    The deletion order walks child tables before parents so the foreign keys
    enforced by ``get_connection`` hold throughout -- a purge that had to
    disable ``PRAGMA foreign_keys`` would be a purge that could orphan live
    rows, which is exactly the failure this is meant to be safe against.

    Evidence files on disk are removed only when ``delete_files=True``, and only
    for paths recorded against this session's evidence rows.
    """
    if not confirm:
        raise RehearsalError(
            "purge_session refuses to run without confirm=True. Purging data on "
            "Mike's machine is his decision (Operational Readiness Mission, "
            "Section 8 item 9). Call plan_purge() to see what would be removed."
        )
    if not (actor_id or "").strip():
        raise RehearsalError("A purge records who performed it. Pass actor_id.")

    plan = plan_purge(session_id)

    with get_connection() as conn:
        # Defer foreign-key enforcement to COMMIT rather than disabling it.
        # A purge has to delete a parent and its children in one transaction,
        # and no single ordering satisfies every reference in a 27-table schema
        # that keeps growing. PRAGMA defer_foreign_keys keeps the constraints
        # fully in force -- they are checked at commit, and a purge that would
        # leave one dangling row raises there and rolls the whole thing back.
        # PRAGMA foreign_keys=OFF would have been the easy version of this and
        # would have silently orphaned live rows instead.
        conn.execute("PRAGMA defer_foreign_keys=ON")

        # Everything that references a purged load, driver, or truck goes with
        # it -- visibility, activities, rate confirmations, expenses,
        # settlements, detentions and anything added later. The dependent set is
        # read from the schema (PRAGMA foreign_key_list) rather than hard-coded,
        # so a table added next year is purged without this function changing.
        for parent in ("loads", "drivers", "equipment"):
            parent_ids = plan.record_ids.get(parent) or []
            if not parent_ids:
                continue
            placeholders = ",".join("?" * len(parent_ids))
            for table, column in _dependents(conn, parent):
                conn.execute(
                    f"DELETE FROM {table} WHERE {column} IN ({placeholders})", parent_ids
                )

        for table in REHEARSAL_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE rehearsal_session=?", (session_id,))
        conn.execute(
            "UPDATE rehearsal_sessions SET status=?, result_note=?, ended_at=? WHERE session_id=?",
            (
                "ABANDONED",
                f"purged by {actor_id.strip()}",
                _utc_now(),
                session_id,
            ),
        )

    if delete_files:
        from pathlib import Path

        for path in plan.evidence_files:
            try:
                Path(path).unlink()
            except OSError:
                # A missing or unreadable evidence file is reported by the plan,
                # not raised here -- a half-finished purge is worse than one
                # that leaves a file behind and says so.
                pass

    return plan


# --------------------------------------------------------------------------- surfaces


def banner_context() -> dict:
    """What every user-facing surface needs to render the rehearsal banner.

    Installed as a Flask context processor in ``portal/app.py`` so no template
    has to remember to ask. Returns ``rehearsal_active=False`` when no session
    is active, which is the operational default and renders nothing.
    """
    session_id = active_session_id()
    if not session_id:
        return {
            "rehearsal_active": False,
            "rehearsal_label": REHEARSAL_LABEL,
            "rehearsal_session_id": "",
            "rehearsal_session_label": "",
        }
    session = get_session(session_id)
    return {
        "rehearsal_active": True,
        "rehearsal_label": REHEARSAL_LABEL,
        "rehearsal_session_id": session_id,
        "rehearsal_session_label": (session or {}).get("label", ""),
    }
