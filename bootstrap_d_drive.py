#!/usr/bin/env python3
"""Bootstrap D:\\ Drive Migration Utility.

Transfers project creations, operational data, contract archives, and memory files
from the isolated Linux/app environment into the Windows host D:\\ drive target structure.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# Target roots (defaults for Windows host D:\ drive)
DEFAULT_OPS_ROOT = r"D:\Dispatch Operations"
DEFAULT_ARCHIVE_ROOT = r"D:\Archive"
DEFAULT_MEMORY_ROOT = r"D:\Memory"
DEFAULT_SANDBOX_ROOT = r"D:\Sandbox\Jules"


def get_target_paths(
    ops_root: str | None = None,
    archive_root: str | None = None,
    memory_root: str | None = None,
    sandbox_root: str | None = None,
) -> dict[str, Path]:
    ops = Path(
        ops_root
        or os.environ.get("DISPATCH_OPERATIONS_ROOT")
        or DEFAULT_OPS_ROOT
    )
    archive = Path(
        archive_root
        or os.environ.get("DISPATCH_ARCHIVE_ROOT")
        or DEFAULT_ARCHIVE_ROOT
    )
    memory = Path(
        memory_root
        or os.environ.get("DISPATCH_MEMORY_ROOT")
        or DEFAULT_MEMORY_ROOT
    )
    sandbox = Path(
        sandbox_root
        or os.environ.get("DISPATCH_SANDBOX_EXPORT")
        or DEFAULT_SANDBOX_ROOT
    )
    return {
        "ops": ops,
        "archive": archive,
        "memory": memory,
        "sandbox": sandbox,
    }


def copy_tree_safe(
    src: Path,
    dst: Path,
    dry_run: bool = False,
    verbose: bool = False,
    ignore_patterns: tuple[str, ...] = ("__pycache__", ".git", ".pytest_cache", "*.pyc", ".coverage"),
) -> tuple[int, int]:
    """Recursively copy files from src to dst. Returns (copied_files, skipped_files)."""
    copied = 0
    skipped = 0

    if not src.exists():
        if verbose:
            print(f"  [SKIP] Source path does not exist: {src}")
        return 0, 0

    if src.is_file():
        if dry_run:
            print(f"  [WOULD COPY] {src} -> {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if verbose:
                print(f"  [COPIED] {src} -> {dst}")
        return 1, 0

    def should_ignore(name: str) -> bool:
        from fnmatch import fnmatch
        return any(fnmatch(name, pat) for pat in ignore_patterns)

    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if not should_ignore(d)]
        rel_path = Path(root).relative_to(src)
        target_dir = dst / rel_path

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            if should_ignore(f):
                skipped += 1
                continue

            src_file = Path(root) / f
            dst_file = target_dir / f

            if dry_run:
                print(f"  [WOULD COPY] {src_file} -> {dst_file}")
                copied += 1
            else:
                shutil.copy2(src_file, dst_file)
                if verbose:
                    print(f"  [COPIED] {src_file} -> {dst_file}")
                copied += 1

    return copied, skipped


def bootstrap_d_drive(
    ops_root: str | None = None,
    archive_root: str | None = None,
    memory_root: str | None = None,
    sandbox_root: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict[str, int]:
    targets = get_target_paths(ops_root, archive_root, memory_root, sandbox_root)

    print("\n  ==========================================")
    print("  DISPATCH D:\\ Drive Migration Bootstrap")
    print("  ==========================================\n")

    if dry_run:
        print("  [MODE] DRY RUN -- No files will be modified.\n")

    print(f"  Target Operations Root: {targets['ops']}")
    print(f"  Target Archive Root:    {targets['archive']}")
    print(f"  Target Memory Root:     {targets['memory']}")
    print(f"  Target Sandbox Root:    {targets['sandbox']}\n")

    # Ensure root directories exist (if not dry run)
    if not dry_run:
        for key, path in targets.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"  [WARNING] Could not create target directory {path}: {e}")

    total_copied = 0
    total_skipped = 0

    # 1. Transfer codebase to OpsRoot/Code and SandboxRoot
    code_target = targets["ops"] / "Code"
    print(f"--> Syncing codebase to {code_target}...")
    copied, skipped = copy_tree_safe(PROJECT_ROOT, code_target, dry_run=dry_run, verbose=verbose)
    total_copied += copied
    total_skipped += skipped

    print(f"--> Syncing full workspace to {targets['sandbox']}...")
    copied, skipped = copy_tree_safe(PROJECT_ROOT, targets["sandbox"], dry_run=dry_run, verbose=verbose)
    total_copied += copied
    total_skipped += skipped

    # 2. Transfer portal operational data to OpsRoot/Current Workspace/PortalData
    portal_data_src = Path(os.environ.get("PORTAL_DATA_DIR") or (PROJECT_ROOT / "portal" / "data"))
    portal_data_dst = targets["ops"] / "Current Workspace" / "PortalData"
    if portal_data_src.exists():
        print(f"--> Transferring Portal data from {portal_data_src} to {portal_data_dst}...")
        copied, skipped = copy_tree_safe(portal_data_src, portal_data_dst, dry_run=dry_run, verbose=verbose)
        total_copied += copied
        total_skipped += skipped

    # 3. Transfer CIN contract archive to ArchiveRoot/CIN
    cin_archive_src = Path(os.environ.get("DISPATCH_ARCHIVE_PATH") or (PROJECT_ROOT / "cin_lite" / "Archive"))
    cin_archive_dst = targets["archive"] / "CIN"
    if cin_archive_src.exists():
        print(f"--> Transferring Contract Archive from {cin_archive_src} to {cin_archive_dst}...")
        copied, skipped = copy_tree_safe(cin_archive_src, cin_archive_dst, dry_run=dry_run, verbose=verbose)
        total_copied += copied
        total_skipped += skipped

    # 4. Transfer uploads/evidence to MemoryRoot/Evidence
    uploads_src = Path(os.environ.get("PORTAL_UPLOAD_DIR") or (portal_data_src / "uploads"))
    uploads_dst = targets["memory"] / "Evidence"
    if uploads_src.exists():
        print(f"--> Transferring Evidence Uploads from {uploads_src} to {uploads_dst}...")
        copied, skipped = copy_tree_safe(uploads_src, uploads_dst, dry_run=dry_run, verbose=verbose)
        total_copied += copied
        total_skipped += skipped

    print("\n  -- Summary --")
    print(f"  Total files copied/transferred: {total_copied}")
    print(f"  Total files skipped:            {total_skipped}\n")

    if dry_run:
        print("  Dry run complete. Run without --dry-run to apply.")
    else:
        print("  Bootstrap complete. All creations migrated successfully.")

    return {"copied": total_copied, "skipped": total_skipped}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap program to transfer isolated creations and data into the D:\\ drive."
    )
    parser.add_argument("--ops-root", help="Override DISPATCH_OPERATIONS_ROOT")
    parser.add_argument("--archive-root", help="Override DISPATCH_ARCHIVE_ROOT")
    parser.add_argument("--memory-root", help="Override DISPATCH_MEMORY_ROOT")
    parser.add_argument("--sandbox-root", help="Override DISPATCH_SANDBOX_EXPORT")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry-run without copying files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()
    bootstrap_d_drive(
        ops_root=args.ops_root,
        archive_root=args.archive_root,
        memory_root=args.memory_root,
        sandbox_root=args.sandbox_root,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
