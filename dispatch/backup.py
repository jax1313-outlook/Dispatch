"""Backup and restore for the entire operational estate.

Dispatch keeps the business in four places at once: a SQLite database, a set of
JSON stores the portal read-modify-writes, uploaded evidence files, and the
archive/library/memory trees. Nothing tied those together, so a disk failure was
an unrecoverable loss of the business rather than an afternoon of downtime. This
module is the tie.

Three properties drive every design decision here:

*Nothing is copied silently and nothing is omitted silently.* A backup that
quietly skipped a directory because an env var moved it is worse than no backup
at all -- it fails at restore time, months later, when the data is already gone.
Every configured source is resolved through the *same* function the application
resolves it with, and a source that is missing is recorded in the manifest as
absent with a reason and surfaced in the result.

*The archive is the restore image.* The layout inside the archive is exactly the
layout `restore()` writes, so an operator who has lost the tooling can recover by
copying directories by hand and pointing the documented env vars at them. See
BACKUP_AND_RECOVERY.md.

*The database is copied by SQLite, not by the filesystem.* `get_connection()`
opens the database in WAL mode, so at any instant the committed truth is split
between `dispatch.db` and `dispatch.db-wal`. Copying the file alone captures a
torn database that silently loses the most recent commits. `sqlite3.Connection.
backup()` takes a transactionally consistent snapshot of a *live* database, which
is the only correct way to do this while the portal is running. The raw file and
its -wal/-shm siblings are therefore excluded from the plain file walk.

Secrets are never written into the archive: env var *names* are recorded so a
recovery operator knows what must be re-supplied, but any name that looks like a
credential is stored with a redaction placeholder instead of its value.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

TOOL_VERSION = "1.0.0"

# Bumped only when the on-disk manifest shape changes in a way an older reader
# would misinterpret. restore() refuses a manifest it does not understand rather
# than half-restoring one.
MANIFEST_VERSION = 1

MANIFEST_NAME = "manifest.json"
REDACTED = "<redacted, not exported>"

# Substring match, not exact match: the real variables in this repo are
# PORTAL_SECRET_KEY, DISPATCH_EMAIL_SECRET and DISPATCH_SAM_API_KEY, and a
# future one will be named something nobody listed here. Matching on the marker
# means a new credential is redacted by default; the failure mode of this test
# being too eager is an unhelpful manifest, and of it being too narrow is a
# secret on a backup drive.
_SECRET_MARKERS = ("SECRET", "KEY", "PASSWORD", "TOKEN", "CREDENTIAL")
_ENV_PREFIXES = ("DISPATCH_", "PORTAL_")

# Written alongside the database by SQLite itself; they are meaningless without
# the exact database file they belong to, and backup() captures their contents
# through the SQLite backup API instead.
_DB_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")

_CHUNK = 1024 * 1024


class BackupError(Exception):
    """Base class so a caller can catch every failure this module raises."""


class BackupIntegrityError(BackupError):
    """An archive's contents do not match its manifest.

    Raised by restore() *before* anything is written. A backup that fails its own
    hashes is not a backup; writing part of it over a destination would turn a
    detectable problem into a silent one.
    """


class DestinationNotEmptyError(BackupError):
    """restore() was pointed at a directory that already contains something.

    Restores happen under pressure, from a shell, with a path that may have been
    typed rather than pasted. Overwriting whatever is already there is never the
    safe default, so this is raised unless the caller passes force=True.
    """


class ManifestError(BackupError):
    """The archive has no readable manifest, or one from a future format."""


# ── source resolution ──────────────────────────────────────────────────

def _resolve_portal_data() -> Path:
    from portal.models import get_data_dir

    return get_data_dir()


def _resolve_uploads() -> Path:
    # Deliberately the application's own resolver rather than a copy of its
    # logic. dispatch.services._get_upload_dir() creates the directory if it is
    # absent -- a side effect even in dry-run mode -- which is accepted on
    # purpose: a second implementation of the same five-branch env lookup is how
    # a backup ends up pointed at a directory the app stopped using.
    from dispatch.services import _get_upload_dir

    return _get_upload_dir()


def _resolve_archive_records() -> Path:
    from portal.models import get_archive_dir

    return get_archive_dir()


def _resolve_memory() -> Path:
    from portal.models import get_memory_dir

    return get_memory_dir()


def _resolve_cin_archive() -> Path:
    # Read as a module attribute, never imported by value: cin_lite.archive
    # computes ARCHIVE_ROOT once at import time and the test suite rebinds it,
    # so `from cin_lite.archive import ARCHIVE_ROOT` would freeze whatever the
    # value happened to be when this module was first imported.
    import cin_lite.archive as cin_archive

    return Path(cin_archive.ARCHIVE_ROOT)


@dataclass(frozen=True)
class _SourceSpec:
    """One thing that must survive a disk failure.

    `label` is the directory name this source gets inside the archive when it is
    not nested inside another source; `env_var` is what a recovery operator sets
    to point the application at the restored copy.
    """

    role: str
    label: str
    env_var: str | None
    recursive: bool
    resolve: Callable[[], Path]


_SOURCES: tuple[_SourceSpec, ...] = (
    _SourceSpec("portal_data", "PortalData", "PORTAL_DATA_DIR", False, _resolve_portal_data),
    _SourceSpec("uploads", "Uploads", "PORTAL_UPLOAD_DIR", True, _resolve_uploads),
    _SourceSpec("archive_records", "ArchiveRecords", "DISPATCH_ARCHIVE_ROOT", True, _resolve_archive_records),
    _SourceSpec("memory", "Memory", "DISPATCH_MEMORY_ROOT", True, _resolve_memory),
    _SourceSpec("cin_archive", "CIN", "DISPATCH_ARCHIVE_PATH", True, _resolve_cin_archive),
)

# Tables whose rows carry an absolute filesystem path. Restoring onto a new
# machine moves every one of those files, so the rows have to move with them --
# see _rehome_database_paths().
_PATH_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("evidence", "evidence_id", "file_path"),
    ("ifta_fuel_evidence", "evidence_id", "file_path"),
    ("pod_packages", "pod_id", "file_path"),
)


@dataclass
class _Root:
    """A distinct directory on disk, and every role that resolves to it.

    Several roles collapse onto one directory in the default configuration --
    get_archive_dir() and get_memory_dir() both fall back to get_data_dir() --
    and on the D-drive layout they are three separate trees. Grouping by
    resolved directory means the archive holds one copy either way and the
    restored layout reproduces whichever topology the source had.
    """

    path: Path
    roles: list[str]
    env_vars: list[str]
    recursive: bool
    rel: str
    present: bool = True
    absent_reason: str = ""
    error: str = ""


def _norm(path: Path) -> Path:
    # resolve() collapses symlinks and relative segments so that two roles
    # reaching the same directory by different spellings group together, and it
    # is non-strict, so a configured-but-absent root still normalises.
    return Path(os.path.abspath(str(path)))


def _plan_roots() -> list[_Root]:
    roots: dict[str, _Root] = {}
    order: list[str] = []

    for spec in _SOURCES:
        try:
            resolved = _norm(spec.resolve())
        except Exception as exc:  # noqa: BLE001 - a broken resolver must not take the backup with it
            roots[f"!error:{spec.role}"] = _Root(
                path=Path(spec.label), roles=[spec.role],
                env_vars=[spec.env_var] if spec.env_var else [],
                recursive=spec.recursive, rel=spec.label, present=False,
                absent_reason=f"could not resolve source: {exc}",
                error=f"{type(exc).__name__}: {exc}",
            )
            order.append(f"!error:{spec.role}")
            continue

        key = os.path.normcase(str(resolved))
        existing = roots.get(key)
        if existing is not None:
            existing.roles.append(spec.role)
            existing.recursive = existing.recursive or spec.recursive
            if spec.env_var:
                existing.env_vars.append(spec.env_var)
            continue

        roots[key] = _Root(
            path=resolved, roles=[spec.role],
            env_vars=[spec.env_var] if spec.env_var else [],
            recursive=spec.recursive, rel=spec.label,
        )
        order.append(key)

    planned = [roots[k] for k in order]
    _assign_relative_layout(planned)

    for root in planned:
        if root.error:
            continue
        if not root.path.exists():
            root.present = False
            root.absent_reason = "directory does not exist"
        elif not root.path.is_dir():
            root.present = False
            root.absent_reason = "path exists but is not a directory"
    return planned


def _assign_relative_layout(planned: list[_Root]) -> None:
    """Give each root its position inside the archive, preserving nesting.

    The default configuration puts the upload directory *inside* the portal data
    directory. If each root were dropped at the archive's top level, restoring
    would flatten that nesting and PORTAL_UPLOAD_DIR would no longer sit where
    the portal's own fallback expects it. Placing a nested root at the same
    relative offset under its parent means the restored tree has the same shape
    as the tree that was backed up -- so the identical file reached through both
    roots also lands at one identical archive path, which is what makes the
    dedupe in _plan_files() correct rather than lossy.

    Shallowest first, so a parent's own position is final before a child asks
    for it (nesting can be more than one level deep).
    """
    for root in sorted(planned, key=lambda r: len(r.path.parts)):
        if root.error:
            continue
        parent: _Root | None = None
        for other in planned:
            if other is root or other.error:
                continue
            if len(other.path.parts) >= len(root.path.parts):
                continue
            if root.path.is_relative_to(other.path):
                if parent is None or len(other.path.parts) > len(parent.path.parts):
                    parent = other
        if parent is not None:
            root.rel = f"{parent.rel}/{root.path.relative_to(parent.path).as_posix()}"


# ── file planning ──────────────────────────────────────────────────────

@dataclass
class _PlannedFile:
    source: Path
    rel: str
    roles: str
    size: int


def _is_scratch(path: Path) -> bool:
    """Skip the temp files atomic_write_json leaves mid-write.

    portal.models.atomic_write_json writes to `.<name>.<rand>.tmp` in the store's
    own directory and then os.replace()s it. Capturing one would archive a
    half-written store under a name nothing reads.
    """
    return path.name.startswith(".") and path.name.endswith(".tmp")


def _is_db_artifact(path: Path, db_path: Path) -> bool:
    if path == db_path:
        return True
    return any(path.name == db_path.name + suffix for suffix in _DB_SIDECAR_SUFFIXES)


def _iter_files(root: _Root) -> Iterator[Path]:
    if root.recursive:
        yield from sorted(p for p in root.path.rglob("*"))
    else:
        # portal_data's contract is "every *.json in the portal data dir" -- the
        # stores themselves, not the uploads subtree beneath them.
        yield from sorted(root.path.glob("*.json"))


def _plan_files(
    roots: list[_Root], db_path: Path, exclude_under: Path | None,
) -> tuple[list[_PlannedFile], list[str]]:
    """Walk every present root once, dropping duplicates by archive position."""
    claimed: dict[str, _PlannedFile] = {}
    notes: list[str] = []

    for root in roots:
        if not root.present:
            continue
        role_label = ",".join(root.roles)
        for path in _iter_files(root):
            if path.is_dir():
                continue
            if path.is_symlink():
                notes.append(f"skipped symlink (not followed): {path}")
                continue
            if not path.is_file():
                continue
            if _is_scratch(path):
                continue
            if _is_db_artifact(path, db_path):
                notes.append(
                    f"skipped {path.name}: the operational database is captured "
                    "through the SQLite backup API, not copied as a file"
                )
                continue
            if exclude_under is not None and path.is_relative_to(exclude_under):
                notes.append(f"skipped {path}: inside the backup destination itself")
                continue

            rel_within = path.relative_to(root.path).as_posix()
            rel = f"{root.rel}/{rel_within}"
            if rel in claimed:
                # Two roles reached the same file. Because nested roots keep
                # their relative offset, "same archive path" means "same file",
                # so one copy satisfies both roles.
                continue
            claimed[rel] = _PlannedFile(source=path, rel=rel, roles=role_label, size=path.stat().st_size)

    return list(claimed.values()), notes


def _database_rel(db_path: Path, roots: list[_Root]) -> str:
    """Where the database snapshot lives inside the archive.

    Normally the database sits inside the portal data directory, and it belongs
    at that same offset in the archive so a restored PORTAL_DATA_DIR contains it
    exactly where dispatch.db._default_db_path() will look. When the path has
    been overridden to somewhere outside every backed-up root it gets its own
    top-level directory instead -- and RestoreResult.database_path names it, so
    it is never lost.
    """
    for root in sorted((r for r in roots if not r.error), key=lambda r: -len(r.path.parts)):
        if db_path.parent.is_relative_to(root.path):
            rel_within = db_path.relative_to(root.path).as_posix()
            return f"{root.rel}/{rel_within}"
    return f"Database/{db_path.name}"


# ── hashing ────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ── database snapshot ──────────────────────────────────────────────────

def _snapshot_database(src: Path, dest: Path) -> None:
    """Copy a live, possibly WAL-mode database consistently."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src))
    try:
        dest_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()


def _read_database_shape(path: Path) -> dict[str, Any]:
    """Row counts and schema DDL, read from the snapshot rather than the source.

    Reading the copy is the point: the manifest then describes what is actually
    in the archive, so a restore can be checked against it. Counting the live
    database instead would describe a moving target.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.row_factory = sqlite3.Row
        objects = conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        schema = [
            {"type": r["type"], "name": r["name"], "table": r["tbl_name"], "sql": r["sql"] or ""}
            for r in objects
        ]
        counts: dict[str, int] = {}
        for row in objects:
            if row["type"] != "table":
                continue
            name = row["name"]
            counts[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
        return {"schema": schema, "row_counts": counts}
    finally:
        conn.close()


# ── environment capture ────────────────────────────────────────────────

def _is_secret_name(name: str) -> bool:
    upper = name.upper()
    return any(marker in upper for marker in _SECRET_MARKERS)


def capture_environment() -> dict[str, str]:
    """Record the configuration a restore has to reproduce -- minus the secrets.

    A restore is not finished when the bytes are back: the application also has
    to be pointed at them, and told the credentials it talks to the outside world
    with. The names are the part a recovery operator needs (they say *what* must
    be re-supplied); the values of anything credential-shaped stay out of the
    archive entirely, because backup media travel and get copied to places the
    live config never goes.
    """
    captured: dict[str, str] = {}
    for name in sorted(os.environ):
        if not name.startswith(_ENV_PREFIXES):
            continue
        captured[name] = REDACTED if _is_secret_name(name) else os.environ[name]
    return captured


# ── results ────────────────────────────────────────────────────────────

@dataclass
class BackupResult:
    archive_path: Path
    manifest: dict[str, Any]
    file_count: int
    total_bytes: int
    absent_sources: list[dict[str, str]]
    notes: list[str]
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        """True when every configured source was present.

        Deliberately not "the copy did not raise": a backup that ran cleanly
        while one of its five sources had moved out from under it is the exact
        failure this module exists to make loud.
        """
        return not self.absent_sources


@dataclass
class VerifyResult:
    archive_path: Path
    checked: int
    mismatched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatched and not self.missing

    def describe(self) -> str:
        if self.ok:
            return f"{self.checked} files verified, all hashes match"
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} missing: {', '.join(self.missing[:5])}")
        if self.mismatched:
            parts.append(f"{len(self.mismatched)} hash mismatch: {', '.join(self.mismatched[:5])}")
        return "; ".join(parts)


@dataclass
class RestoreResult:
    archive_path: Path
    destination: Path
    restored: list[str]
    env: dict[str, str]
    database_path: Path | None
    paths_rehomed: int = 0
    notes: list[str] = field(default_factory=list)
    dry_run: bool = False


# ── backup ─────────────────────────────────────────────────────────────

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_backup(
    destination: Path | str,
    *,
    dry_run: bool = False,
    compress: bool = False,
    name: str | None = None,
) -> BackupResult:
    """Capture the whole estate into a timestamped archive under *destination*.

    With compress=True the staged directory is rolled into a .tar.gz and removed,
    for backup media where one file is easier to move than a tree. Either form is
    accepted by verify() and restore().

    dry_run reports the exact plan -- every source, every file, every byte count,
    every absent directory -- and writes nothing. Hashes are absent from a dry
    run by design: hashing the database snapshot would require taking one.
    """
    destination = Path(destination)
    roots = _plan_roots()
    db_path = _norm(_current_db_path())
    db_rel = _database_rel(db_path, roots)

    archive_name = name or f"dispatch-backup-{_timestamp()}"
    archive_dir = destination / archive_name

    # Backing up into a directory that is itself inside a backed-up root would
    # otherwise walk the archive into itself.
    exclude_under = _norm(destination) if any(
        (not r.error) and _norm(destination).is_relative_to(r.path) for r in roots
    ) else None

    planned, notes = _plan_files(roots, db_path, exclude_under)
    absent = [
        {"roles": ",".join(r.roles), "path": str(r.path), "reason": r.absent_reason}
        for r in roots if not r.present
    ]

    db_present = db_path.is_file()
    if not db_present:
        absent.append({
            "roles": "database", "path": str(db_path),
            "reason": "database file does not exist",
        })

    source_summary = [
        {
            "roles": r.roles,
            "env_vars": r.env_vars,
            "path": str(r.path),
            "archive_path": r.rel,
            "present": r.present,
            "reason": r.absent_reason,
            "recursive": r.recursive,
        }
        for r in roots
    ]

    if dry_run:
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "tool_version": TOOL_VERSION,
            "created_at": _utc_now_iso(),
            "dry_run": True,
            "archive_name": archive_name,
            "sources": source_summary,
            "database": {
                "source_path": str(db_path),
                "archive_path": db_rel,
                "present": db_present,
            },
            "files": [
                {"path": f.rel, "size": f.size, "sha256": None, "source": f.roles, "origin": str(f.source)}
                for f in planned
            ],
            "absent": absent,
            "environment": capture_environment(),
            "notes": notes,
        }
        return BackupResult(
            archive_path=archive_dir, manifest=manifest, file_count=len(planned),
            total_bytes=sum(f.size for f in planned), absent_sources=absent,
            notes=notes, dry_run=True,
        )

    archive_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    database_meta: dict[str, Any] = {
        "source_path": str(db_path),
        "archive_path": db_rel,
        "present": db_present,
    }

    if db_present:
        db_dest = archive_dir / db_rel
        _snapshot_database(db_path, db_dest)
        database_meta.update(_read_database_shape(db_dest))
        entries.append({
            "path": db_rel, "size": db_dest.stat().st_size,
            "sha256": sha256_file(db_dest), "source": "database", "origin": str(db_path),
        })

    for planned_file in planned:
        dest_file = archive_dir / planned_file.rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(planned_file.source, dest_file)
        entries.append({
            "path": planned_file.rel, "size": dest_file.stat().st_size,
            "sha256": sha256_file(dest_file), "source": planned_file.roles,
            "origin": str(planned_file.source),
        })

    # Roots that exist but hold no files still need to come back as directories,
    # otherwise a restored env var points at nothing and the first write fails.
    empty_roots = sorted({
        r.rel for r in roots
        if r.present and not any(e["path"].startswith(r.rel + "/") for e in entries)
    })

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "tool_version": TOOL_VERSION,
        "created_at": _utc_now_iso(),
        "dry_run": False,
        "archive_name": archive_name,
        "sources": source_summary,
        "database": database_meta,
        "files": sorted(entries, key=lambda e: e["path"]),
        "empty_directories": empty_roots,
        "absent": absent,
        "environment": capture_environment(),
        "notes": notes,
    }
    (archive_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    archive_path = archive_dir
    if compress:
        archive_path = destination / f"{archive_name}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(archive_dir, arcname=archive_name)
        shutil.rmtree(archive_dir)

    return BackupResult(
        archive_path=archive_path, manifest=manifest, file_count=len(entries),
        total_bytes=sum(int(e["size"]) for e in entries), absent_sources=absent, notes=notes,
    )


def _current_db_path() -> Path:
    from dispatch.db import get_db_path

    return Path(get_db_path())


# ── reading an archive ─────────────────────────────────────────────────

def _looks_like_tar(path: Path) -> bool:
    return path.is_file() and (
        path.name.endswith(".tar.gz") or path.name.endswith(".tgz") or path.name.endswith(".tar")
    )


@contextmanager
def _opened(archive: Path | str) -> Iterator[Path]:
    """Yield a directory holding the archive, extracting a tarball if needed."""
    archive = Path(archive)
    if archive.is_dir():
        yield archive
        return
    if not _looks_like_tar(archive):
        raise ManifestError(f"not a Dispatch backup archive: {archive}")

    tmp = Path(tempfile.mkdtemp(prefix="dispatch-restore-"))
    try:
        with tarfile.open(archive) as tar:
            # filter="data" refuses absolute paths, parent-directory escapes,
            # device files and setuid bits -- a backup tarball is untrusted input
            # the moment it comes back from off-site media.
            tar.extractall(tmp, filter="data")
        entries = [p for p in tmp.iterdir()]
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp
        yield root
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def read_manifest(archive_dir: Path) -> dict[str, Any]:
    path = archive_dir / MANIFEST_NAME
    if not path.is_file():
        raise ManifestError(f"no {MANIFEST_NAME} in {archive_dir}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"unreadable {MANIFEST_NAME} in {archive_dir}: {exc}") from exc
    version = manifest.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ManifestError(
            f"manifest version {version!r} is not supported by tool version {TOOL_VERSION} "
            f"(expected {MANIFEST_VERSION})"
        )
    return manifest


def _verify_dir(archive_dir: Path, manifest: dict[str, Any]) -> VerifyResult:
    result = VerifyResult(archive_path=archive_dir, checked=0)
    recorded: set[str] = set()

    for entry in manifest.get("files", []):
        rel = entry["path"]
        recorded.add(rel)
        path = archive_dir / rel
        if not path.is_file():
            result.missing.append(rel)
            continue
        result.checked += 1
        if path.stat().st_size != entry["size"] or sha256_file(path) != entry["sha256"]:
            result.mismatched.append(rel)

    for path in archive_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(archive_dir).as_posix()
        if rel == MANIFEST_NAME or rel in recorded:
            continue
        # Not a failure by itself, but an operator should know the archive holds
        # something its own manifest never described.
        result.unexpected.append(rel)

    return result


def verify(archive: Path | str) -> VerifyResult:
    """Recompute every hash in the archive and report what does not match."""
    with _opened(archive) as archive_dir:
        manifest = read_manifest(archive_dir)
        result = _verify_dir(archive_dir, manifest)
        result.archive_path = Path(archive)
        return result


# ── restore ────────────────────────────────────────────────────────────

def _destination_is_occupied(destination: Path) -> bool:
    return destination.exists() and any(destination.iterdir())


def _restored_env(manifest: dict[str, Any], destination: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for source in manifest.get("sources", []):
        if not source.get("present"):
            continue
        target = destination / source["archive_path"]
        for var in source.get("env_vars", []):
            env[var] = str(target)
    return env


def _normalise_for_compare(value: str) -> str:
    return value.replace("\\", "/").rstrip("/")


def _rehome_database_paths(db_file: Path, manifest: dict[str, Any], destination: Path) -> int:
    """Repoint absolute file paths stored in the database at the restored files.

    dispatch.services.attach_evidence() stores the *absolute* path of every
    uploaded file in evidence.file_path. Restoring onto a new machine -- or into
    a staging directory to test the backup -- moves every one of those files, so
    without this pass the database comes back intact and every download link in
    it is dead. The rewrite is deliberately conservative: only values that sit
    under a root this archive actually captured are touched, longest root first
    so a nested root wins over its parent.
    """
    mapping: list[tuple[str, str]] = []
    for source in manifest.get("sources", []):
        if not source.get("present"):
            continue
        mapping.append((
            _normalise_for_compare(source["path"]),
            str(destination / source["archive_path"]),
        ))
    mapping.sort(key=lambda pair: -len(pair[0]))
    if not mapping:
        return 0

    # Windows sources restored on POSIX (and the reverse) still have to match;
    # drive letters make case-insensitive comparison the safe choice there.
    def remap(value: str) -> str | None:
        norm = _normalise_for_compare(value)
        for old, new in mapping:
            candidates = (norm, norm.lower()) if ":" in old[:3] else (norm,)
            probe = old.lower() if ":" in old[:3] else old
            for candidate in candidates:
                if candidate == probe:
                    return new
                if candidate.startswith(probe + "/"):
                    return str(Path(new) / candidate[len(probe) + 1:])
        return None

    changed = 0
    conn = sqlite3.connect(str(db_file))
    try:
        existing = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table, key_col, path_col in _PATH_COLUMNS:
            if table not in existing:
                continue
            rows = conn.execute(
                f'SELECT "{key_col}", "{path_col}" FROM "{table}" WHERE "{path_col}" IS NOT NULL'
            ).fetchall()
            for key, old_value in rows:
                if not old_value:
                    continue
                new_value = remap(str(old_value))
                if new_value is not None and new_value != old_value:
                    conn.execute(
                        f'UPDATE "{table}" SET "{path_col}"=? WHERE "{key_col}"=?',
                        (new_value, key),
                    )
                    changed += 1
        conn.commit()
    finally:
        conn.close()
    return changed


def restore(
    archive: Path | str,
    destination: Path | str,
    *,
    force: bool = False,
    dry_run: bool = False,
    rehome_paths: bool = True,
) -> RestoreResult:
    """Rebuild the estate from *archive* into *destination*.

    Order matters and is the whole safety story: the destination is checked, then
    every hash in the archive is recomputed, and only if both pass does a single
    byte get written. A corrupted archive therefore leaves the destination
    exactly as it found it, rather than half-populated with plausible-looking
    data nobody later questions.

    Returns the env var -> directory mapping the application must be started
    with; the restored tree is inert until something points at it.
    """
    destination = Path(destination)
    with _opened(archive) as archive_dir:
        manifest = read_manifest(archive_dir)

        if _destination_is_occupied(destination) and not force:
            raise DestinationNotEmptyError(
                f"{destination} is not empty; refusing to restore over existing data "
                "(pass force=True to overwrite)"
            )

        check = _verify_dir(archive_dir, manifest)
        if not check.ok:
            raise BackupIntegrityError(
                f"archive failed verification, nothing was written: {check.describe()}"
            )

        files = sorted(manifest.get("files", []), key=lambda e: e["path"])
        env = _restored_env(manifest, destination)
        db_rel = manifest.get("database", {}).get("archive_path")
        db_present = bool(manifest.get("database", {}).get("present"))
        db_target = destination / db_rel if (db_rel and db_present) else None
        notes = list(manifest.get("notes", []))

        if dry_run:
            return RestoreResult(
                archive_path=Path(archive), destination=destination,
                restored=[e["path"] for e in files], env=env,
                database_path=db_target, notes=notes, dry_run=True,
            )

        destination.mkdir(parents=True, exist_ok=True)
        for entry in files:
            target = destination / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive_dir / entry["path"], target)

        for rel in manifest.get("empty_directories", []):
            (destination / rel).mkdir(parents=True, exist_ok=True)

        rehomed = 0
        if rehome_paths and db_target is not None and db_target.is_file():
            rehomed = _rehome_database_paths(db_target, manifest, destination)

        return RestoreResult(
            archive_path=Path(archive), destination=destination,
            restored=[e["path"] for e in files], env=env, database_path=db_target,
            paths_rehomed=rehomed, notes=notes,
        )
