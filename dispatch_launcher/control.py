"""Start, Stop, Restart, Open -- the four operations, and the safety around them.

The mission's process-safety requirements are the whole design of this module,
and each is implemented as a real check rather than an intention:

*Start creates exactly one server process.* Start first establishes ownership
(below), and returns "already running" without spawning anything when a server it
can positively identify is alive. It also refuses when something else is already
listening on the configured port, which is the common real-world cause of a
duplicate: a server orphaned by a closed console window.

*Stop confirms the process is gone.* A delivered signal is not a stopped server.
Stop polls the PID until the operating system stops reporting it, escalates once
if the process ignores a graceful request, polls again, and reports failure --
with what to do about it -- if the process is still there.

*Restart proves the first process is dead before starting the second.* If Stop
cannot confirm the old process is gone, Restart does not start a new one. Two
Dispatch servers against one SQLite file is a data-integrity event, not an
inconvenience.

*Orphans are detected, not overwritten.* A PID file whose process is dead is
cleared with a note. A PID file whose PID is alive but is somebody else's program
is treated as stale, not as a target. A PID that is alive but whose identity the
platform will not confirm stops the launcher from acting at all -- see
`inspect_pidfile`.

*Failures are reported in plain language.* The stack trace goes to the log; what
Mike reads is a sentence. `describe_failure` translates the handful of causes
that actually happen, and says "the full error is in <path>" for the rest rather
than inventing a diagnosis.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from dispatch_launcher import locations, pidfile, probe, processes, redaction
from dispatch_launcher.pidfile import PidRecord
from dispatch_launcher.probe import RuntimeFacts
from dispatch_launcher.processes import ProcessFacts

# ── ownership states ───────────────────────────────────────────────────

#: A live process this launcher started, positively identified.
RUNNING = "RUNNING"
#: No PID file, or one that could not be read as a record.
NO_RECORD = "ABSENT"
#: A PID file naming a process that no longer exists.
STALE_DEAD = "STALE_DEAD"
#: A PID file naming a live process that is demonstrably not our server.
STALE_FOREIGN = "STALE_FOREIGN"
#: A PID file naming a live process whose identity the platform will not confirm.
UNCONFIRMED = "UNVERIFIED"

#: How long a freshly started server gets to answer on its port before the
#: launcher stops waiting and says so.
#: The variable dispatch/rehearsal.py reads to decide whether records created
#: now are rehearsal records. Duplicated here as a literal rather than imported:
#: the launcher must not import any dispatch.* application module, and
#: tests/test_launcher.py::TestNoPathToCurrentReality enforces that. A test
#: below pins the two spellings together so a rename cannot silently break this.
REHEARSAL_ENV_VAR = "DISPATCH_REHEARSAL_SESSION"

SETTLE_SECONDS = 10.0
#: How long a graceful stop is given before escalating, and again after.
STOP_TIMEOUT_SECONDS = 10.0
FORCE_TIMEOUT_SECONDS = 5.0
#: How much of the server log is read when explaining a failed start.
LOG_TAIL_BYTES = 8000


@dataclass(frozen=True)
class Ownership:
    state: str
    explanation: str
    record: PidRecord | None = None
    facts: ProcessFacts | None = None

    @property
    def running(self) -> bool:
        return self.state == RUNNING

    @property
    def pid(self) -> int | None:
        return self.record.pid if self.record else None


@dataclass
class ControlResult:
    action: str
    ok: bool
    message: str
    details: list[str] = field(default_factory=list)
    pid: int | None = None


def inspect_pidfile(path: Path | None = None) -> Ownership:
    """Decide what the PID file actually proves, right now.

    Identity is established by agreement between what was recorded at start time
    and what the operating system reports now. The creation token is the stronger
    of the two signals -- a recycled PID always has a different one -- so when
    both are available both must agree. When only one is available it is used
    alone and the weaker basis is stated in the explanation, because an operator
    is entitled to know how sure the launcher is.
    """
    record = pidfile.read_record(path)
    if record is None:
        return Ownership(
            state=NO_RECORD,
            explanation="No launcher record of a running Dispatch server.",
        )

    facts = processes.process_facts(record.pid)
    if not facts.alive:
        return Ownership(
            state=STALE_DEAD,
            explanation=(
                f"The launcher's record names process ID {record.pid}, which is no "
                "longer running. Dispatch stopped without the record being cleared, "
                "which usually means the window was closed or the machine lost power."
            ),
            record=record,
            facts=facts,
        )

    checks: list[bool] = []
    basis: list[str] = []
    if record.created_token and facts.created_token:
        checks.append(record.created_token == facts.created_token)
        basis.append("process start time")
    if record.command_line and facts.command_line:
        checks.append(record.command_line == facts.command_line)
        basis.append("command line")

    if not checks:
        # Liveness without identity. Refuse to treat it as ours -- and say why,
        # because the operator, unlike the launcher, can look at the process.
        if facts.looks_like_portal:
            return Ownership(
                state=UNCONFIRMED,
                explanation=(
                    f"Process ID {record.pid} is running and looks like a Dispatch "
                    "server, but this machine would not confirm its identity, so the "
                    "launcher will not act on it."
                ),
                record=record,
                facts=facts,
            )
        return Ownership(
            state=UNCONFIRMED,
            explanation=(
                f"Process ID {record.pid} is running but this machine would not report "
                "what it is, so the launcher cannot tell whether it is Dispatch."
            ),
            record=record,
            facts=facts,
        )

    if all(checks):
        return Ownership(
            state=RUNNING,
            explanation=(
                f"Process ID {record.pid} is the Dispatch server this launcher started "
                f"(confirmed by {' and '.join(basis)})."
            ),
            record=record,
            facts=facts,
        )

    return Ownership(
        state=STALE_FOREIGN,
        explanation=(
            f"Process ID {record.pid} is in use by a different program than the one the "
            "launcher started -- the operating system reuses process IDs. The old "
            "record is stale and Dispatch is not running."
        ),
        record=record,
        facts=facts,
    )


# ── logging ────────────────────────────────────────────────────────────

def log_action(message: str) -> None:
    """Append one redacted line to the launcher's own log.

    Never raises: a launcher that cannot write its log must still be able to
    start and stop the server.
    """
    try:
        locations.ensure_logs_dir()
        stamp = pidfile.utc_now()
        with locations.launcher_log().open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {redaction.redact_text(message)}\n")
    except OSError:
        pass


def read_log_tail(path: Path | None = None, *, limit: int = LOG_TAIL_BYTES) -> str:
    """The end of the server log, redacted.

    The portal writes this file itself, straight to the file descriptor the
    launcher hands it, so the launcher cannot redact on the way in without
    standing between the server and its own log -- which would mean losing output
    whenever the launcher process ends. It redacts on the way out instead: every
    path that displays or copies this text passes through here.
    """
    path = path or locations.server_log()
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > limit:
                handle.seek(size - limit)
            raw = handle.read()
    except OSError:
        return ""
    return redaction.redact_text(raw.decode("utf-8", "replace"))


def write_failure(action: str, message: str, *, detail: str = "") -> None:
    payload = {
        "recorded_at": pidfile.utc_now(),
        "action": action,
        "message": redaction.redact_text(message),
        "detail": redaction.redact_text(detail),
        "log": str(locations.server_log()),
    }
    try:
        locations.ensure_logs_dir()
        locations.failure_file().write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def read_failure() -> dict | None:
    try:
        data = json.loads(locations.failure_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def clear_failure() -> None:
    try:
        locations.failure_file().unlink()
    except OSError:
        pass


# ── plain-language failure translation ─────────────────────────────────

def describe_failure(log_text: str, facts: RuntimeFacts, *, exit_code: int | None) -> str:
    """One sentence an owner can act on, from whatever the server printed.

    Only causes that genuinely occur are translated. Everything else is reported
    as unrecognised, pointing at the log -- a launcher that guesses at a diagnosis
    sends the operator to fix the wrong thing.
    """
    lowered = log_text.lower()
    port = facts.port if facts.port is not None else "the configured port"

    if (
        "address already in use" in lowered
        or "only one usage of each socket address" in lowered
        or "winerror 10048" in lowered
        or "errno 98" in lowered
        or "errno 48" in lowered
    ):
        return (
            f"Dispatch could not start because port {port} is already in use. "
            "Another copy of Dispatch, or another program, is using it."
        )

    if "refusing to start:" in lowered or "insecureconfigurationerror" in lowered:
        names = ", ".join(facts.weak_secret_names) or "a required security setting"
        return (
            f"Dispatch could not start because {names} is not set. "
            "Set it to a real value before starting."
        )

    if "no module named 'flask'" in lowered or 'no module named "flask"' in lowered:
        return (
            "Dispatch could not start because the Flask package is not installed "
            "for this Python. Install it with: pip install -e ."
        )

    if "no module named" in lowered:
        return (
            "Dispatch could not start because a required Python package is missing. "
            f"The log names it: {locations.server_log()}"
        )

    if "permission denied" in lowered or "winerror 5" in lowered or "access is denied" in lowered:
        return (
            "Dispatch could not start because Windows refused permission for a file or "
            f"port it needs. The details are in {locations.server_log()}"
        )

    if "database is locked" in lowered:
        return (
            "Dispatch could not start because the database file is locked by another "
            "program. Close any other copy of Dispatch and try again."
        )

    code = "" if exit_code is None else f" (it exited with code {exit_code})"
    return (
        f"Dispatch could not start{code}, and the launcher does not recognise the "
        f"reason. The full error is in {locations.server_log()}"
    )


# ── the four operations ────────────────────────────────────────────────

def _spawn_command() -> list[str]:
    """The exact command that starts a Dispatch server.

    `portal/app.py` run as a script, which is the way the repository has always
    documented. (`run_portal.bat` used to do the same thing directly and no
    longer does: an unmanaged second front door on the same port produced a real
    orphan, so it hands over to the launcher instead.) The launcher does
    not import `portal.app` and does not construct the Flask app itself: a
    control that builds the application inside its own process is no longer a
    control, and would put the whole service layer one import away.
    """
    return [sys.executable, str(locations.repo_root() / "portal" / "app.py")]


def _creation_flags() -> int:
    """Windows: detach the server so closing the launcher window does not kill it.

    DETACHED_PROCESS gives the server no console of its own (its output is
    already going to the log file), and CREATE_NEW_PROCESS_GROUP keeps Ctrl+C in
    the launcher's console from reaching it. Both are looked up rather than
    written as literals so this module imports cleanly on POSIX, where neither
    constant exists.
    """
    if os.name != "nt":
        return 0
    detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
    new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    return detached | new_group


def start(
    *,
    facts: RuntimeFacts | None = None,
    settle_seconds: float = SETTLE_SECONDS,
) -> ControlResult:
    facts = facts or probe.probe_runtime()
    details: list[str] = []

    ownership = inspect_pidfile()
    if ownership.running:
        return ControlResult(
            action="start", ok=True, pid=ownership.pid,
            message=f"Dispatch is already running (process ID {ownership.pid}). Nothing was started.",
            details=[ownership.explanation],
        )
    if ownership.state == UNCONFIRMED:
        return ControlResult(
            action="start", ok=False, pid=ownership.pid,
            message=(
                "Dispatch was not started because the launcher cannot tell whether it is "
                "already running."
            ),
            details=[
                ownership.explanation,
                f"Check process ID {ownership.pid} in Task Manager. If it is not Dispatch, "
                f"delete {locations.pid_file()} and start again.",
            ],
        )
    if ownership.state in (STALE_DEAD, STALE_FOREIGN):
        pidfile.clear_record()
        details.append(ownership.explanation)
        details.append("The stale record was cleared.")
        log_action(f"cleared stale pid record: {ownership.explanation}")

    if facts.secrets_block_start:
        names = ", ".join(facts.weak_secret_names)
        message = (
            f"Dispatch cannot start because {names} is not set, and Dispatch is in "
            "operational mode. Set a real value for it and start again."
        )
        write_failure("start", message)
        return ControlResult(
            action="start", ok=False, message=message,
            details=details + [
                "The launcher reports the name of the setting only, never its value.",
                "Dispatch itself refuses to start on the published default from this "
                "repository, which anyone who can read the source already knows.",
            ],
        )

    if facts.port is None or facts.host == probe.UNVERIFIED:
        message = (
            "Dispatch cannot start because its address could not be read from the "
            "configuration."
        )
        write_failure("start", message, detail="; ".join(facts.errors))
        return ControlResult(action="start", ok=False, message=message, details=details + facts.errors)

    if processes.port_in_use(facts.host, facts.port):
        orphans = processes.find_portal_processes()
        if orphans is None:
            details.append(
                "The launcher could not ask this machine which program holds the port."
            )
        elif orphans:
            for orphan in orphans:
                details.append(
                    f"A Dispatch-looking process is running that this launcher did not "
                    f"start: process ID {orphan.pid}."
                )
            details.append(
                "This is most likely a server left over from a previous session whose "
                "window was closed. Stop it in Task Manager, then start Dispatch again."
            )
        message = (
            f"Dispatch could not start because port {facts.port} is already in use."
        )
        write_failure("start", message, detail="; ".join(details))
        return ControlResult(action="start", ok=False, message=message, details=details)

    log_dir = locations.ensure_logs_dir()
    log_path = locations.server_log()
    command = _spawn_command()

    child_environment = dict(os.environ)
    # Unbuffered, so a failure that happens in the first second is in the log by
    # the time the launcher reads it rather than sitting in a pipe buffer.
    child_environment["PYTHONUNBUFFERED"] = "1"

    log_action(
        f"starting: {' '.join(command)} | log={log_path} | "
        f"environment={json.dumps(redaction.redact_mapping({k: v for k, v in child_environment.items() if k.startswith(('DISPATCH_', 'PORTAL_'))}), sort_keys=True)}"
    )

    try:
        handle = log_path.open("a", encoding="utf-8")
    except OSError as exc:
        message = f"Dispatch could not start because its log file could not be opened: {exc}"
        write_failure("start", message)
        return ControlResult(action="start", ok=False, message=message, details=details)

    with handle:
        handle.write(f"\n===== Dispatch start {pidfile.utc_now()} =====\n")
        handle.flush()
        try:
            child = subprocess.Popen(  # noqa: S603 - fixed command, no shell
                command,
                cwd=str(locations.repo_root()),
                stdout=handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=child_environment,
                creationflags=_creation_flags(),
                start_new_session=(os.name != "nt"),
            )
        except OSError as exc:
            message = (
                f"Dispatch could not start because Python could not be run: {exc}"
            )
            write_failure("start", message)
            return ControlResult(action="start", ok=False, message=message, details=details)

    observed = processes.process_facts(child.pid)
    pidfile.write_record(PidRecord(
        pid=child.pid,
        recorded_at=pidfile.utc_now(),
        command=command,
        command_line=observed.command_line,
        created_token=observed.created_token,
        host=facts.host,
        port=facts.port,
        log_path=str(log_path),
    ))

    settled = _wait_for_settle(child, facts, settle_seconds)
    if settled == "exited":
        tail = read_log_tail(log_path)
        message = describe_failure(tail, facts, exit_code=child.returncode)
        write_failure("start", message, detail=_last_lines(tail))
        pidfile.clear_record()
        log_action(f"start failed: {message}")
        return ControlResult(
            action="start", ok=False, message=message,
            details=details + [f"The full output is in {log_path}"],
        )

    clear_failure()
    if settled == "listening":
        log_action(f"started: pid={child.pid} url={facts.url}")
        return ControlResult(
            action="start", ok=True, pid=child.pid,
            message=f"Dispatch is running (process ID {child.pid}) at {facts.url}",
            details=details + [f"Log directory: {log_dir}"],
        )

    log_action(f"started but not yet answering: pid={child.pid} url={facts.url}")
    return ControlResult(
        action="start", ok=True, pid=child.pid,
        message=(
            f"Dispatch was started (process ID {child.pid}) but has not answered on "
            f"{facts.url} yet."
        ),
        details=details + [
            "It may still be starting. Choose Status again in a moment to confirm.",
            f"If it never answers, the reason will be in {log_path}",
        ],
    )


def _wait_for_settle(child: subprocess.Popen, facts: RuntimeFacts, seconds: float) -> str:
    """Watch a freshly started server. Returns "exited", "listening" or "waiting"."""
    deadline = time.monotonic() + seconds
    while True:
        if child.poll() is not None:
            return "exited"
        if facts.port is not None and processes.port_in_use(facts.host, facts.port):
            return "listening"
        if time.monotonic() >= deadline:
            return "waiting"
        time.sleep(0.25)


def _last_lines(text: str, count: int = 5) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return "\n".join(lines[-count:])


def _stop_with_no_record_of_ours(*, found_none: bool) -> ControlResult:
    """Stop, when the launcher owns nothing -- reconciled against the port.

    **This is the repair for a contradiction an operator read on one screen.** The
    status block said *"Something is already answering on port 8080, but this
    launcher did not start it"*, and `[8] Stop Dispatch`, chosen seconds later,
    said *"Dispatch is not running. Nothing to stop."* Both sentences came from
    this program. The first is a port probe; the second was a process scan; nothing
    reconciled them, and the reassuring one is the one that answered the question
    he actually asked.

    "Nothing to stop" is now said only when nothing is listening. When something
    holds the address, Stop reports that it did not stop it -- and says whether the
    process scan came back empty or came back blind, because those call for
    different next steps.
    """
    facts = probe.probe_runtime()
    listening = (
        facts.port is not None
        and facts.host != probe.UNVERIFIED
        and processes.port_in_use(facts.host, facts.port)
    )
    if not listening:
        return ControlResult(
            action="stop", ok=True,
            message="Dispatch is not running. Nothing to stop.",
        )

    details = [
        f"Something is listening on {facts.host}:{facts.port}, and this launcher "
        "has no record of starting it.",
    ]
    if found_none:
        details.append(
            "No process on this machine looks like a Dispatch server, so the "
            "address is most likely held by another program."
        )
    else:
        details.append(
            "The launcher could not read this machine's process list, so it cannot "
            "say which program holds the address."
        )
    details.append(
        "Nothing was stopped. Find the program holding the address and close it, "
        "or restart the computer."
    )
    return ControlResult(
        action="stop", ok=False,
        message=(
            "Dispatch was not stopped: something is answering on its address that "
            "this launcher did not start."
        ),
        details=details,
    )


def stop(
    *,
    timeout: float = STOP_TIMEOUT_SECONDS,
    force_timeout: float = FORCE_TIMEOUT_SECONDS,
) -> ControlResult:
    ownership = inspect_pidfile()

    if ownership.state == NO_RECORD:
        orphans = processes.find_portal_processes()
        if orphans:
            return ControlResult(
                action="stop", ok=False,
                message=(
                    "Dispatch is not running under this launcher, but a Dispatch-looking "
                    "process is running that it did not start."
                ),
                details=[
                    f"Process ID {orphan.pid}" for orphan in orphans
                ] + [
                    "The launcher will not terminate a process it cannot prove it owns. "
                    "Stop it in Task Manager if it should not be running."
                ],
            )
        return _stop_with_no_record_of_ours(found_none=orphans is not None)

    if ownership.state == STALE_DEAD:
        pidfile.clear_record()
        return ControlResult(
            action="stop", ok=True,
            message="Dispatch was not running. The leftover record has been cleared.",
            details=[ownership.explanation],
        )

    if ownership.state == STALE_FOREIGN:
        pidfile.clear_record()
        return ControlResult(
            action="stop", ok=True,
            message=(
                "Dispatch was not running. A leftover record pointed at an unrelated "
                "program, which was left alone, and the record has been cleared."
            ),
            details=[ownership.explanation],
        )

    if ownership.state == UNCONFIRMED:
        return ControlResult(
            action="stop", ok=False, pid=ownership.pid,
            message=(
                "Dispatch was not stopped because the launcher cannot confirm which "
                "program holds that process ID."
            ),
            details=[
                ownership.explanation,
                f"Check process ID {ownership.pid} in Task Manager and stop it there if "
                "it is Dispatch.",
            ],
        )

    pid = ownership.pid
    assert pid is not None
    details = [ownership.explanation]

    if not processes.terminate(pid, force=False):
        details.append("The operating system refused the request to close the process.")
    if processes.wait_until_gone(pid, timeout):
        pidfile.clear_record()
        log_action(f"stopped: pid={pid}")
        return ControlResult(
            action="stop", ok=True, pid=pid,
            message=f"Dispatch has stopped. Process ID {pid} is gone.",
            details=details,
        )

    details.append(
        f"Process ID {pid} did not close within {timeout:.0f} seconds, so the launcher "
        "escalated to a forced stop."
    )
    processes.terminate(pid, force=True)
    if processes.wait_until_gone(pid, force_timeout):
        pidfile.clear_record()
        log_action(f"force-stopped: pid={pid}")
        return ControlResult(
            action="stop", ok=True, pid=pid,
            message=f"Dispatch has stopped. Process ID {pid} had to be forced, and is gone.",
            details=details,
        )

    message = (
        f"Dispatch did not stop. Process ID {pid} is still running after a forced stop."
    )
    write_failure("stop", message, detail="; ".join(details))
    log_action(f"stop failed: pid={pid} still alive")
    return ControlResult(
        action="stop", ok=False, pid=pid,
        message=message,
        details=details + [
            f"Open Task Manager, find process ID {pid}, and end it there.",
            "Do not start Dispatch again until it is gone: two servers sharing one "
            "database can corrupt it.",
        ],
    )


def restart(*, facts: RuntimeFacts | None = None) -> ControlResult:
    facts = facts or probe.probe_runtime()
    before = inspect_pidfile()
    previous_pid = before.pid if before.running else None

    stopped = stop()
    if not stopped.ok:
        return ControlResult(
            action="restart", ok=False, pid=stopped.pid,
            message=(
                "Dispatch was not restarted, because the running copy could not be "
                "confirmed stopped. Nothing new was started."
            ),
            details=[stopped.message] + stopped.details,
        )

    # The proof, not the assumption: the old process must be gone from the
    # operating system's own view before a new one is allowed to exist.
    if previous_pid is not None and processes.pid_alive(previous_pid):
        message = (
            f"Dispatch was not restarted: process ID {previous_pid} is still running. "
            "Nothing new was started."
        )
        write_failure("restart", message)
        return ControlResult(
            action="restart", ok=False, pid=previous_pid, message=message,
            details=[
                "Two Dispatch servers sharing one database can corrupt it, so the "
                "launcher will not start a second one.",
            ],
        )

    started = start(facts=facts)
    prefix = (
        f"Stopped process ID {previous_pid}." if previous_pid is not None
        else "Dispatch was not running."
    )
    return ControlResult(
        action="restart", ok=started.ok, pid=started.pid,
        message=f"{prefix} {started.message}",
        details=stopped.details + started.details,
    )


def reset_session(*, facts: RuntimeFacts | None = None) -> ControlResult:
    """Clear the launcher's own transient state so the next Start begins clean.

    What this clears, and nothing else:

    * a **stale PID record** -- one that names a process which is gone, or one
      the platform will not confirm is Dispatch. This is the thing that makes a
      launcher say "already running" about a machine where nothing is running.
    * the **last-failure record**, so an old error stops appearing on the status
      screen after it has been dealt with.
    * the **rehearsal binding** in this launcher's environment, so a Start after
      a reset produces live records rather than silently continuing to tag
      everything REHEARSAL because a variable was left set in this window.

    What it never touches: the database, evidence, the archive, the memory root,
    any load, milestone, driver, POD or rehearsal *record*, and the log files
    themselves. Nothing operational is deleted here, and there is no flag that
    makes it so -- purging rehearsal data is Mike's decision and lives in
    ``scripts/dispatch_proof.py``, which reports and refuses rather than deletes.

    **It refuses while Dispatch is running.** Deleting the PID record of a live
    server is precisely how an orphan is created: the process keeps holding the
    port, the launcher forgets it exists, and the next Start collides with
    something it can no longer identify or stop. Stop first, then reset.
    """
    facts = facts or probe.probe_runtime()
    ownership = inspect_pidfile()

    if ownership.state == RUNNING:
        return ControlResult(
            action="reset-session",
            ok=False,
            message=(
                f"Dispatch is running (process ID {ownership.pid}). Nothing was reset."
            ),
            details=[
                "Resetting now would discard the record of a live server and leave it "
                "orphaned -- still holding the port, no longer stoppable from here.",
                "Stop Dispatch first, then Reset Session.",
            ],
            pid=ownership.pid,
        )

    cleared: list[str] = []
    kept: list[str] = []

    if ownership.state == UNCONFIRMED:
        # A live process the platform will not identify. Clearing its record is
        # the same mistake as clearing a confirmed one, so it is refused too.
        return ControlResult(
            action="reset-session",
            ok=False,
            message="A process this launcher cannot identify is still alive. Nothing was reset.",
            details=[
                ownership.explanation,
                "Stop Dispatch first, or close that process yourself, then Reset Session.",
            ],
            pid=ownership.pid,
        )

    if ownership.state == NO_RECORD:
        kept.append("There was no process record to clear.")
    elif pidfile.clear_record():
        cleared.append(f"Cleared a stale process record ({ownership.explanation})")
    else:
        kept.append("A process record exists but could not be removed. Check the log directory.")

    if read_failure() is not None:
        clear_failure()
        cleared.append("Cleared the recorded last start failure")
    else:
        kept.append("There was no recorded failure to clear.")

    rehearsal = os.environ.pop(REHEARSAL_ENV_VAR, None)
    if rehearsal:
        cleared.append(
            f"Cleared the rehearsal binding in this window ({REHEARSAL_ENV_VAR}={rehearsal}). "
            f"The next Start will record live data."
        )
    else:
        kept.append("No rehearsal was bound in this window; records were already live.")

    log_action(f"reset-session: cleared {len(cleared)} item(s)")

    message = (
        "Session reset. Dispatch is stopped and the next Start begins clean."
        if cleared
        else "Nothing needed resetting. Dispatch is stopped and the session is already clean."
    )
    return ControlResult(
        action="reset-session",
        ok=True,
        message=message,
        details=[
            *cleared,
            *kept,
            "No load, milestone, driver, evidence file or database record was touched.",
        ],
    )


def open_portal(*, facts: RuntimeFacts | None = None) -> ControlResult:
    facts = facts or probe.probe_runtime()
    url = facts.url
    if url == probe.UNVERIFIED:
        return ControlResult(
            action="open", ok=False,
            message="The portal address could not be read from the configuration.",
            details=facts.errors,
        )

    ownership = inspect_pidfile()
    details = [f"Address: {url}"]
    if not ownership.running:
        details.append(
            "Dispatch does not appear to be running, so the page may not load. "
            "Use Start first."
        )

    try:
        opened = webbrowser.open(url)
    except Exception:  # pragma: no cover - platform browser launch failure
        opened = False

    if opened:
        return ControlResult(action="open", ok=True, message=f"Opened {url} in your browser.", details=details)
    return ControlResult(
        action="open", ok=False,
        message=f"The browser could not be opened automatically. Go to {url}",
        details=details,
    )
