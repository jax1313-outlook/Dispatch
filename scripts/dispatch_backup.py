#!/usr/bin/env python3
"""Operator entry point for Dispatch backup, verify and restore.

Kept as a thin shell over dispatch.backup: everything that decides what is
captured or whether a restore is safe lives in the engine, so the behaviour an
operator gets from this script is the same behaviour the test suite exercises.
The exit code is the part automation reads -- non-zero whenever a source was
missing or a hash did not match, so a scheduled backup that quietly stopped
capturing a directory shows up as a failed job instead of a green one.

    python3 scripts/dispatch_backup.py backup  /mnt/backup [--compress] [--dry-run]
    python3 scripts/dispatch_backup.py verify  /mnt/backup/dispatch-backup-...
    python3 scripts/dispatch_backup.py restore /mnt/backup/dispatch-backup-... /srv/restored

See BACKUP_AND_RECOVERY.md for the full procedure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Importable when the repository is not installed: an operator recovering a dead
# machine runs this from a checkout, before `pip install -e .` has been possible.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch import backup as backup_engine  # noqa: E402


def _print_sources(result: backup_engine.BackupResult) -> None:
    for source in result.manifest.get("sources", []):
        state = "ok" if source["present"] else f"ABSENT ({source['reason']})"
        print(f"  {','.join(source['roles']):<28} {source['path']}  [{state}]")


def _cmd_backup(args: argparse.Namespace) -> int:
    result = backup_engine.create_backup(
        args.destination, dry_run=args.dry_run, compress=args.compress, name=args.name,
    )
    verb = "would capture" if result.dry_run else "captured"
    print(f"{'DRY RUN: ' if result.dry_run else ''}{result.archive_path}")
    _print_sources(result)
    print(f"  {verb} {result.file_count} files, {result.total_bytes:,} bytes")
    for note in result.notes:
        print(f"  note: {note}")
    for absent in result.absent_sources:
        print(f"  MISSING: {absent['roles']} -> {absent['path']} ({absent['reason']})", file=sys.stderr)
    if not result.ok:
        print("backup incomplete: one or more configured sources were missing", file=sys.stderr)
        return 2
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    result = backup_engine.verify(args.archive)
    print(f"{result.archive_path}: {result.describe()}")
    for rel in result.unexpected:
        print(f"  note: file not listed in the manifest: {rel}")
    return 0 if result.ok else 1


def _cmd_restore(args: argparse.Namespace) -> int:
    try:
        result = backup_engine.restore(
            args.archive, args.destination, force=args.force, dry_run=args.dry_run,
        )
    except backup_engine.DestinationNotEmptyError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    except backup_engine.BackupIntegrityError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 4

    prefix = "DRY RUN: would restore" if result.dry_run else "restored"
    print(f"{prefix} {len(result.restored)} files to {result.destination}")
    if result.database_path:
        print(f"  database: {result.database_path}")
    if result.paths_rehomed:
        print(f"  repointed {result.paths_rehomed} stored file paths at the restored copies")
    print("  start the application with:")
    for var, value in sorted(result.env.items()):
        print(f"    {var}={value}")
    print("  secrets are not in the archive; re-supply them from your password store "
          "(the manifest lists which names were set).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dispatch_backup", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="capture the operational estate")
    p_backup.add_argument("destination", type=Path, help="directory to write the archive into")
    p_backup.add_argument("--compress", action="store_true", help="produce a .tar.gz instead of a directory")
    p_backup.add_argument("--dry-run", action="store_true", help="report the plan, write nothing")
    p_backup.add_argument("--name", default=None, help="override the timestamped archive name")
    p_backup.set_defaults(func=_cmd_backup)

    p_verify = sub.add_parser("verify", help="recompute every hash in an archive")
    p_verify.add_argument("archive", type=Path)
    p_verify.set_defaults(func=_cmd_verify)

    p_restore = sub.add_parser("restore", help="rebuild the estate from an archive")
    p_restore.add_argument("archive", type=Path)
    p_restore.add_argument("destination", type=Path, help="empty directory to restore into")
    p_restore.add_argument("--force", action="store_true", help="allow a non-empty destination")
    p_restore.add_argument("--dry-run", action="store_true", help="report what would be written, write nothing")
    p_restore.set_defaults(func=_cmd_restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
