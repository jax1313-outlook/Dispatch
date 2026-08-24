"""The status screen: every line an observation, none of them a default.

The mission lists what has to be displayed. The discipline behind each line is
the same: it is either a value read from the runtime this moment, or one of the
program's fixed truth words saying it could not be established. There is no third
category. A status screen that prints a plausible number it did not read is worse
than one that prints UNVERIFIED, because the operator cannot tell the difference.

Two lines deserve their own note.

*Secrets.* The screen names the setting and never its value -- "PORTAL_SECRET_KEY
is not set", never the key. It also distinguishes "this would prevent Dispatch
from starting" (operational mode) from "this is a warning" (development mode),
because those call for different actions.

*Backups.* The screen reports when the last backup was taken and where it is, and
refuses to call it good. See `dispatch_launcher.backups` for why: without a
restore verification record, a backup is a hypothesis, and the launcher says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dispatch_launcher import backups, control, locations, probe, processes
from dispatch_launcher.backups import BackupStatus
from dispatch_launcher.probe import RuntimeFacts
from dispatch_launcher.processes import ProcessFacts

RUNNING = "RUNNING"
STOPPED = "STOPPED"

_INDENT = "    "
_LABEL_WIDTH = 22


@dataclass
class LauncherStatus:
    runtime: RuntimeFacts
    ownership: control.Ownership
    backup: BackupStatus
    orphans: list[ProcessFacts] | None = None
    port_answering: bool = False
    last_failure: dict | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def running(self) -> bool:
        return self.ownership.running

    @property
    def pid(self) -> int | None:
        return self.ownership.pid if self.ownership.running else None


def collect_status(*, facts: RuntimeFacts | None = None) -> LauncherStatus:
    """Take one reading of everything. Creates nothing and changes nothing."""
    facts = facts or probe.probe_runtime()
    ownership = control.inspect_pidfile()

    port_answering = False
    if facts.port is not None and facts.host != probe.UNVERIFIED:
        port_answering = processes.port_in_use(facts.host, facts.port)

    # Only look for orphans when there is a reason to: something is answering on
    # the port but the launcher has no server of its own, or the record is stale.
    orphans: list[ProcessFacts] | None = None
    if not ownership.running and (port_answering or ownership.state != control.NO_RECORD):
        orphans = processes.find_portal_processes()

    return LauncherStatus(
        runtime=facts,
        ownership=ownership,
        backup=backups.backup_status(facts.backup_dir),
        orphans=orphans,
        port_answering=port_answering,
        last_failure=control.read_failure(),
    )


def _line(label: str, value: object) -> str:
    return f"{_INDENT}{label:<{_LABEL_WIDTH}}{value}"


def _secrets_lines(facts: RuntimeFacts) -> list[str]:
    if not facts.weak_secret_names:
        return [_line("Security settings", "CONFIGURED - required settings have real values")]
    names = ", ".join(facts.weak_secret_names)
    if facts.secrets_block_start:
        return [
            _line("Security settings", f"UNCONFIGURED - {names}"),
            _line("", "Dispatch will refuse to start until this is set."),
        ]
    return [
        _line("Security settings", f"UNCONFIGURED - {names}"),
        _line("", "Development mode allows this. Never expose this machine."),
    ]


def _backup_lines(status: BackupStatus) -> list[str]:
    lines = [_line("Backup", status.state)]
    if status.created_at:
        source = f" (from {status.created_at_source})" if status.created_at_source else ""
        lines.append(_line("Last backup taken", f"{status.created_at}{source}"))
    if status.location:
        lines.append(_line("Backup location", status.location))
    if status.state == backups.VERIFIED and status.verification:
        verified_at = status.verification.get("verified_at") or "no date recorded"
        lines.append(_line("Restore verified", verified_at))
    lines.append(_line("", status.detail))
    return lines


def render(status: LauncherStatus) -> str:
    """The whole status block, as printed by the menu and by `--status`."""
    facts = status.runtime
    lines: list[str] = []

    lines.append("  DISPATCH - Operations Control")
    lines.append("")

    if status.running:
        lines.append(_line("Dispatch", f"{RUNNING} - process ID {status.pid}"))
    else:
        lines.append(_line("Dispatch", STOPPED))
    if status.ownership.state not in (control.RUNNING, control.NO_RECORD):
        lines.append(_line("", status.ownership.explanation))
    if status.port_answering and not status.running:
        lines.append(_line(
            "",
            f"Something is already answering on port {facts.port}, but this launcher "
            "did not start it.",
        ))
    if status.orphans:
        for orphan in status.orphans:
            lines.append(_line(
                "Unclaimed process",
                f"process ID {orphan.pid} looks like a Dispatch server this launcher "
                "did not start",
            ))
    elif status.orphans is None and not status.running and status.port_answering:
        lines.append(_line("Unclaimed process", processes.UNAVAILABLE))

    lines.append("")
    lines.append(_line("Version", f"{facts.version} ({facts.version_source})"))
    lines.append(_line("Commit", f"{facts.commit}"))
    if facts.commit == probe.UNVERIFIED:
        lines.append(_line("", facts.commit_source))
    lines.append(_line("Portal address", facts.url))
    if facts.host_pinned:
        lines.append(_line(
            "",
            f"Requested {facts.requested_host}, pinned to {facts.host} because Dispatch "
            "is in development mode.",
        ))
    lines.append(_line("Mode", facts.mode))
    if facts.dispatch_mode_setting:
        lines.append(_line("", f"DISPATCH_MODE={facts.dispatch_mode_setting}"))
    else:
        lines.append(_line("", "DISPATCH_MODE is not set; Dispatch defaults to operational."))
    lines.extend(_secrets_lines(facts))

    lines.append("")
    lines.append(_line("Database", facts.database_path))
    lines.append(_line("Portal data", facts.portal_data_dir))
    lines.append(_line("Operations root", facts.operations_root or "UNCONFIGURED - using defaults"))
    lines.append(_line("Archive root", facts.archive_root or "UNCONFIGURED - using defaults"))
    lines.append(_line("Memory root", facts.memory_root or "UNCONFIGURED - using defaults"))
    lines.append(_line("Contract archive", facts.contract_archive_root))

    lines.append("")
    lines.extend(_backup_lines(status.backup))

    lines.append("")
    lines.append(_line("Logs", locations.logs_dir()))
    if status.last_failure:
        lines.append(_line(
            "Last start failure",
            f"{status.last_failure.get('recorded_at', 'no date recorded')}",
        ))
        lines.append(_line("", status.last_failure.get("message", "")))
    else:
        lines.append(_line("Last start failure", "ABSENT - no failure recorded"))

    for error in facts.errors:
        lines.append(_line("Configuration", f"UNAVAILABLE - {error}"))
    for note in status.notes:
        lines.append(_line("", note))

    return "\n".join(lines)
