"""Rotating backup drives -- recognised by identity, never by drive letter (CO-12).

Owner direction, 2026-09-14: *"Back up is rotating 4TB Crucial external hard drives."*

Two or more external drives take turns. One is plugged into the node and receives the
backups; the other is somewhere else. Every so often they swap. Three things make that
habit trustworthy instead of hopeful, and each is a part of this module:

*Identity, not letters.* Windows hands out drive letters in the order drives arrive, so
"the backup drive is T:" is true until the day it is not -- and then a backup is written
to whatever happens to be T:, or reported ABSENT while the drive sits in the port. A
prepared drive therefore carries a small identity file at its root naming it ("Drive A")
with a random id. Discovery reads that file on every mounted volume; the letter is only
where the drive happened to be seen.

*Every run checks itself and leaves a trail in two places.* A run re-hashes the archive it
just wrote (dispatch.backup.create_backup does that), then appends one line to a rotation
log **on the drive** and one line to a record **on the node**. The drive's log survives the
node; the node's record answers "how old is my newest good backup" while the drive is in a
drawer across town.

*Reminders, never deletion.* Status reports the age of the newest backup whose hash check
passed, warns when that is older than 24 hours, and says when the plugged-in drive has been
in use long enough that it is time to swap. Nothing here deletes, prunes or overwrites a
backup. A full drive is a message to a human, not a licence to remove history.

Honest Reporting: a hash check PASS says the bytes on the drive match their manifest. It is
**not** a restore test and nothing here calls it one. Restore proof is a separate, human
procedure -- docs/operations/ROTATING_BACKUP_DRIVES.md.

Probing is read-only: listing volumes, reading a volume's label and serial number, and
checking for one file at each root. The only writes are the identity file (when a human
prepares a drive), the backup itself, and the two log lines.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dispatch import backup as backup_engine

#: The file at a drive's root that makes it a Dispatch backup drive.
IDENTITY_FILE = "dispatch-backup-drive.json"
IDENTITY_SCHEMA = 1

#: Where archives go on an identified drive. The same folder name on every drive, so a
#: recovery operator with no tooling knows where to look.
BACKUP_FOLDER = "DispatchBackups"

#: One JSON line per run, on the drive, inside BACKUP_FOLDER. Append-only.
ROTATION_LOG = "rotation-log.jsonl"

#: The node's own record of which drive holds which backup. Append-only.
LOCAL_RECORD_NAME = "backup_drive_record.jsonl"
RECORD_ENV = "DISPATCH_BACKUP_RECORD"

#: Optional explicit list of mount points to probe (os.pathsep separated). When unset the
#: node's mounted volumes are listed. Useful off Windows and for pointing at one folder.
ROOTS_ENV = "DISPATCH_BACKUP_DRIVE_ROOTS"

#: How many days one drive may stay in use before status says it is time to swap.
SWAP_DAYS_ENV = "DISPATCH_BACKUP_SWAP_DAYS"
DEFAULT_SWAP_DAYS = 7

#: The newest passing backup older than this is a warning.
STALE_AFTER_HOURS = 24

PASS = "PASS"
FAIL = "FAIL"
ABSENT = "ABSENT"

_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_MAX_NAME = 40


class DriveIdentityError(Exception):
    """A drive cannot be prepared, recognised or used -- with the reason, for a human."""


# ── time ───────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(_STAMP)


def _parse(value: Any) -> datetime | None:
    try:
        return datetime.strptime(str(value), _STAMP).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ── identity ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DriveIdentity:
    drive_id: str
    name: str
    prepared_at: str
    #: What the volume reported when the drive was prepared. Empty when the platform
    #: could not say (or the "drive" is a plain folder, as in tests).
    volume_label: str = ""
    volume_serial: str = ""
    schema: int = IDENTITY_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "purpose": "Dispatch rotating backup drive. Do not delete this file.",
            "drive_id": self.drive_id,
            "name": self.name,
            "prepared_at": self.prepared_at,
            "volume_label": self.volume_label,
            "volume_serial": self.volume_serial,
        }

    @classmethod
    def from_dict(cls, data: Any, *, where: str = "") -> "DriveIdentity":
        if not isinstance(data, dict):
            raise DriveIdentityError(f"identity file is not a JSON object{where}")
        if data.get("schema") != IDENTITY_SCHEMA:
            raise DriveIdentityError(
                f"identity file schema {data.get('schema')!r} is not understood{where}")
        drive_id = str(data.get("drive_id") or "").strip()
        name = str(data.get("name") or "").strip()
        if not drive_id or not name:
            raise DriveIdentityError(f"identity file has no drive_id or name{where}")
        return cls(
            drive_id=drive_id, name=name,
            prepared_at=str(data.get("prepared_at") or ""),
            volume_label=str(data.get("volume_label") or ""),
            volume_serial=str(data.get("volume_serial") or ""),
        )


def _is_volume_root(root: Path) -> bool:
    return bool(root.anchor) and str(root).rstrip("\\/") == root.anchor.rstrip("\\/")


def volume_facts(root: Path | str) -> tuple[str, str]:
    """(label, serial) the operating system reports for the volume at *root*.

    Read-only. Answers only for a volume root on Windows; anything else -- a folder, another
    platform, a call that fails -- is ("", "") rather than a guess.
    """
    root = Path(root)
    if sys.platform != "win32" or not _is_volume_root(root):
        return "", ""
    try:  # pragma: no cover - Windows-only branch
        import ctypes

        kernel32 = ctypes.windll.kernel32
        label = ctypes.create_unicode_buffer(261)
        fs_name = ctypes.create_unicode_buffer(261)
        serial = ctypes.c_uint32()
        max_len = ctypes.c_uint32()
        flags = ctypes.c_uint32()
        ok = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root.anchor), label, 261, ctypes.byref(serial),
            ctypes.byref(max_len), ctypes.byref(flags), fs_name, 261,
        )
        if not ok:
            return "", ""
        return label.value, f"{serial.value:08X}"
    except Exception:  # noqa: BLE001 - a probe that cannot run reports nothing
        return "", ""


def read_identity(root: Path | str) -> DriveIdentity | None:
    """The identity at *root*; None when there is none; DriveIdentityError when it is broken."""
    path = Path(root) / IDENTITY_FILE
    try:
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise DriveIdentityError(f"identity file at {path} is not readable JSON: {exc}") from exc
    return DriveIdentity.from_dict(data, where=f" ({path})")


def _overlapping_data(root: Path) -> list[Path]:
    """Configured data locations that sit on, or contain, *root*.

    A backup written onto the same folder tree as the data it protects is not a backup.
    This cannot see partitions of one physical disk; the operator document says so.
    """
    target = Path(os.path.normcase(os.path.abspath(root)))
    hits = []
    for source in backup_engine.configured_source_paths():
        candidate = Path(os.path.normcase(os.path.abspath(source)))
        if candidate == target or candidate.is_relative_to(target) or target.is_relative_to(candidate):
            hits.append(source)
    return hits


def prepare_drive(root: Path | str, name: str, *, now: datetime | None = None) -> DriveIdentity:
    """Write the identity file onto a drive a human has chosen. Never overwrites one.

    Refuses when: the root does not exist, the name is empty or long, the drive already has
    an identity (a second identity would make two drives indistinguishable in the record),
    or the drive holds the data it would be protecting.
    """
    root = Path(root)
    clean = " ".join(str(name or "").split())
    if not clean:
        raise DriveIdentityError("a drive needs a name, for example \"Drive A\"")
    if len(clean) > _MAX_NAME:
        raise DriveIdentityError(f"drive name is longer than {_MAX_NAME} characters")
    if not root.is_dir():
        raise DriveIdentityError(f"{root} is not a mounted drive or folder")
    existing = read_identity(root)
    if existing is not None:
        raise DriveIdentityError(
            f"{root} is already prepared as {existing.name!r} ({existing.drive_id}); "
            "nothing was changed")
    overlap = _overlapping_data(root)
    if overlap:
        raise DriveIdentityError(
            f"{root} holds Dispatch data ({overlap[0]}); a backup drive must be a separate drive")

    label, serial = volume_facts(root)
    identity = DriveIdentity(
        drive_id=uuid.uuid4().hex, name=clean, prepared_at=_stamp(now or _now()),
        volume_label=label, volume_serial=serial,
    )
    target = root / IDENTITY_FILE
    fd, tmp = tempfile.mkstemp(prefix=".dispatch-drive-", suffix=".tmp", dir=str(root))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(identity.to_dict(), handle, indent=2)
        # O_EXCL-style guard: if something wrote an identity between the check and now,
        # keep theirs and fail rather than replacing it.
        if target.exists():
            raise DriveIdentityError(f"{target} appeared while preparing; nothing was changed")
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    (root / BACKUP_FOLDER).mkdir(exist_ok=True)
    return identity


# ── discovery ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FoundDrive:
    root: Path
    identity: DriveIdentity
    #: The serial the volume reports right now ("" when it cannot be read).
    serial_now: str = ""

    @property
    def backup_dir(self) -> Path:
        return self.root / BACKUP_FOLDER

    @property
    def serial_matches(self) -> bool | None:
        """False only when both serials are known and differ -- the identity file was copied."""
        if not self.identity.volume_serial or not self.serial_now:
            return None
        return self.identity.volume_serial == self.serial_now


@dataclass
class DriveScan:
    found: list[FoundDrive] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    probed: list[str] = field(default_factory=list)


def mounted_roots() -> list[Path]:
    """Volume roots worth probing for an identity file. Read-only.

    ROOTS_ENV wins when set. On Windows the logical drives are listed, keeping removable and
    fixed disks (a USB hard drive reports as fixed) and skipping network, optical and RAM
    drives -- a disconnected network share can stall a probe for a long time. Elsewhere the
    usual mount parents are listed.
    """
    configured = os.environ.get(ROOTS_ENV, "").strip()
    if configured:
        return [Path(p) for p in configured.split(os.pathsep) if p.strip()]

    if sys.platform == "win32":  # pragma: no cover - Windows-only branch
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # Suppress "insert a disk" dialogs for empty card readers while probing; this
            # is the calling process's error mode, restored immediately.
            previous = kernel32.SetErrorMode(0x0001 | 0x8000)
            try:
                mask = kernel32.GetLogicalDrives()
                roots = []
                for index in range(26):
                    if not mask & (1 << index):
                        continue
                    letter_root = f"{chr(65 + index)}:\\"
                    if kernel32.GetDriveTypeW(ctypes.c_wchar_p(letter_root)) in (2, 3):
                        roots.append(Path(letter_root))
                return roots
            finally:
                kernel32.SetErrorMode(previous)
        except Exception:  # noqa: BLE001 - no listing is an empty listing, reported by caller
            return []

    roots: list[Path] = []
    for parent in (Path("/media"), Path("/mnt"), Path("/Volumes"), Path("/run/media")):
        try:
            for child in parent.iterdir():
                if child.is_dir():
                    roots.append(child)
                    roots.extend(g for g in child.iterdir() if g.is_dir())
        except OSError:
            continue
    return roots


def find_backup_drives(roots: Iterable[Path | str] | None = None) -> DriveScan:
    """Every identified backup drive among *roots* (default: the mounted volumes)."""
    scan = DriveScan()
    seen_ids: dict[str, Path] = {}
    for raw in (mounted_roots() if roots is None else roots):
        root = Path(raw)
        scan.probed.append(str(root))
        try:
            identity = read_identity(root)
        except DriveIdentityError as exc:
            scan.problems.append(str(exc))
            continue
        if identity is None:
            continue
        _, serial = volume_facts(root)
        drive = FoundDrive(root=root, identity=identity, serial_now=serial)
        if drive.serial_matches is False:
            scan.problems.append(
                f"{root}: identity {identity.name!r} was prepared on volume "
                f"{identity.volume_serial} but this volume is {serial} -- the identity file "
                "looks copied from another drive; it will not be used")
            continue
        if identity.drive_id in seen_ids:
            scan.problems.append(
                f"{root} and {seen_ids[identity.drive_id]} carry the same drive id "
                f"({identity.name!r}); neither will be used until one is re-prepared")
            scan.found = [d for d in scan.found if d.identity.drive_id != identity.drive_id]
            continue
        seen_ids[identity.drive_id] = root
        scan.found.append(drive)
    return scan


def choose_drive(scan: DriveScan, name: str | None = None) -> FoundDrive:
    """The one drive a run should use, or a DriveIdentityError that says why not."""
    candidates = scan.found
    if name:
        wanted = name.strip().lower()
        candidates = [d for d in candidates if d.identity.name.lower() == wanted]
        if not candidates:
            raise DriveIdentityError(f"no mounted backup drive is named {name!r}")
    if not candidates:
        detail = f" ({'; '.join(scan.problems)})" if scan.problems else ""
        raise DriveIdentityError(f"no prepared backup drive is plugged in{detail}")
    if len(candidates) > 1:
        names = ", ".join(f"{d.identity.name} at {d.root}" for d in candidates)
        raise DriveIdentityError(f"more than one backup drive is plugged in ({names}); name one")
    return candidates[0]


# ── records ────────────────────────────────────────────────────────────

def local_record_path() -> Path:
    configured = os.environ.get(RECORD_ENV, "").strip()
    if configured:
        return Path(configured)
    from portal.models import get_data_dir

    return Path(get_data_dir()) / LOCAL_RECORD_NAME


def _append(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_record(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Every run line, oldest first. A malformed line is skipped, never fatal."""
    target = Path(path) if path is not None else local_record_path()
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and _parse(entry.get("recorded_at")) is not None:
            entries.append(entry)
    entries.sort(key=lambda e: e["recorded_at"])
    return entries


@dataclass
class DriveRun:
    entry: dict[str, Any]
    result: backup_engine.BackupResult | None
    drive_log: Path
    local_record: Path

    @property
    def ok(self) -> bool:
        return self.result is not None and self.result.ok


def run_drive_backup(
    drive: FoundDrive,
    *,
    compress: bool = False,
    now: datetime | None = None,
    record_path: Path | str | None = None,
) -> DriveRun:
    """Back up onto *drive*, check the archive, and log the run on the drive and the node.

    A run that raises is still logged, as FAIL with the error, before the error propagates:
    a failed backup nobody wrote down is the silent failure this program forbids.
    """
    if drive.serial_matches is False:
        raise DriveIdentityError(f"{drive.root}: identity file does not belong to this volume")
    overlap = _overlapping_data(drive.root)
    if overlap:
        raise DriveIdentityError(
            f"{drive.root} holds Dispatch data ({overlap[0]}); refusing to back up onto it")

    local = Path(record_path) if record_path is not None else local_record_path()
    drive_log = drive.backup_dir / ROTATION_LOG
    started = now or _now()
    entry: dict[str, Any] = {
        "schema": 1,
        "recorded_at": _stamp(started),
        "drive_id": drive.identity.drive_id,
        "drive_name": drive.identity.name,
        "drive_root_seen": str(drive.root),
    }

    result: backup_engine.BackupResult | None = None
    error: BaseException | None = None
    try:
        drive.backup_dir.mkdir(parents=True, exist_ok=True)
        result = backup_engine.create_backup(drive.backup_dir, compress=compress)
    except BaseException as exc:  # noqa: BLE001 - logged, then re-raised below
        error = exc

    if result is not None:
        check = result.self_check
        entry.update({
            "archive": Path(result.archive_path).name,
            "archive_path": str(result.archive_path),
            "file_count": result.file_count,
            "total_bytes": result.total_bytes,
            "hash_check": result.hash_check or FAIL,
            "hash_detail": check.describe() if check is not None else "no hash check was run",
            "sources_complete": not result.absent_sources,
            "absent": result.absent_sources,
            "error": "",
        })
    else:
        entry.update({
            "archive": "", "archive_path": "", "file_count": 0, "total_bytes": 0,
            "hash_check": FAIL, "hash_detail": "the backup did not finish",
            "sources_complete": False, "absent": [],
            "error": f"{type(error).__name__}: {error}",
        })

    log_problems = []
    for target in (drive_log, local):
        try:
            _append(target, entry)
        except OSError as exc:
            log_problems.append(f"could not write {target}: {exc}")
    if error is not None:
        raise error
    if log_problems:
        # The backup exists and checked out, but its trail is incomplete. Say so.
        entry = {**entry, "log_problems": log_problems}
    return DriveRun(entry=entry, result=result, drive_log=drive_log, local_record=local)


# ── status ─────────────────────────────────────────────────────────────

def _swap_days(explicit: int | None, warnings: list[str]) -> int:
    if explicit is not None:
        return max(1, int(explicit))
    raw = os.environ.get(SWAP_DAYS_ENV, "").strip()
    if not raw:
        return DEFAULT_SWAP_DAYS
    try:
        value = int(raw)
        if value < 1:
            raise ValueError
        return value
    except ValueError:
        warnings.append(f"{SWAP_DAYS_ENV}={raw!r} is not a whole number of days; using {DEFAULT_SWAP_DAYS}")
        return DEFAULT_SWAP_DAYS


@dataclass
class DriveSummary:
    drive_id: str
    name: str
    runs: int
    last_run_at: str
    last_hash_check: str
    last_pass_at: str | None
    last_pass_age_hours: float | None


@dataclass
class RotationStatus:
    #: ABSENT when no rotating-drive backup has ever been recorded on this node.
    recorded: bool
    drives: list[DriveSummary]
    newest_pass_at: str | None
    newest_pass_drive: str | None
    newest_pass_age_hours: float | None
    #: True when there is no passing backup, or the newest is older than stale_hours.
    stale: bool
    stale_hours: int
    current_drive: str | None
    current_drive_since: str | None
    current_drive_days: float | None
    swap_days: int
    swap_due: bool
    warnings: list[str]
    record_path: str

    @property
    def state(self) -> str | None:
        return None if self.recorded else ABSENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "recorded": self.recorded,
            "drives": [vars(d) for d in self.drives],
            "newest_pass_at": self.newest_pass_at,
            "newest_pass_drive": self.newest_pass_drive,
            "newest_pass_age_hours": self.newest_pass_age_hours,
            "stale": self.stale,
            "stale_hours": self.stale_hours,
            "current_drive": self.current_drive,
            "current_drive_since": self.current_drive_since,
            "current_drive_days": self.current_drive_days,
            "swap_days": self.swap_days,
            "swap_due": self.swap_due,
            "warnings": list(self.warnings),
            "record_path": self.record_path,
            "hash_check_meaning": "PASS means the copy matches its manifest. It is not a restore test.",
        }


def _hours(later: datetime, earlier: datetime) -> float:
    return round((later - earlier).total_seconds() / 3600.0, 1)


def rotation_status(
    *,
    now: datetime | None = None,
    record_path: Path | str | None = None,
    swap_days: int | None = None,
    stale_hours: int = STALE_AFTER_HOURS,
) -> RotationStatus:
    """What the node's record says about its rotating backups. Reads only the local record."""
    moment = now or _now()
    warnings: list[str] = []
    days = _swap_days(swap_days, warnings)
    path = Path(record_path) if record_path is not None else local_record_path()
    entries = read_record(path)

    if not entries:
        warnings.append("No backup to a rotating drive has been recorded on this node.")
        return RotationStatus(
            recorded=False, drives=[], newest_pass_at=None, newest_pass_drive=None,
            newest_pass_age_hours=None, stale=True, stale_hours=stale_hours,
            current_drive=None, current_drive_since=None, current_drive_days=None,
            swap_days=days, swap_due=False, warnings=warnings, record_path=str(path),
        )

    by_drive: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_drive.setdefault(str(entry.get("drive_id")), []).append(entry)

    summaries = []
    for drive_id, runs in by_drive.items():
        passes = [r for r in runs if r.get("hash_check") == PASS]
        last_pass = passes[-1] if passes else None
        last_pass_at = _parse(last_pass["recorded_at"]) if last_pass else None
        summaries.append(DriveSummary(
            drive_id=drive_id, name=str(runs[-1].get("drive_name") or drive_id),
            runs=len(runs), last_run_at=runs[-1]["recorded_at"],
            last_hash_check=str(runs[-1].get("hash_check") or FAIL),
            last_pass_at=last_pass["recorded_at"] if last_pass else None,
            last_pass_age_hours=_hours(moment, last_pass_at) if last_pass_at else None,
        ))
    summaries.sort(key=lambda s: s.name.lower())

    passes = [e for e in entries if e.get("hash_check") == PASS]
    newest_pass = passes[-1] if passes else None
    newest_pass_at = _parse(newest_pass["recorded_at"]) if newest_pass else None
    age = _hours(moment, newest_pass_at) if newest_pass_at else None
    stale = age is None or age > stale_hours
    if newest_pass is None:
        warnings.append("No backup has passed its hash check.")
    elif stale:
        warnings.append(
            f"The newest checked backup is {age:.0f} hours old -- older than {stale_hours} hours.")

    last = entries[-1]
    if last.get("hash_check") != PASS:
        warnings.append(
            f"The last backup run ({last['recorded_at']}, {last.get('drive_name')}) did not pass "
            f"its hash check: {last.get('hash_detail') or last.get('error') or 'no detail'}")
    elif not last.get("sources_complete", True):
        warnings.append(
            f"The last backup run ({last['recorded_at']}) was missing a configured source.")

    # The current drive is the one the last run used; it has been "in use" since the first
    # run of the unbroken streak of runs onto it.
    current_id = last.get("drive_id")
    since = last
    for entry in reversed(entries):
        if entry.get("drive_id") != current_id:
            break
        since = entry
    since_at = _parse(since["recorded_at"])
    in_use_days = round((moment - since_at).total_seconds() / 86400.0, 1) if since_at else None
    swap_due = in_use_days is not None and in_use_days >= days
    if swap_due:
        warnings.append(
            f"Time to swap drives: {last.get('drive_name')} has been in use for "
            f"{in_use_days:.0f} days (swap every {days}).")
    if len(by_drive) < 2:
        warnings.append("Only one backup drive has ever been used; rotation needs a second drive.")

    return RotationStatus(
        recorded=True, drives=summaries,
        newest_pass_at=newest_pass["recorded_at"] if newest_pass else None,
        newest_pass_drive=str(newest_pass.get("drive_name")) if newest_pass else None,
        newest_pass_age_hours=age, stale=stale, stale_hours=stale_hours,
        current_drive=str(last.get("drive_name") or current_id),
        current_drive_since=since["recorded_at"], current_drive_days=in_use_days,
        swap_days=days, swap_due=swap_due, warnings=warnings, record_path=str(path),
    )
