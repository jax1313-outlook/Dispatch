"""CLI entry point for the Dispatch Synchronization Utility."""

from __future__ import annotations

import argparse
import logging
import sys

from sync.config import SyncConfig
from sync.engine import SyncEngine
from sync.transport import SFTPTransport, LocalTransport


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dispatch-sync",
        description="Dispatch Synchronization Utility — pull approved records from VPS",
    )
    p.add_argument(
        "-c", "--config",
        default=None,
        help="Path to sync_config.json (default: sync/sync_config.json)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without writing files",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    p.add_argument(
        "--local-source",
        default=None,
        help="Use a local directory as source instead of SFTP (for testing)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        config = SyncConfig(args.config)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    errors = config.validate()
    if errors and not args.local_source:
        for err in errors:
            print(f"CONFIG ERROR: {err}", file=sys.stderr)
        return 2

    if args.local_source:
        transport = LocalTransport(args.local_source)
    else:
        transport = SFTPTransport(
            hostname=config.vps_hostname,
            port=config.vps_port,
            username=config.vps_username,
            key_path=config.vps_ssh_key_path,
            timeout=config.vps_timeout,
        )

    engine = SyncEngine(config, transport)
    exit_code = engine.run(dry_run=args.dry_run)

    summary = engine.report.summary()
    print(f"\nSync {engine.report.status}")
    print(f"  Checked: {summary['checked']}")
    print(f"  Pulled:  {summary['pulled']}")
    print(f"  Skipped: {summary['skipped']}")
    print(f"  Conflicts: {summary['conflicts']}")
    print(f"  Errors: {summary['errors']}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
