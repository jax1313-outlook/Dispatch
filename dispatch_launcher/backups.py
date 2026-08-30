"""Backup observation -- and the refusal to call a backup good.

`dispatch/backup.py` and `scripts/dispatch_backup.py` already do the work. This
module only *looks* at the result, so Mike can see from the launcher whether a
backup exists and when it was taken, without running anything.

The rule this module exists to enforce is BACKUP_AND_RECOVERY.md's own:

    "A backup you have never restored is a hypothesis."
    "An unverified backup is an assumption."

So the launcher will never render a backup as valid, good, verified or current on
the strength of the archive existing, on the strength of its manifest parsing, or
on the strength of a hash check. It says VERIFIED only when a **restore
verification record** exists -- a file written by whoever actually performed a
restore and confirmed the restored estate worked. Nothing in this repository
writes that file today, by design: it is a record of a human action, and
manufacturing it is precisely the kind of claim this program forbids. Until one
exists, the honest state is UNVERIFIED.

The backup directory itself is not guessed. If `DISPATCH_BACKUP_DIR` is unset the
state is UNCONFIGURED -- inventing a plausible `D:\\Backups` and reporting
"no backups found" would tell Mike his backups are missing when in fact the
launcher was looking in a folder nobody chose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

#: The file that turns "a backup exists" into "a backup was proven restorable".
#: Searched for in three places so an operator can keep it next to the archive,
#: next to the backup set, or in one folder of them -- see `_find_verification`.
VERIFICATION_NAME = "restore-verification.json"

#: What `dispatch.backup.create_backup` names its archives.
ARCHIVE_PREFIX = "dispatch-backup-"
_ARCHIVE_TIMESTAMP = re.compile(r"dispatch-backup-(\d{8}T\d{6}Z)")

_TARBALL_SUFFIXES = (".tar.gz", ".tgz", ".tar")

# Truth vocabulary. No other words are used for this state anywhere in the
# launcher's output.
UNCONFIGURED = "UNCONFIGURED"
ABSENT = "ABSENT"
UNVERIFIED = "UNVERIFIED"
VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class BackupStatus:
    state: str
    detail: str
    location: str | None = None
    created_at: str | None = None
    #: Where `created_at` came from: "manifest", "archive name", "file timestamp".
    #: Displayed, because "the manifest says so" and "the file's timestamp says
    #: so" are different strengths of claim.
    created_at_source: str | None = None
    verification: dict | None = None


def _archive_candidates(directory: Path) -> list[Path]:
    found: list[Path] = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return found
    for entry in entries:
        if not entry.name.startswith(ARCHIVE_PREFIX):
            continue
        if entry.is_dir() or (
            entry.is_file() and entry.name.endswith(_TARBALL_SUFFIXES)
        ):
            found.append(entry)
    return found


def _archive_name(archive: Path) -> str:
    name = archive.name
    for suffix in _TARBALL_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _created_at(archive: Path) -> tuple[str | None, str]:
    """When the archive was taken, and how strongly we know it.

    The manifest is authoritative and is read when the archive is an
    uncompressed directory. A tarball is deliberately not opened -- a status
    screen must not spend seconds decompressing backup media -- so its timestamp
    comes from the archive name `create_backup` stamps, and only from the file's
    modification time when even that is missing.
    """
    if archive.is_dir():
        manifest = archive / "manifest.json"
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            created = data.get("created_at")
            if created:
                return str(created), "manifest"
        except (OSError, ValueError):
            pass

    match = _ARCHIVE_TIMESTAMP.search(archive.name)
    if match:
        stamp = match.group(1)
        try:
            parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ"), "archive name"
        except ValueError:
            pass

    try:
        mtime = datetime.fromtimestamp(archive.stat().st_mtime, tz=timezone.utc)
        return mtime.strftime("%Y-%m-%dT%H:%M:%SZ"), "file timestamp"
    except OSError:
        return None, "unknown"


def _load_verification(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _find_verification(directory: Path, archive: Path) -> dict | None:
    """Locate a restore verification record for exactly this archive.

    A record that names a *different* archive is not evidence about this one, so
    it is ignored rather than borrowed. A record with no `archive` field at all
    is accepted only when it sits inside the archive directory itself, where it
    cannot be about anything else.
    """
    name = _archive_name(archive)
    inside = archive / VERIFICATION_NAME if archive.is_dir() else None
    beside = directory / f"{name}.{VERIFICATION_NAME}"
    collected = directory / "restore-verifications" / f"{name}.json"

    for candidate, implies_this_archive in (
        (inside, True), (beside, False), (collected, False),
    ):
        if candidate is None or not candidate.is_file():
            continue
        record = _load_verification(candidate)
        if record is None:
            continue
        named = str(record.get("archive", "")).strip()
        if named:
            if _archive_name(Path(named)) != name:
                continue
        elif not implies_this_archive:
            continue
        return {"record_path": str(candidate), **record}
    return None


def backup_status(backup_dir: str | Path | None) -> BackupStatus:
    """Observe the most recent backup, and say exactly how much is known about it."""
    if not backup_dir:
        return BackupStatus(
            state=UNCONFIGURED,
            detail=(
                "No backup location is configured. Set DISPATCH_BACKUP_DIR to the "
                "folder scripts/dispatch_backup.py writes to."
            ),
        )

    directory = Path(backup_dir)
    if not directory.is_dir():
        return BackupStatus(
            state=ABSENT,
            location=str(directory),
            detail=(
                f"The configured backup location does not exist: {directory}. "
                "No backup has been observed."
            ),
        )

    candidates = _archive_candidates(directory)
    if not candidates:
        return BackupStatus(
            state=ABSENT,
            location=str(directory),
            detail=(
                f"No Dispatch backup archives were found in {directory}. "
                "Run: python scripts/dispatch_backup.py backup <destination>"
            ),
        )

    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    created_at, created_source = _created_at(newest)
    verification = _find_verification(directory, newest)

    if verification is None:
        return BackupStatus(
            state=UNVERIFIED,
            location=str(newest),
            created_at=created_at,
            created_at_source=created_source,
            detail=(
                "This backup has never been restored and proven, so it is not known "
                "to be usable. To prove it, restore it to a scratch folder and record "
                f"the result as {VERIFICATION_NAME}."
            ),
        )

    return BackupStatus(
        state=VERIFIED,
        location=str(newest),
        created_at=created_at,
        created_at_source=created_source,
        verification=verification,
        detail=(
            "A restore verification record exists for this backup: "
            f"{verification.get('record_path')}"
        ),
    )
