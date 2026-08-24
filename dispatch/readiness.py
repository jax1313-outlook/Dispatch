"""Readiness checks — what must be true before Dispatch carries a real load.

Section 4.4 of the Operational Readiness Mission lists the conditions the proof
utility verifies before step 1 of the proof path runs:

    database path exists and is writable; evidence-storage path exists and is
    writable; backup destination exists and is separate from the live paths;
    restore destination exists, is empty or purgeable, and is separate from
    both; no default secrets in operational mode; application commit and version.

Two design points worth stating plainly, because both are places where a
readiness check could quietly lie:

**Writability is proven by writing, not by inspecting permission bits.** A
directory can be `os.access(..., os.W_OK)` and still refuse a write -- a
read-only mount, a full volume, a Windows ACL that `os.access` does not model.
So each path check creates a temporary file, writes to it, and deletes it. That
is the only evidence that answers the question actually being asked.

**Separateness is proven by resolved path containment, not by string
inequality.** `D:\\Backups` and `D:\\Backups\\..\\Dispatch Operations` are
different strings and the same place. Every comparison here resolves both sides
first and then asks whether either contains the other, so a backup destination
nested inside the live evidence store is caught rather than passed.

Status words come from the mission's Section 1.8 vocabulary and nowhere else:
`CONFIGURED` (present and validated), `UNCONFIGURED` (required configuration
absent), `UNAVAILABLE` (configured but the attempt failed), `ABSENT` (the step
was not performed at all), `UNVERIFIED` (implemented but not proven on Mike's
machine). There are no softer variants and no synonyms.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: Section 1.8. Anything reporting a dependency, data source, or proof state
#: uses one of these and nothing else.
TRUTH_WORDS = (
    "LIVE",
    "CONFIGURED",
    "UNCONFIGURED",
    "SIMULATED",
    "UNAVAILABLE",
    "MANUAL",
    "ABSENT",
    "UNVERIFIED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- identity


def application_version() -> str:
    """The version string that appears in every artifact this mission produces."""
    from portal import __version__

    return __version__


def application_commit() -> str:
    """The commit, or the literal word ``UNVERIFIED`` when git cannot answer.

    A guess here would be worse than an absence: every proof artifact carries
    this value, and a wrong commit makes an otherwise honest report unusable
    for deciding what code was actually running.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git binary
        return "UNVERIFIED"
    commit = out.stdout.strip()
    return commit if out.returncode == 0 and commit else "UNVERIFIED"


def application_identity() -> dict:
    return {
        "version": application_version(),
        "commit": application_commit(),
        "python": os.sys.version.split()[0],
        "platform": os.sys.platform,
        "captured_at": _now(),
    }


# --------------------------------------------------------------------------- checks


@dataclass
class CheckResult:
    """One readiness condition and the evidence for its answer."""

    name: str
    status: str
    detail: str
    evidence: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in TRUTH_WORDS:
            raise ValueError(
                f"{self.status!r} is not one of the Section 1.8 truth words: "
                f"{', '.join(TRUTH_WORDS)}. Synonyms and softer variants are not allowed."
            )

    @property
    def ok(self) -> bool:
        return self.status == "CONFIGURED"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ok"] = self.ok
        return d


@dataclass
class ReadinessReport:
    checks: list[CheckResult]
    identity: dict
    generated_at: str = field(default_factory=_now)

    @property
    def ready(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def blocking(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "ready": self.ready,
            "identity": self.identity,
            "checks": [c.to_dict() for c in self.checks],
        }


def _resolve(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _contains(outer: Path, inner: Path) -> bool:
    """True when ``inner`` is ``outer`` or sits underneath it, after resolution."""
    try:
        inner.relative_to(outer)
        return True
    except ValueError:
        return False


def _overlaps(a: Path, b: Path) -> bool:
    a, b = _resolve(a), _resolve(b)
    return _contains(a, b) or _contains(b, a)


def check_writable(name: str, path: Path | str, *, must_exist: bool = True) -> CheckResult:
    """Prove a directory is writable by writing to it."""
    p = _resolve(path)
    if not p.exists():
        if must_exist:
            return CheckResult(
                name,
                "UNCONFIGURED",
                f"{p} does not exist. Create it, or set the environment variable that points here.",
                {"path": str(p), "exists": False},
            )
        return CheckResult(
            name, "UNCONFIGURED", f"{p} does not exist yet.", {"path": str(p), "exists": False}
        )
    if not p.is_dir():
        return CheckResult(
            name,
            "UNAVAILABLE",
            f"{p} exists but is not a directory.",
            {"path": str(p), "is_dir": False},
        )
    probe = p / f".dispatch-write-probe-{uuid.uuid4().hex[:8]}"
    try:
        probe.write_text("probe", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return CheckResult(
            name,
            "UNAVAILABLE",
            f"{p} exists but Dispatch could not write to it: {exc.strerror or exc}.",
            {"path": str(p), "error": exc.__class__.__name__},
        )
    return CheckResult(
        name, "CONFIGURED", f"{p} exists and Dispatch wrote to it and cleaned up.",
        {"path": str(p), "write_probe": "succeeded"},
    )


def check_database_path() -> CheckResult:
    from dispatch.db import get_db_path

    db = _resolve(get_db_path())
    parent = check_writable("Database directory", db.parent)
    parent.evidence["database_path"] = str(db)
    parent.evidence["database_exists"] = db.exists()
    parent.name = "Database path"
    if parent.ok:
        parent.detail = (
            f"Database resolves to {db} "
            f"({'exists' if db.exists() else 'will be created on first connection'}); "
            f"its directory is writable."
        )
    return parent


def check_evidence_path() -> CheckResult:
    """Resolve the evidence directory the way Dispatch does, then prove it writable.

    ``dispatch.services._get_upload_dir`` creates the directory as part of
    resolving it, exactly as it does on a real upload. That is a side effect in a
    function called "check", and it is the right one: the question being asked is
    "will an upload land here", and answering it by resolving the path a
    *different* way -- reimplementing the four-branch environment fallback -- would
    give an answer about a path Dispatch might not use. There is no "does not
    exist" branch below because that resolution cannot return a missing
    directory; if the mkdir fails, it raises, and that is the case handled here.
    """
    from dispatch.services import _get_upload_dir

    try:
        upload = _resolve(_get_upload_dir())
    except OSError as exc:
        return CheckResult(
            "Evidence storage",
            "UNAVAILABLE",
            f"Dispatch could not create the evidence directory: {exc.strerror or exc}. "
            f"Check PORTAL_UPLOAD_DIR / DISPATCH_MEMORY_ROOT and the drive they point at.",
            {"error": exc.__class__.__name__},
        )
    return check_writable("Evidence storage", upload)


def check_separate(
    name: str, candidate: Path | str | None, *, against: dict[str, Path]
) -> CheckResult:
    """A destination must exist, be writable, and overlap none of the live paths."""
    if candidate is None:
        return CheckResult(
            name,
            "UNCONFIGURED",
            f"No {name.lower()} was supplied. Pass one explicitly; Dispatch will not "
            f"choose a destination for backup or restore on its own.",
            {},
        )
    p = _resolve(candidate)
    writable = check_writable(name, p, must_exist=False)
    if writable.status == "UNCONFIGURED" and not p.exists():
        return CheckResult(
            name,
            "UNCONFIGURED",
            f"{p} does not exist. Create it before running the proof.",
            {"path": str(p), "exists": False},
        )
    if not writable.ok:
        return writable
    collisions = {label: str(live) for label, live in against.items() if _overlaps(live, p)}
    if collisions:
        listed = "; ".join(f"{k} ({v})" for k, v in sorted(collisions.items()))
        return CheckResult(
            name,
            "UNAVAILABLE",
            f"{p} overlaps a live path and must not: {listed}. A backup or restore "
            f"destination inside the live tree can overwrite the data it exists to protect.",
            {"path": str(p), "overlaps": collisions},
        )
    return CheckResult(
        name,
        "CONFIGURED",
        f"{p} exists, is writable, and overlaps none of the live paths.",
        {"path": str(p), "overlaps": {}},
    )


def check_restore_destination(
    candidate: Path | str | None, *, against: dict[str, Path]
) -> CheckResult:
    """As ``check_separate``, plus: empty, or purgeable and reported as non-empty."""
    result = check_separate("Restore destination", candidate, against=against)
    if not result.ok or candidate is None:
        return result
    p = _resolve(candidate)
    contents = sorted(x.name for x in p.iterdir())
    if contents:
        return CheckResult(
            "Restore destination",
            "UNAVAILABLE",
            f"{p} is not empty ({len(contents)} entr{'y' if len(contents) == 1 else 'ies'}). "
            f"dispatch.backup.restore refuses a non-empty destination. Empty it yourself -- "
            f"Dispatch will not delete files on your machine to make room.",
            {"path": str(p), "entries": contents[:20], "entry_count": len(contents)},
        )
    result.detail = f"{p} exists, is empty, is writable, and overlaps none of the live paths."
    result.evidence["empty"] = True
    return result


def check_secrets_configured() -> CheckResult:
    """No published-default secret in operational mode. Names only, never values."""
    from portal.config import _PUBLISHED_DEFAULTS, is_development_mode

    weak = sorted(
        name
        for name, published in _PUBLISHED_DEFAULTS.items()
        if os.environ.get(name, published) == published
    )
    dev = is_development_mode()
    if not weak:
        return CheckResult(
            "Secrets",
            "CONFIGURED",
            "Both signing secrets are set to values that are not the published defaults.",
            {"weak_settings": [], "development_mode": dev},
        )
    listed = ", ".join(weak)
    verb = "is" if len(weak) == 1 else "are"
    if dev:
        return CheckResult(
            "Secrets",
            "UNCONFIGURED",
            f"DISPATCH_MODE is development and {listed} {verb} unset or a published default. "
            f"Sessions are forgeable and every signed link is mintable by anyone who can "
            f"read this repository. Set real values before any load, rehearsal included.",
            {"weak_settings": weak, "development_mode": True},
        )
    return CheckResult(
        "Secrets",
        "UNCONFIGURED",
        f"{listed} {verb} unset or still the published default. Operational mode refuses to "
        f"start at all in this state -- portal.config.check_secrets() raises.",
        {"weak_settings": weak, "development_mode": False},
    )


def check_authority_identity() -> CheckResult:
    """Nothing past /login is reachable until the Authority PIN is bootstrapped."""
    try:
        from portal.models import identity as identity_model

        exists = identity_model.has_any_identity()
    except Exception as exc:  # pragma: no cover - store unreadable
        return CheckResult(
            "Authority identity",
            "UNAVAILABLE",
            f"Could not read the identity store: {exc.__class__.__name__}.",
            {},
        )
    if exists:
        return CheckResult(
            "Authority identity",
            "CONFIGURED",
            "An Authority identity exists, so the portal login gate has something to admit.",
            {"bootstrapped": True},
        )
    return CheckResult(
        "Authority identity",
        "UNCONFIGURED",
        "No Authority identity exists. Run `cin-portal-init-admin` at the terminal "
        "(never through a logged session) before step 2 of the proof path.",
        {"bootstrapped": False},
    )


def live_paths() -> dict[str, Path]:
    """The paths a backup or restore destination must not overlap."""
    from dispatch.db import get_db_path
    from dispatch.services import _get_upload_dir
    from portal.models import get_archive_dir, get_data_dir, get_memory_dir

    return {
        "database directory": _resolve(get_db_path()).parent,
        "evidence store": _resolve(_get_upload_dir()),
        "portal data": _resolve(get_data_dir()),
        "memory root": _resolve(get_memory_dir()),
        "archive root": _resolve(get_archive_dir()),
    }


def run_readiness_checks(
    *,
    backup_destination: Path | str | None = None,
    restore_destination: Path | str | None = None,
) -> ReadinessReport:
    """Every Section 4.4 condition, in the order the mission lists them."""
    live = live_paths()
    checks = [
        check_database_path(),
        check_evidence_path(),
        check_separate("Backup destination", backup_destination, against=live),
        check_restore_destination(restore_destination, against=live),
        check_secrets_configured(),
        check_authority_identity(),
    ]
    return ReadinessReport(checks=checks, identity=application_identity())


def render_readiness(report: ReadinessReport) -> str:
    """Plain text, for the launcher and the CLI. One line per check, no colour."""
    lines = [
        "Dispatch readiness",
        f"  generated       {report.generated_at}",
        f"  version         {report.identity['version']}",
        f"  commit          {report.identity['commit']}",
        f"  python          {report.identity['python']} on {report.identity['platform']}",
        "",
    ]
    width = max(len(c.name) for c in report.checks)
    for c in report.checks:
        lines.append(f"  {c.name.ljust(width)}  {c.status:<13} {c.detail}")
    lines.append("")
    if report.ready:
        lines.append("  All readiness conditions are CONFIGURED.")
    else:
        lines.append(f"  {len(report.blocking)} condition(s) not CONFIGURED — see above.")
    lines.append(
        "  This is a check of this machine's configuration. It is not proof that a load "
        "has moved through Dispatch."
    )
    return "\n".join(lines)
