"""The Settings and Version screens: what Dispatch is configured with, and how to change it.

**Settings shows configuration. It does not own any.** That distinction is the
whole design. Dispatch reads its configuration from environment variables, and
`setup_dispatch_folders.ps1` already persists them with `setx`. A launcher that
wrote its own settings file would create a second source of truth, and the first
time the two disagreed nobody would know which one the portal actually used --
which is exactly the failure the status screen exists to prevent. So this screen
reads what the portal would resolve right now, names where each value came from,
and prints the command that changes it. Mike runs the command; the launcher does
not.

Three rules hold on every row:

*A value or a truth word, never a plausible guess.* A setting that is not set
says `UNCONFIGURED` and shows the fallback the code would use instead. It does
not print the fallback as though it were the setting.

*Secrets by name, never by value.* `PORTAL_SECRET_KEY` is listed, its status is
reported, and its content never reaches the screen, the log, or the clipboard.
The screen distinguishes "this stops Dispatch starting" from "this is a warning
in development mode", because those need different actions from the operator.

*The change command is exact and is `setx`.* `set` lasts until the window
closes, which produces the most confusing possible bug: Dispatch works this
afternoon and is broken tomorrow. `setx` writes the registry, and the screen
says the part everyone forgets -- that a new value only reaches windows opened
after it.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field

from dispatch_launcher import locations, probe
from dispatch_launcher.probe import UNVERIFIED, RuntimeFacts

_INDENT = "    "

CONFIGURED = "CONFIGURED"
UNCONFIGURED = "UNCONFIGURED"


@dataclass
class SettingRow:
    """One environment variable, and everything an operator needs to act on it."""

    name: str
    status: str
    value: str
    purpose: str
    fallback: str = ""
    secret: bool = False
    blocks_start: bool = False
    #: Belongs to one window, not to the machine. See `change_command`.
    session_scoped: bool = False

    @property
    def displayed_value(self) -> str:
        if self.secret:
            # Named, never shown. There is no flag that reveals it.
            return "set (value not shown)" if self.status == CONFIGURED else "not set"
        return self.value or ""

    def change_command(self) -> str:
        """The command to change this setting -- and `set` is not a typo.

        Almost everything here describes the machine and belongs on it
        permanently, so `setx` is right. **Rehearsal mode does not.** It is
        switched on for an afternoon of testing and off again, and `setx` would
        put every future start in rehearsal mode -- including PILOT-01, whose
        one real load would then be recorded as a test. That is the exact
        failure rehearsal tagging exists to prevent, so this screen must not
        print the command that causes it.
        """
        example = "<value>" if not self.secret else "<a long random value you generate>"
        if self.session_scoped:
            # Both shells, because the wrong one fails quietly. In PowerShell
            # `set` is an alias for Set-Variable: it sets nothing Dispatch can
            # read, says nothing, and the records come out untagged.
            return (
                f'PowerShell:  $env:{self.name} = "<value>"'
                f"\n{' ' * 17}cmd:         set {self.name}=<value>"
                f"\n{' ' * 17}This window only. Never setx."
            )
        return f'setx {self.name} "{example}"'


@dataclass
class SettingsView:
    rows: list[SettingRow]
    facts: RuntimeFacts
    resolved: list[tuple[str, str]] = field(default_factory=list)

    @property
    def blocking(self) -> list[SettingRow]:
        return [r for r in self.rows if r.blocks_start and r.status != CONFIGURED]


def _env(name: str) -> tuple[str, str]:
    raw = os.environ.get(name)
    return (CONFIGURED, raw) if raw else (UNCONFIGURED, "")



def _root_value(value: str | None, from_env: bool, setting: str) -> str:
    """A resolved root, marked when nobody chose it. See status._root_line."""
    if not value:
        return f"{UNCONFIGURED} - {setting} is not set"
    return value if from_env else f"{value}  (default - {setting} is not set)"


def collect_settings(*, facts: RuntimeFacts | None = None) -> SettingsView:
    """Read every setting Dispatch consults. Creates nothing, changes nothing."""
    facts = facts or probe.probe_runtime()
    weak = set(facts.weak_secret_names or [])

    def secret_row(name: str, purpose: str) -> SettingRow:
        # A secret is CONFIGURED only when it is set AND is not the published
        # default from this repository. "Set to the value anyone reading the
        # source already knows" is not configured, and calling it configured
        # would be the single most dangerous lie this screen could tell.
        status = UNCONFIGURED if name in weak else CONFIGURED
        return SettingRow(
            name=name,
            status=status,
            value="",
            purpose=purpose,
            secret=True,
            blocks_start=facts.secrets_block_start,
            fallback="Dispatch refuses to start in operational mode until this is set."
            if facts.secrets_block_start
            else "Development mode permits this. Never expose this machine.",
        )

    rows: list[SettingRow] = [
        secret_row("PORTAL_SECRET_KEY", "Signs the browser session cookie."),
        secret_row(
            "DISPATCH_EMAIL_SECRET",
            "Signs decision, stakeholder and IFTA links sent by email.",
        ),
    ]

    for name, purpose, fallback in (
        (
            "DISPATCH_OPERATIONS_ROOT",
            "Where Dispatch keeps its working files, database and logs.",
            "the repository folder",
        ),
        ("DISPATCH_ARCHIVE_ROOT", "Where completed loads and PODs are archived.", "the portal data folder"),
        ("DISPATCH_MEMORY_ROOT", "Where evidence, receipts and the library live.", "the portal data folder"),
        ("DISPATCH_BACKUP_DIR", "Where backups are written and read from.", "no backup location known"),
        ("PORTAL_HOST", "The network address the portal binds to.", "127.0.0.1"),
        ("PORTAL_PORT", "The port the portal listens on.", "8080"),
        (
            "DISPATCH_MODE",
            "operational (default) or development. Development pins to loopback.",
            "operational",
        ),
        (
            "DISPATCH_REHEARSAL_SESSION",
            "Starts Dispatch in rehearsal mode, tagging every record REHEARSAL.",
            "no rehearsal; records are live",
        ),
        (
            locations.LOG_DIR_ENV,
            "Where the launcher keeps its PID file and logs.",
            str(locations.logs_dir()),
        ),
    ):
        status, value = _env(name)
        rows.append(
            SettingRow(
                name=name,
                status=status,
                value=value,
                purpose=purpose,
                fallback=fallback,
                session_scoped=(name == "DISPATCH_REHEARSAL_SESSION"),
            )
        )

    resolved = [
        ("Portal URL", facts.url),
        ("Database", facts.database_path),
        ("Portal data", facts.portal_data_dir),
        ("Operations root", facts.operations_root or f"{UNCONFIGURED} - using defaults"),
        (
            "Archive root",
            _root_value(facts.archive_root, facts.archive_root_from_env, "DISPATCH_ARCHIVE_ROOT"),
        ),
        (
            "Memory root",
            _root_value(facts.memory_root, facts.memory_root_from_env, "DISPATCH_MEMORY_ROOT"),
        ),
        ("Contract archive", facts.contract_archive_root),
        ("Launcher logs", str(locations.logs_dir())),
    ]
    return SettingsView(rows=rows, facts=facts, resolved=resolved)


def rehearsal_warning() -> str:
    """Whether `DISPATCH_REHEARSAL_SESSION` names a session that actually exists.

    `active_session_id()` reads this variable and does not validate it, because
    it is called on every write and must stay silent and fast. So a typo -- or
    a plausible-looking value like `yes` -- tags every record created afterwards
    with a string that leads nowhere. `rehearsal.py` says why that is worse than
    no tag at all: *"an orphan tag is worse than no tag, because purge cannot
    find it and the banner cannot explain it."*

    The check belongs here rather than in the write path: this screen is where
    Mike looks before starting, and a warning he reads once beats a refusal that
    stops a start he meant to make.

    Returns "" when there is nothing to say.
    """
    import os

    value = (os.environ.get("DISPATCH_REHEARSAL_SESSION") or "").strip()
    if not value:
        return ""
    try:
        from dispatch import rehearsal
    except Exception:  # noqa: BLE001 - a warning must never stop a status screen
        return ""
    try:
        session = rehearsal.get_session(value)
    except Exception:  # noqa: BLE001
        return ""

    if session is None:
        return (
            f"DISPATCH_REHEARSAL_SESSION is set to {value!r}, and no rehearsal session "
            f"by that name exists.\n"
            "Every load, milestone and evidence record created from now on will be tagged "
            "with that \ntext, and nothing will be able to explain or purge them later. "
            "Start a real session first,\nor clear the variable:  set DISPATCH_REHEARSAL_SESSION="
        )
    if session.get("status") != "OPEN":
        return (
            f"DISPATCH_REHEARSAL_SESSION points at {value}, which is "
            f"{session.get('status')}, not OPEN.\n"
            "New records would be added to a rehearsal that has already been closed out. "
            "Start a new \nsession rather than reopening a finished one."
        )
    return ""


def render_settings(view: SettingsView) -> str:
    lines = ["  DISPATCH - Settings", ""]
    lines.append(f"{_INDENT}These are read from this machine right now. Dispatch stores no")
    lines.append(f"{_INDENT}settings of its own -- every value below comes from an environment")
    lines.append(f"{_INDENT}variable, and the command to change one is printed beside it.")
    lines.append("")

    warning = rehearsal_warning()
    if warning:
        lines.append(f"{_INDENT}*** REHEARSAL SETTING PROBLEM ***")
        for line in warning.splitlines():
            lines.append(f"{_INDENT}{line}")
        lines.append("")

    for row in view.rows:
        marker = "" if row.status == CONFIGURED else "   <-- not set"
        lines.append(f"{_INDENT}{row.name}")
        lines.append(f"{_INDENT}  {'status':<11}{row.status}{marker}")
        lines.append(f"{_INDENT}  {'value':<11}{row.displayed_value or '-'}")
        lines.append(f"{_INDENT}  {'purpose':<11}{row.purpose}")
        if row.status != CONFIGURED and row.fallback:
            lines.append(f"{_INDENT}  {'without it':<11}{row.fallback}")
        lines.append(f"{_INDENT}  {'to change':<11}{row.change_command()}")
        lines.append("")

    lines.append(f"{_INDENT}What Dispatch actually resolved with the settings above:")
    lines.append("")
    for label, value in view.resolved:
        lines.append(f"{_INDENT}  {label:<18}{value}")
    lines.append("")

    if view.blocking:
        names = ", ".join(r.name for r in view.blocking)
        lines.append(f"{_INDENT}Dispatch will refuse to start until these are set: {names}")
    else:
        lines.append(f"{_INDENT}Nothing in this list is preventing Dispatch from starting.")
    lines.append("")
    lines.append(f"{_INDENT}setx writes the value permanently, but a NEW value only reaches")
    lines.append(f"{_INDENT}windows opened afterwards. Close this window and reopen it after")
    lines.append(f"{_INDENT}changing anything here.")
    if any(r.session_scoped for r in view.rows):
        lines.append("")
        lines.append(f"{_INDENT}One exception: DISPATCH_REHEARSAL_SESSION is never made permanent.")
        lines.append(f"{_INDENT}Rehearsal mode belongs to one window and one afternoon. Made")
        lines.append(f"{_INDENT}permanent it would tag your first real load as a test.")
        lines.append("")
        lines.append(f"{_INDENT}Its command differs by shell. A PowerShell prompt reads PS D:\\...>")
        lines.append(f"{_INDENT}and needs $env:NAME = \"value\". Using cmd's `set` there sets nothing")
        lines.append(f"{_INDENT}Dispatch can read, and says nothing about it.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────── version


@dataclass
class VersionView:
    version: str
    version_source: str
    commit: str
    commit_source: str
    python: str
    platform_name: str
    executable: str
    repository: str
    dependencies: list[tuple[str, str]]


def _dependency(name: str) -> str:
    """The installed version of a dependency, or a truth word.

    `ABSENT` and `UNVERIFIED` say different things and both are true sometimes:
    a package that is not installed is ABSENT, and one that is installed but
    declares no version is UNVERIFIED. Neither is guessed.
    """
    try:
        from importlib import metadata
    except ImportError:  # pragma: no cover - Python < 3.8 only
        return UNVERIFIED
    try:
        return metadata.version(name)
    except Exception:
        return "ABSENT"


def collect_version(*, facts: RuntimeFacts | None = None) -> VersionView:
    facts = facts or probe.probe_runtime()
    return VersionView(
        version=facts.version,
        version_source=facts.version_source,
        commit=facts.commit,
        commit_source=facts.commit_source,
        python=platform.python_version(),
        platform_name=f"{platform.system()} {platform.release()}".strip() or UNVERIFIED,
        executable=sys.executable or UNVERIFIED,
        repository=str(locations.repo_root()),
        dependencies=[(name, _dependency(name)) for name in ("flask", "paramiko", "anthropic")],
    )


def render_version(view: VersionView) -> str:
    lines = ["  DISPATCH - Version", ""]
    lines.append(f"{_INDENT}{'Dispatch version':<20}{view.version} ({view.version_source})")
    lines.append(f"{_INDENT}{'Commit':<20}{view.commit}")
    if view.commit == UNVERIFIED:
        lines.append(f"{_INDENT}{'':<20}{view.commit_source}")
    lines.append("")
    lines.append(f"{_INDENT}{'Python':<20}{view.python}")
    lines.append(f"{_INDENT}{'Interpreter':<20}{view.executable}")
    lines.append(f"{_INDENT}{'Windows / OS':<20}{view.platform_name}")
    lines.append(f"{_INDENT}{'Repository':<20}{view.repository}")
    lines.append("")
    lines.append(f"{_INDENT}Installed packages Dispatch depends on:")
    for name, installed in view.dependencies:
        lines.append(f"{_INDENT}  {name:<18}{installed}")
    lines.append("")
    lines.append(f"{_INDENT}The commit is what proves which code is running. Quote it when")
    lines.append(f"{_INDENT}reporting anything, and record it in any proof document.")
    return "\n".join(lines)
