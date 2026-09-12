"""Taking a backup, and proving one -- from the launcher, where Mike is.

`dispatch/backup.py` is 926 lines of capture, manifest, SHA-256 verification,
safe restore and stored-path repointing. `dispatch_launcher/backups.py` reports
on the result. Between the two there was nothing that *took* one: no portal
route, no template, no launcher command, no scheduled task. The only caller of
`create_backup` inside the product was `dispatch/proof.py`, and the only
instruction anywhere was a sentence in the status text telling the operator to
type a script path from memory.

So the whole estate -- SQLite, twelve JSON stores, and every uploaded evidence
file -- was protected by Mike remembering a command that appeared in no menu.

This module is the missing middle. It does none of the work itself: every
decision about what is captured and whether a restore is safe stays in the
engine, so what the launcher does is exactly what the suite exercises.

**On the verification record.** `backups.py` says, correctly, that nothing here
writes it "by design: it is a record of a human action, and manufacturing it is
precisely the kind of claim this program forbids." That rule is kept. What
`prove_restore` writes is a record that says who performed it -- `Code-automated`
unless a person passes their own identity -- and `backups.py` now reads that
field: a machine-performed restore leaves the state at UNVERIFIED with the detail
upgraded to say what was actually done, and only a person's confirmation reaches
VERIFIED. The program can prove the archive restores and hashes. It cannot
prove the restored estate works, because that is somebody looking at it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dispatch_launcher import backups, locations

#: What `performed_by` says when nobody claimed it. Matches
#: `dispatch.proof.PERFORMERS`, so the two records read the same way.
CODE_AUTOMATED = "Code-automated"


@dataclass(frozen=True)
class BackupActionResult:
    ok: bool
    summary: str
    detail: str = ""
    archive: str | None = None
    evidence: dict | None = None

    def render(self) -> str:
        head = f"  {'OK' if self.ok else 'FAILED'}  {self.summary}"
        if not self.detail:
            return head
        body = "\n".join(f"    {line}" for line in self.detail.splitlines())
        return f"{head}\n{body}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_backup_dir(explicit: str | Path | None = None) -> Path | None:
    """Where backups go. Never guessed.

    An unset DISPATCH_BACKUP_DIR is UNCONFIGURED, not `D:\\Backups`: inventing a
    plausible folder and reporting "no backups found" would tell Mike his
    backups are missing when the launcher was looking somewhere nobody chose.
    """
    if explicit:
        return Path(explicit)
    configured = os.environ.get("DISPATCH_BACKUP_DIR")
    return Path(configured) if configured else None


def create(destination: str | Path | None = None, *, compress: bool = False) -> BackupActionResult:
    """Take a backup now."""
    target = resolve_backup_dir(destination)
    if target is None:
        return BackupActionResult(
            False,
            "No backup location is configured.",
            "Set DISPATCH_BACKUP_DIR to the folder backups should be written to,\n"
            "then run this again. Dispatch will not choose a folder on your machine.",
        )

    from dispatch import backup as engine

    try:
        result = engine.create_backup(target, compress=compress)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        return BackupActionResult(False, "The backup did not complete.", str(exc))

    lines = [f"{result.file_count} files, {result.total_bytes:,} bytes"]
    for absent in result.absent_sources:
        lines.append(f"MISSING: {absent['roles']} -> {absent['path']} ({absent['reason']})")
    for note in result.notes:
        lines.append(f"note: {note}")
    lines.append("")
    lines.append("This backup has not been restored, so it is not yet known to be usable.")
    lines.append("Prove it with:  python -m dispatch_launcher prove-restore")

    return BackupActionResult(
        bool(result.ok),
        ("Backup written to " if result.ok else "Backup incomplete: ") + str(result.archive_path),
        "\n".join(lines),
        archive=str(result.archive_path),
        evidence={"file_count": result.file_count, "total_bytes": result.total_bytes},
    )


def latest_archive(directory: Path) -> Path | None:
    candidates = backups._archive_candidates(directory)  # noqa: SLF001 - same package
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def verify(archive: str | Path | None = None) -> BackupActionResult:
    """Recompute every hash in an archive. Says nothing about restorability."""
    from dispatch import backup as engine

    target = Path(archive) if archive else None
    if target is None:
        directory = resolve_backup_dir()
        if directory is None or not directory.is_dir():
            return BackupActionResult(False, "No backup location is configured.")
        target = latest_archive(directory)
        if target is None:
            return BackupActionResult(False, f"No Dispatch backup archives in {directory}.")

    result = engine.verify(target)
    return BackupActionResult(
        result.ok,
        f"{target}: {result.describe()}",
        "A hash check proves the archive is intact. It does not prove it restores.",
        archive=str(target),
    )


def prove_restore(
    archive: str | Path | None = None,
    destination: str | Path | None = None,
    *,
    confirmed_by: str | None = None,
    keep: bool = False,
) -> BackupActionResult:
    """Restore into an isolated scratch destination and record what happened.

    The destination is checked by `dispatch.readiness.check_restore_destination`
    before anything is written -- it must be empty and must overlap neither the
    live database nor the live evidence store. Restoring into the live paths is
    prohibited outright, and the gate runs before the step rather than being
    remembered during it.
    """
    from dispatch import backup as engine
    from dispatch import readiness

    directory = resolve_backup_dir()
    target = Path(archive) if archive else (latest_archive(directory) if directory and directory.is_dir() else None)
    if target is None:
        return BackupActionResult(
            False,
            "No backup to prove.",
            "Take one first:  python -m dispatch_launcher backup",
        )

    scratch_created = False
    if destination is None:
        destination = Path(tempfile.mkdtemp(prefix="dispatch-restore-proof-"))
        scratch_created = True
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    try:
        check = readiness.check_restore_destination(
            destination, against=readiness.live_paths()
        )
        if not check.ok:
            return BackupActionResult(False, "Restore destination refused.", check.detail)

        try:
            result = engine.restore(target, destination)
        except Exception as exc:  # noqa: BLE001
            return BackupActionResult(False, "The restore failed.", f"{type(exc).__name__}: {exc}")

        record = {
            "archive": backups._archive_name(target),  # noqa: SLF001 - same package
            "archive_path": str(target),
            "restored_at": _utc_now(),
            "restored_to": str(destination),
            "files_restored": len(result.restored),
            "database_restored": bool(result.database_path),
            "paths_rehomed": result.paths_rehomed,
            # The whole point of this field. `backups.py` will not render
            # VERIFIED on a machine's say-so, and this is what it reads.
            "performed_by": confirmed_by or CODE_AUTOMATED,
            "verified_scope": (
                "restored into an isolated destination; every manifest hash recomputed"
                if not confirmed_by
                else "restored into an isolated destination, and the restored estate "
                     "was opened and confirmed working by the person named"
            ),
        }
        written = _write_verification(directory or target.parent, target, record)

        detail = [
            f"restored {len(result.restored)} files to {destination}",
            f"verification record: {written}",
        ]
        if result.paths_rehomed:
            detail.append(f"repointed {result.paths_rehomed} stored file paths")
        if not confirmed_by:
            detail.append(
                "Recorded as Code-automated. The archive restores and every hash matches;"
            )
            detail.append(
                "that the restored Dispatch actually works is still for a person to confirm."
            )
        return BackupActionResult(
            True, "Restore proven in an isolated destination.", "\n".join(detail),
            archive=str(target), evidence=record,
        )
    finally:
        if scratch_created and not keep:
            shutil.rmtree(destination, ignore_errors=True)


def _write_verification(directory: Path, archive: Path, record: dict) -> Path:
    """Beside the archive, named for it, so it can never be read as evidence
    about a different backup."""
    directory.mkdir(parents=True, exist_ok=True)
    name = backups._archive_name(archive)  # noqa: SLF001 - same package
    path = directory / f"{name}.{backups.VERIFICATION_NAME}"
    path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return path


def status_line() -> str:
    directory = resolve_backup_dir()
    return backups.backup_status(directory).describe()


# ---------------------------------------------------------------- scheduling


WINDOWS_TASK_NAME = "Dispatch Nightly Backup"


def schedule_command(*, hour: int = 2, minute: int = 0) -> dict:
    """The exact command to register a nightly backup, per platform.

    Printed rather than run. Registering a scheduled task writes to the machine
    outside Dispatch's own folders, and the program does not do that to somebody's
    computer without being asked -- but making the operator invent the command is
    how the backup never gets scheduled at all.
    """
    python = sys.executable or "python"
    module = "-m dispatch_launcher backup"
    directory = resolve_backup_dir()
    return {
        "windows": (
            f'schtasks /Create /TN "{WINDOWS_TASK_NAME}" /SC DAILY '
            f'/ST {hour:02d}:{minute:02d} /TR "\\"{python}\\" {module}" /F'
        ),
        "windows_remove": f'schtasks /Delete /TN "{WINDOWS_TASK_NAME}" /F',
        "cron": f"{minute} {hour} * * *  {python} {module}",
        "backup_dir": str(directory) if directory else None,
        "note": (
            "The scheduled task inherits the account's environment, so "
            "DISPATCH_BACKUP_DIR must be set for the machine (setx /M) or the "
            "task will run and find no configured location."
        ),
    }


def render_schedule() -> str:
    plan = schedule_command()
    lines = ["  To run a backup every night at 02:00:", ""]
    lines.append("  Windows (run as Administrator):")
    lines.append(f"    {plan['windows']}")
    lines.append("")
    lines.append("  Linux / macOS (crontab -e):")
    lines.append(f"    {plan['cron']}")
    lines.append("")
    if plan["backup_dir"]:
        lines.append(f"  Backups will be written to: {plan['backup_dir']}")
    else:
        lines.append("  DISPATCH_BACKUP_DIR is not set. Set it first, or the task will")
        lines.append("  run every night and write nothing.")
    lines.append("")
    lines.append(f"  {plan['note']}")
    lines.append("")
    lines.append("  To remove it later:")
    lines.append(f"    {plan['windows_remove']}")
    return "\n".join(lines)
