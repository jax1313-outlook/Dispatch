"""The Real-Load Operational Proof System — the 20-step path and its report.

Section 4.1 of the Operational Readiness Mission states the objective without
ambiguity: "Prove that Mike can move one complete Level 1 Transport load through
Dispatch on his own Windows machine -- **not that the test suite passes.**"

Everything in this module is built around that distinction. The repository test
suite is evidence of software behaviour. It is not operational proof and this
module never presents it as such: the headline of a report generated anywhere
other than Mike's machine is **REHEARSAL NOT YET RUN ON TARGET MACHINE**, and
every step in it is `ABSENT` with the exact command he runs printed beside it.

Three properties this module has to keep, in the order they would otherwise be
lost:

**A step's performer is recorded, never assumed.** Section 4.3 requires every
step to record who performed it -- Mike, Code-automated, or not performed -- and
Section 1.1 forbids manufacturing a Mike attribution anywhere. So the default
performer of every step is `not performed`, and setting it to `Mike` requires a
caller to say so explicitly about a thing that actually happened. Nothing in
this module ever writes that value on its own.

**Persistence across a restart is proven by comparison, not by absence of
error.** Steps 16-18 stop the application, restart it, and then compare record
identifiers and SHA-256 evidence hashes taken before and after. A report that
said "the load was still there" without the identifiers side by side would be a
statement, and Section 0 says a statement that something works is not proof.

**A restore is proven in an isolated destination.** Step 20 restores into a
directory that `dispatch.readiness.check_restore_destination` has already
confirmed is empty and overlaps neither the live database nor the live evidence
store. Restoring into the live paths is prohibited outright (Section 9), and the
readiness gate exists so that prohibition is enforced before the step runs
rather than remembered while it does.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dispatch.readiness import (
    TRUTH_WORDS,
    ReadinessReport,
    application_identity,
    live_paths,
)

#: Section 4.3: "who performed it (Mike / Code-automated / not performed)".
PERFORMERS = ("Mike", "Code-automated", "not performed")

#: The default. Never anything else -- see the module docstring.
NOT_PERFORMED = "not performed"

HEADLINE_PASSED = "REHEARSAL PASSED"
HEADLINE_NOT_RUN = "REHEARSAL NOT YET RUN ON TARGET MACHINE"


def _headline_failed(step_number: int) -> str:
    return f"REHEARSAL FAILED at step {step_number}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- the path


@dataclass(frozen=True)
class StepDefinition:
    """One step of the Section 4.3 proof path, with the command that performs it."""

    number: int
    title: str
    expected_performer: str
    command: str
    note: str = ""


#: Section 4.3, verbatim in order. `command` is what Mike types on his own
#: machine; where a step is a portal action rather than a command, it says so in
#: the terms the portal uses, because "the exact command Mike runs" for a click
#: is the click.
PROOF_PATH: tuple[StepDefinition, ...] = (
    StepDefinition(
        1, "Start Dispatch (via the launcher)", "Mike",
        r"cd /d D:\Dispatch Operations\Code\Dispatch && dispatch.bat  →  choose Start",
        "Records the server PID. Step 16 kills this exact PID.",
    ),
    StepDefinition(
        2, "Authenticate", "Mike",
        "Open http://127.0.0.1:8080/login and sign in with the Authority PIN.",
        "If no identity exists yet, run `cin-portal-init-admin` at the terminal first.",
    ),
    StepDefinition(
        3, "Create or confirm Driver", "Mike",
        "Portal → Fleet → Drivers → Add Driver (or confirm an existing one).",
        "Tagged REHEARSAL automatically while the rehearsal session is active.",
    ),
    StepDefinition(
        4, "Create or confirm Truck", "Mike",
        "Portal → Fleet → Equipment → Add Equipment (or confirm an existing unit).",
        "",
    ),
    StepDefinition(
        5, "Create Load", "Mike",
        "Portal → Dispatch → New Load.",
        "Use a lane you would actually run, so the rehearsal exercises real distances.",
    ),
    StepDefinition(
        6, "Assign Driver", "Mike",
        "Portal → Dispatch → the load → Assign Driver.",
        "",
    ),
    StepDefinition(
        7, "Assign Truck", "Mike",
        "Portal → Dispatch → the load → Assign Equipment.",
        "",
    ),
    StepDefinition(
        8, "Record human decision where required", "Mike",
        "Portal → the decision surface the load presents (approve / reject / flag).",
        "Actor is the authenticated account performing the rehearsal, labeled REHEARSAL. "
        "No Mike attribution is ever written by Dispatch on its own.",
    ),
    StepDefinition(
        9, "Create or confirm Outlook schedule information where authorized", "Mike",
        "Outlook, by hand. Dispatch does not create calendar events; Outlook is the "
        "single source of scheduling truth (mission Section 1.5).",
        "Record the status as LIVE, SIMULATED, MANUAL, or ABSENT -- nothing else.",
    ),
    StepDefinition(
        10, "Driver receives mission", "Mike",
        "Open the Driver Portal (/driver) on the phone and sign in with phone number + PIN.",
        "The REHEARSAL banner must be visible on this screen. If it is not, the run fails here.",
    ),
    StepDefinition(
        11, "Driver reports milestones (arrival, pickup, departure, delivery)", "Mike",
        "Driver Portal → the four milestone buttons, in order.",
        "",
    ),
    StepDefinition(
        12, "Driver uploads pickup evidence", "Mike",
        "Driver Portal → Upload Evidence → photograph of the loaded trailer / BOL.",
        "The file's SHA-256 is recorded here and compared again at step 18 and step 20.",
    ),
    StepDefinition(
        13, "Driver reports an exception if applicable", "Mike",
        "Driver Portal → Report Exception.",
        "Optional in reality; perform it once during the rehearsal so the path is proven.",
    ),
    StepDefinition(
        14, "Driver uploads POD and delivery evidence", "Mike",
        "Driver Portal → Upload Evidence → signed POD.",
        "",
    ),
    StepDefinition(
        15, "Load reaches delivered or closed state through governed Spine transitions", "Mike",
        "Portal → the load → advance status to delivered / closed.",
        "Spine owns the transition. A refusal here is the gate working, not a failure of the run.",
    ),
    StepDefinition(
        16, "Application stops completely (PID confirmed dead)", "Mike",
        r"dispatch.bat  →  choose Stop, then confirm the PID is gone",
        "Confirm the stop yourself. A second launch that hits 'address already in use' and "
        "is answered by the ORIGINAL process is a false pass on the one thing this step exists "
        "to prove.",
    ),
    StepDefinition(
        17, "Application restarts", "Mike",
        r"dispatch.bat  →  choose Start",
        "The new PID must differ from the one recorded at step 1.",
    ),
    StepDefinition(
        18, "Load, milestones, and evidence remain", "Code-automated",
        "python scripts/dispatch_proof.py verify --load-id <LOAD_ID>",
        "Compares record identifiers and evidence SHA-256 hashes against step 12/14.",
    ),
    StepDefinition(
        19, "Backup is created", "Code-automated",
        r'python scripts/dispatch_backup.py create --destination "D:\Backups\Dispatch"',
        "",
    ),
    StepDefinition(
        20, "Restore is proven in an isolated destination", "Code-automated",
        r'python scripts/dispatch_backup.py restore --archive <ARCHIVE> '
        r'--destination "D:\Restore Proof" --verify',
        "Never the live database or the live evidence store. The readiness check refuses "
        "a destination that overlaps either.",
    ),
)

assert len(PROOF_PATH) == 20 and [s.number for s in PROOF_PATH] == list(range(1, 21))


# --------------------------------------------------------------------------- results


@dataclass
class StepResult:
    """What actually happened at one step, or the fact that nothing did."""

    number: int
    title: str
    performer: str = NOT_PERFORMED
    status: str = "ABSENT"
    timestamp: str = ""
    record_ids: dict = field(default_factory=dict)
    result: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if self.performer not in PERFORMERS:
            raise ValueError(
                f"performer must be one of {PERFORMERS}, got {self.performer!r}. "
                f"Section 4.3 allows exactly these three."
            )
        if self.status not in TRUTH_WORDS:
            raise ValueError(
                f"{self.status!r} is not one of the Section 1.8 truth words: "
                f"{', '.join(TRUTH_WORDS)}."
            )

    @property
    def performed(self) -> bool:
        return self.performer != NOT_PERFORMED

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProofRun:
    """One walk of the proof path, complete or not."""

    steps: list[StepResult]
    identity: dict = field(default_factory=application_identity)
    generated_at: str = field(default_factory=_now)
    rehearsal_session_id: str = ""
    rehearsal_session_label: str = ""
    machine: str = "UNVERIFIED"
    outlook_status: str = "ABSENT"
    readiness: ReadinessReport | None = None
    paths: dict = field(default_factory=dict)
    evidence_hashes: dict = field(default_factory=dict)
    restored_evidence_hashes: dict = field(default_factory=dict)
    original_record_ids: dict = field(default_factory=dict)
    restored_record_ids: dict = field(default_factory=dict)
    failure_note: str = ""

    def __post_init__(self) -> None:
        if self.outlook_status not in ("LIVE", "SIMULATED", "MANUAL", "ABSENT"):
            raise ValueError(
                "Section 4.3 restricts step 9's Outlook status to LIVE, SIMULATED, "
                f"MANUAL, or ABSENT. Got {self.outlook_status!r}."
            )

    @property
    def first_failure(self) -> StepResult | None:
        for step in self.steps:
            if step.performed and step.status == "UNAVAILABLE":
                return step
        return None

    @property
    def all_performed(self) -> bool:
        return all(s.performed for s in self.steps)

    @property
    def headline(self) -> str:
        """One line, at the top of the report. Section 4.5.

        A run is PASSED only when every step was performed on the target machine
        and none failed. Anything else is either a named failure step or the
        honest admission that it has not been run.
        """
        failure = self.first_failure
        if failure is not None:
            return _headline_failed(failure.number)
        if self.all_performed and self.machine != "UNVERIFIED":
            return HEADLINE_PASSED
        return HEADLINE_NOT_RUN

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "generated_at": self.generated_at,
            "machine": self.machine,
            "identity": self.identity,
            "rehearsal_session_id": self.rehearsal_session_id,
            "rehearsal_session_label": self.rehearsal_session_label,
            "outlook_status": self.outlook_status,
            "paths": self.paths,
            "evidence_hashes": self.evidence_hashes,
            "restored_evidence_hashes": self.restored_evidence_hashes,
            "original_record_ids": self.original_record_ids,
            "restored_record_ids": self.restored_record_ids,
            "failure_note": self.failure_note,
            "readiness": self.readiness.to_dict() if self.readiness else None,
            "steps": [s.to_dict() for s in self.steps],
        }


def blank_run(**overrides) -> ProofRun:
    """A run in which nothing has been performed.

    This is what the report generator produces when it runs anywhere other than
    Mike's machine -- which, for this mission, is everywhere. Section 4.5: "If
    you cannot run the rehearsal on Mike's machine, the report must still be
    generated in template form with every step marked UNVERIFIED and the exact
    commands Mike runs to execute each step."
    """
    steps = [
        StepResult(
            number=d.number,
            title=d.title,
            performer=NOT_PERFORMED,
            status="ABSENT",
            note=d.note,
        )
        for d in PROOF_PATH
    ]
    return ProofRun(steps=steps, **overrides)


# --------------------------------------------------------------------------- evidence


def collect_evidence_hashes(load_id: str) -> dict[str, dict]:
    """SHA-256 of every evidence file attached to a load, by evidence id.

    Reuses ``dispatch.backup.sha256_file`` rather than growing a second hashing
    implementation -- one hash function, one answer.

    A file recorded in the database but missing on disk is reported with
    ``status="ABSENT"`` and no hash, never skipped: a missing evidence file is
    the single most important thing a persistence proof can tell you, and a
    generator that quietly omitted it would produce a report that looked clean.
    """
    from dispatch import store
    from dispatch.backup import sha256_file

    out: dict[str, dict] = {}
    for ev in store.list_evidence(load_id):
        path = Path(ev.get("file_path") or "")
        entry = {
            "evidence_id": ev["evidence_id"],
            "original_filename": ev.get("original_filename", ""),
            "file_path": str(path),
            "recorded_checksum": ev.get("checksum", ""),
        }
        if path and path.is_file():
            entry["sha256"] = sha256_file(path)
            entry["size"] = path.stat().st_size
            entry["status"] = "CONFIGURED"
        else:
            entry["sha256"] = ""
            entry["size"] = 0
            entry["status"] = "ABSENT"
        out[ev["evidence_id"]] = entry
    return out


def compare_hashes(original: dict[str, dict], restored: dict[str, dict]) -> dict:
    """Side-by-side comparison for Section 4.5's "original vs restored" table."""
    rows = []
    identical = True
    for evidence_id in sorted(set(original) | set(restored)):
        a = original.get(evidence_id, {})
        b = restored.get(evidence_id, {})
        match = bool(a.get("sha256")) and a.get("sha256") == b.get("sha256")
        identical = identical and match
        rows.append(
            {
                "evidence_id": evidence_id,
                "original_sha256": a.get("sha256", ""),
                "restored_sha256": b.get("sha256", ""),
                "original_status": a.get("status", "ABSENT"),
                "restored_status": b.get("status", "ABSENT"),
                "match": match,
            }
        )
    return {"rows": rows, "identical": identical and bool(rows)}


def collect_record_ids(load_id: str) -> dict[str, list[str]]:
    """Every identifier the proof compares across the restart and the restore."""
    from dispatch import store

    load = store.get_load(load_id)
    return {
        "loads": [load["load_id"]] if load else [],
        "drivers": [load["driver_id"]] if load and load.get("driver_id") else [],
        "equipment": [load["equipment_id"]] if load and load.get("equipment_id") else [],
        "milestones": [m["milestone_id"] for m in store.list_milestones(load_id)],
        "evidence": [e["evidence_id"] for e in store.list_evidence(load_id)],
        "exceptions": [e["exception_id"] for e in store.list_exceptions(load_id=load_id)],
        "pod_packages": [p["pod_id"] for p in store.list_pods(load_id)],
    }


def compare_record_ids(original: dict, restored: dict) -> dict:
    """Which identifiers survived, which did not, and which appeared from nowhere."""
    rows = []
    identical = True
    for table in sorted(set(original) | set(restored)):
        a = sorted(original.get(table, []))
        b = sorted(restored.get(table, []))
        match = a == b
        identical = identical and match
        rows.append(
            {
                "table": table,
                "original": a,
                "restored": b,
                "missing": [x for x in a if x not in b],
                "unexpected": [x for x in b if x not in a],
                "match": match,
            }
        )
    return {"rows": rows, "identical": identical}


# --------------------------------------------------------------------------- report


def _fmt(value: str) -> str:
    return value if value else "—"


def render_proof_report(run: ProofRun) -> str:
    """The Section 4.5 document, as Markdown."""
    by_number = {d.number: d for d in PROOF_PATH}
    performed_by_mike = [s for s in run.steps if s.performer == "Mike"]
    performed_by_code = [s for s in run.steps if s.performer == "Code-automated"]
    unperformed = [s for s in run.steps if not s.performed]

    L: list[str] = []
    L.append(f"# {run.headline}")
    L.append("")
    L.append("# Dispatch — Operational Load Proof")
    L.append("")
    L.append("**Generated by:** Claude Code (implementation engineer)  ")
    L.append(f"**Generated at:** {run.generated_at}  ")
    L.append(f"**Machine:** {run.machine}  ")
    L.append(f"**Application version:** {run.identity.get('version', 'UNVERIFIED')}  ")
    L.append(f"**Application commit:** {run.identity.get('commit', 'UNVERIFIED')}  ")
    L.append(
        f"**Rehearsal session:** "
        f"{_fmt(run.rehearsal_session_id)}"
        f"{' · ' + run.rehearsal_session_label if run.rehearsal_session_label else ''}"
    )
    L.append("")
    L.append(
        "> This document reports whether a load moved through Dispatch **on Mike's own "
        "machine**. Repository test results are evidence of software behaviour and are "
        "deliberately not cited here as operational proof (mission Section 1.9)."
    )
    if run.failure_note:
        L.append("")
        L.append(f"> **Note:** {run.failure_note}")
    L.append("")

    # ── Section 4.5 required content ──
    L.append("## What Mike personally performed")
    L.append("")
    if performed_by_mike:
        for s in performed_by_mike:
            L.append(f"- **Step {s.number}** — {s.title} ({s.status}, {_fmt(s.timestamp)})")
    else:
        L.append("Nothing. `ABSENT` — no step of this path has been performed by Mike.")
    L.append("")

    L.append("## What Code verified automatically")
    L.append("")
    if performed_by_code:
        for s in performed_by_code:
            L.append(f"- **Step {s.number}** — {s.title} ({s.status}, {_fmt(s.timestamp)})")
    else:
        L.append("Nothing. `ABSENT` — no step of this path has been executed by tooling.")
    L.append("")

    L.append("## What remains UNVERIFIED")
    L.append("")
    if unperformed:
        L.append(
            f"{len(unperformed)} of {len(run.steps)} steps. Each is listed below with the "
            f"exact command that performs it."
        )
    else:
        L.append("Nothing — every step was performed.")
    L.append("")

    L.append("## Paths")
    L.append("")
    L.append("| Path | Value |")
    L.append("|---|---|")
    for label in (
        "database",
        "evidence store",
        "backup destination",
        "restore destination",
    ):
        L.append(f"| {label.title()} | `{_fmt(run.paths.get(label, ''))}` |")
    L.append("")

    L.append("## Outlook interaction")
    L.append("")
    L.append(
        f"**{run.outlook_status}** — Outlook is the single source of scheduling truth "
        f"(mission Section 1.5). Dispatch evaluates fit and presents schedule information; "
        f"it does not create a second scheduling truth, and it creates no calendar event "
        f"without human authorization."
    )
    L.append("")

    L.append("## The proof path")
    L.append("")
    L.append("| # | Step | Performer | Status | Timestamp | Records | Result |")
    L.append("|---|---|---|---|---|---|---|")
    for s in run.steps:
        ids = ", ".join(
            f"{k}={v}" for k, v in sorted(s.record_ids.items()) if v
        ) or "—"
        L.append(
            f"| {s.number} | {s.title} | {s.performer} | `{s.status}` | "
            f"{_fmt(s.timestamp)} | {ids} | {_fmt(s.result)} |"
        )
    L.append("")

    L.append("### Commands")
    L.append("")
    L.append("The exact action that performs each step, for the steps not yet performed.")
    L.append("")
    for s in run.steps:
        d = by_number[s.number]
        marker = "" if s.performed else "  ← not performed"
        L.append(f"**{s.number}. {s.title}**{marker}")
        L.append("")
        L.append("```")
        L.append(d.command)
        L.append("```")
        if d.note:
            L.append(f"*{d.note}*")
        L.append("")

    L.append("## Record identifiers — original vs restored")
    L.append("")
    if run.original_record_ids or run.restored_record_ids:
        comparison = compare_record_ids(run.original_record_ids, run.restored_record_ids)
        L.append("| Table | Original | Restored | Missing | Unexpected | Match |")
        L.append("|---|---|---|---|---|---|")
        for row in comparison["rows"]:
            L.append(
                f"| {row['table']} | {len(row['original'])} | {len(row['restored'])} | "
                f"{', '.join(row['missing']) or '—'} | "
                f"{', '.join(row['unexpected']) or '—'} | "
                f"{'yes' if row['match'] else '**no**'} |"
            )
        L.append("")
        L.append(
            f"**Identical:** {'yes' if comparison['identical'] else 'no'}"
        )
    else:
        L.append("`ABSENT` — no records were created, so none were compared.")
    L.append("")

    L.append("## Evidence hashes — original vs restored")
    L.append("")
    if run.evidence_hashes or run.restored_evidence_hashes:
        comparison = compare_hashes(run.evidence_hashes, run.restored_evidence_hashes)
        L.append("| Evidence ID | Original SHA-256 | Restored SHA-256 | Match |")
        L.append("|---|---|---|---|")
        for row in comparison["rows"]:
            L.append(
                f"| `{row['evidence_id']}` | `{_fmt(row['original_sha256'])}` | "
                f"`{_fmt(row['restored_sha256'])}` | "
                f"{'yes' if row['match'] else '**no**'} |"
            )
        L.append("")
        L.append(f"**Identical:** {'yes' if comparison['identical'] else 'no'}")
    else:
        L.append("`ABSENT` — no evidence files were uploaded, so none were hashed.")
    L.append("")

    if run.readiness is not None:
        L.append("## Readiness checks (Section 4.4)")
        L.append("")
        L.append("| Check | Status | Detail |")
        L.append("|---|---|---|")
        for c in run.readiness.checks:
            L.append(f"| {c.name} | `{c.status}` | {c.detail} |")
        L.append("")

    L.append("---")
    L.append("")
    L.append(
        "*Nothing in this report is accepted doctrine or a Mike decision. No record here "
        "bears a Mike attribution that was not produced by an explicit authenticated human "
        "action.*"
    )
    L.append("")
    return "\n".join(L)


def write_proof_report(run: ProofRun, path: Path | str) -> Path:
    """Write the Markdown report and its machine-readable sibling."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_proof_report(run), encoding="utf-8")
    p.with_suffix(".json").write_text(
        json.dumps(run.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
    )
    return p


def template_run(
    *, backup_destination: str = "", restore_destination: str = ""
) -> ProofRun:
    """A blank run with this machine's real paths filled in.

    The paths are real because they are the ones Dispatch would use; every step
    is `ABSENT` because none of them has been performed. That combination is the
    honest artifact: it tells Mike exactly where his data will go and exactly
    how much of the proof still owes him a run.
    """
    live = live_paths()
    run = blank_run()
    run.paths = {
        "database": str(live["database directory"]),
        "evidence store": str(live["evidence store"]),
        "backup destination": backup_destination,
        "restore destination": restore_destination,
    }
    return run


# --------------------------------------------------------------------------- automation


#: The milestone sequence a load walks, in the order Section 4.3 step 11 names
#: them: arrival, pickup, departure, delivery. `dispatched` and `en_route_pickup`
#: come first because dispatch/services.py::_VALID_TRANSITIONS refuses to jump
#: from `created` straight to `at_pickup` -- the gate is doing its job, so the
#: rehearsal walks the states rather than working around them.
REHEARSAL_MILESTONES = (
    "dispatched",
    "en_route_pickup",
    "arrived_pickup",
    "loaded",
    "departed_pickup",
    "in_transit",
    "arrived_delivery",
    "delivered",
)

#: Steps the automated rehearsal cannot perform, and why. Each stays
#: `not performed` / `ABSENT` in the resulting report, with its command printed.
NOT_AUTOMATABLE = {
    1: "Starting the server is a launcher action on Mike's machine.",
    2: "Authentication is a human action at the browser.",
    9: "Outlook is the single source of scheduling truth and Dispatch creates no event "
       "without human authorization.",
    10: "Receiving the mission happens on the driver's phone.",
    16: "Stopping the server is a launcher action on Mike's machine.",
    17: "Restarting the server is a launcher action on Mike's machine.",
}


def _set(run: ProofRun, number: int, **fields) -> StepResult:
    step = next(s for s in run.steps if s.number == number)
    for k, v in fields.items():
        setattr(step, k, v)
    step.__post_init__()
    return step


def _read_back(database_path, load_id: str) -> tuple[dict, dict]:
    """Collect record ids and evidence hashes from a RESTORED database.

    Points ``dispatch.db`` at the restored file for the duration of the read
    and puts it back afterwards, in a ``finally`` so a failure mid-read cannot
    leave the process pointed at a restore destination -- which would be the
    worst possible outcome of a verification step, since every subsequent write
    would land in the copy instead of the live database.
    """
    from dispatch import db as dispatch_db

    if database_path is None:
        return {}, {}
    # Save the OVERRIDE, not the resolved path. set_db_path(get_db_path())
    # would look like a restore and would in fact pin a path that was
    # previously being resolved from the environment on every call.
    previous = dispatch_db._db_path_override
    dispatch_db.set_db_path(Path(database_path))
    try:
        return collect_record_ids(load_id), collect_evidence_hashes(load_id)
    finally:
        dispatch_db.set_db_path(previous)


def automated_rehearsal(
    *,
    actor_id: str,
    label: str,
    backup_destination: Path | str | None = None,
    restore_destination: Path | str | None = None,
    customer: str = "REHEARSAL — not a live customer",
    equipment_type: str = "dry_van",
    pickup_location: str = "Kansas City, MO",
    delivery_location: str = "Denver, CO",
) -> ProofRun:
    """Walk every step of the proof path that does not need a human or a browser.

    This exists so the *machinery* of the proof -- rehearsal tagging, the
    milestone gate, evidence hashing, backup, restore, and the record comparison
    -- is exercised rather than merely written. It is explicitly **not** the
    operational proof: the six steps in ``NOT_AUTOMATABLE`` are exactly the ones
    that make a proof operational, and every one of them stays `ABSENT` here.
    That is why a run produced by this function can never print
    **REHEARSAL PASSED** -- ``ProofRun.headline`` requires every step performed
    *and* a named machine, and this function names neither.

    ``actor_id`` is required and is the authenticated account performing the
    rehearsal. It is never defaulted and never Mike unless Mike is the one
    running it (mission Section 1.1).
    """
    from dispatch import rehearsal, services, store
    from dispatch.backup import create_backup, restore, verify

    session = rehearsal.start_session(label=label, actor_id=actor_id, note="automated rehearsal")
    run = template_run(
        backup_destination=str(backup_destination or ""),
        restore_destination=str(restore_destination or ""),
    )
    run.rehearsal_session_id = session["session_id"]
    run.rehearsal_session_label = session["label"]

    for number, why in NOT_AUTOMATABLE.items():
        _set(run, number, note=why)

    try:
        with rehearsal.rehearsal_mode(session["session_id"]):
            driver = services.create_driver(
                name="REHEARSAL Driver", license_number="REHEARSAL-0000", phone="555-0100"
            )
            _set(run, 3, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"driver_id": driver["driver_id"]},
                 result="created")

            truck = services.create_equipment(
                unit_number="REHEARSAL-1", equipment_type=equipment_type
            )
            _set(run, 4, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"equipment_id": truck["equipment_id"]},
                 result="created")

            load = services.create_load(
                customer=customer,
                pickup_location=pickup_location,
                delivery_location=delivery_location,
                notes="Created by the automated rehearsal. Not a live mission.",
            )
            load_id = load["load_id"]
            _set(run, 5, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"load_id": load_id}, result="created")

            services.assign_driver(load_id, driver["driver_id"])
            _set(run, 6, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"load_id": load_id,
                                               "driver_id": driver["driver_id"]},
                 result="assigned")

            services.assign_equipment(load_id, truck["equipment_id"])
            _set(run, 7, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"load_id": load_id,
                                               "equipment_id": truck["equipment_id"]},
                 result="assigned")

            # Step 8 -- the human decision. Recorded as a load activity naming
            # the account that performed it and carrying the REHEARSAL label in
            # the message body, so the record itself says what it is. The actor
            # is never Mike unless Mike is the account running this: Section 1.1
            # forbids Dispatch writing a Mike attribution on its own, and this
            # is the one step where it would be easiest to.
            decision = services.add_activity(
                load_id,
                message=(
                    f"REHEARSAL — pursuit decision recorded by {actor_id} during "
                    f"rehearsal session {session['session_id']}. Not a live authorization."
                ),
                activity_type="status_change",
                author=f"{actor_id} (REHEARSAL)",
                source="user",
            )
            _set(run, 8, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(),
                 record_ids={"load_id": load_id, "activity_id": decision["activity_id"]},
                 result=f"recorded against {actor_id}, labeled REHEARSAL")

            milestone_ids = []
            for event_type in REHEARSAL_MILESTONES:
                ms = services.add_milestone(
                    load_id, event_type, location=pickup_location,
                    source="driver", entered_by=f"{actor_id} (REHEARSAL)",
                )
                milestone_ids.append(ms["milestone_id"])
            _set(run, 11, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(),
                 record_ids={"milestones": f"{len(milestone_ids)} recorded"},
                 result=", ".join(REHEARSAL_MILESTONES))

            pickup_evidence = services.attach_evidence(
                load_id, evidence_type="photo",
                description="REHEARSAL pickup evidence",
                uploaded_by=f"{actor_id} (REHEARSAL)",
                file_data=b"REHEARSAL pickup evidence -- not a real document.",
                original_filename="rehearsal_pickup.txt",
            )
            _set(run, 12, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(),
                 record_ids={"evidence_id": pickup_evidence["evidence_id"]},
                 result="uploaded and hashed")

            exception = services.open_exception(
                load_id, exception_type="delay", severity="low",
                description="REHEARSAL exception — exercising the path only.",
            )
            services.resolve_exception(
                exception["exception_id"], resolution_note="REHEARSAL — resolved."
            )
            _set(run, 13, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(),
                 record_ids={"exception_id": exception["exception_id"]},
                 result="opened and resolved")

            pod_evidence = services.attach_evidence(
                load_id, evidence_type="pod",
                description="REHEARSAL proof of delivery",
                uploaded_by=f"{actor_id} (REHEARSAL)",
                file_data=b"REHEARSAL POD -- not a real signature.",
                original_filename="rehearsal_pod.txt",
            )
            pod = services.generate_pod(
                load_id, recipient="REHEARSAL", notes="Automated rehearsal.",
                evidence_ids=[pod_evidence["evidence_id"]],
            )
            _set(run, 14, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(),
                 record_ids={"evidence_id": pod_evidence["evidence_id"],
                             "pod_id": pod["pod_id"]},
                 result="uploaded and packaged")

            final = store.get_load(load_id)
            _set(run, 15, performer="Code-automated", status="CONFIGURED",
                 timestamp=_now(), record_ids={"load_id": load_id},
                 result=f"status={final['status']}")

        # Outside the rehearsal context: the verification steps read, they do
        # not create, so nothing they touch needs a rehearsal tag.
        run.evidence_hashes = collect_evidence_hashes(load_id)
        run.original_record_ids = collect_record_ids(load_id)
        _set(run, 18, performer="Code-automated", status="CONFIGURED", timestamp=_now(),
             record_ids={"load_id": load_id},
             result=f"{len(run.original_record_ids['evidence'])} evidence file(s) hashed; "
                    f"records captured for comparison",
             note="Captured in-process. A restart across steps 16-17 has NOT been performed, "
                  "so persistence across a real process restart remains ABSENT.")

        if backup_destination:
            result = create_backup(destination=backup_destination)
            _set(run, 19, performer="Code-automated", status="CONFIGURED", timestamp=_now(),
                 record_ids={"archive": str(result.archive_path)},
                 result=f"{result.file_count} file(s), {result.total_bytes} bytes")

            if restore_destination:
                verify(result.archive_path)
                restored = restore(result.archive_path, destination=restore_destination)
                # Read the restored copy back and compare it to the original,
                # rather than trusting that a restore which raised nothing
                # produced the same bytes. Section 0: a statement that something
                # works is not proof.
                run.restored_record_ids, run.restored_evidence_hashes = _read_back(
                    restored.database_path, load_id
                )
                hashes = compare_hashes(run.evidence_hashes, run.restored_evidence_hashes)
                records = compare_record_ids(run.original_record_ids, run.restored_record_ids)
                matched = hashes["identical"] and records["identical"]
                _set(run, 20, performer="Code-automated",
                     status="CONFIGURED" if matched else "UNAVAILABLE",
                     timestamp=_now(),
                     record_ids={"destination": str(restored.destination)},
                     result=(
                         "verified, restored into an isolated destination, and compared: "
                         f"record identifiers {'match' if records['identical'] else 'DIFFER'}, "
                         f"evidence hashes {'match' if hashes['identical'] else 'DIFFER'}"
                     ))

        rehearsal.close_session(
            session["session_id"], result="PASSED", actor_id=actor_id,
            note="Automated portion completed. The operational steps remain ABSENT.",
        )
    except Exception as exc:
        failed = next((s for s in run.steps if s.performer == NOT_PERFORMED
                       and s.number not in NOT_AUTOMATABLE), None)
        if failed is not None:
            _set(run, failed.number, performer="Code-automated", status="UNAVAILABLE",
                 timestamp=_now(), result=f"{exc.__class__.__name__}: {exc}")
        run.failure_note = f"The automated rehearsal stopped: {exc.__class__.__name__}: {exc}"
        rehearsal.close_session(
            session["session_id"], result="FAILED", actor_id=actor_id, note=str(exc)
        )

    run.readiness = None
    return run
