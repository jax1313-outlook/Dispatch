#!/usr/bin/env python3
"""Operator entry point for the Dispatch operational-proof system.

Thin shell over dispatch.readiness and dispatch.proof, matching
scripts/dispatch_backup.py: every decision about what a check means or whether a
step passed lives in the engine, so what an operator sees here is exactly what
the test suite exercises. The exit code is what automation reads -- non-zero
whenever a readiness condition is not CONFIGURED or a rehearsal step failed.

    python scripts/dispatch_proof.py readiness --backup-destination D:\\Backups \\
                                               --restore-destination "D:\\Restore Proof"
    python scripts/dispatch_proof.py template  --output proof/load/OPERATIONAL_LOAD_PROOF.md
    python scripts/dispatch_proof.py rehearse  --actor mike-workstation \\
                                               --label "first rehearsal" \\
                                               --backup-destination D:\\Backups \\
                                               --restore-destination "D:\\Restore Proof"
    python scripts/dispatch_proof.py sessions
    python scripts/dispatch_proof.py purge-plan REH-...

Two things this script deliberately will not do:

* It will not run a live revenue load. `rehearse` opens a rehearsal session and
  every record it creates is tagged REHEARSAL at the record level and banners
  itself in every user-facing surface.
* It will not purge anything. `purge-plan` reports what a purge WOULD remove and
  stops there, because purging data on Mike's machine is his decision
  (Operational Readiness Mission, Section 8 item 9).

See docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md for the full procedure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Importable from a checkout, before `pip install -e .` has been possible --
# same reasoning as scripts/dispatch_backup.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch import proof as proof_engine  # noqa: E402
from dispatch import readiness as readiness_engine  # noqa: E402

DEFAULT_REPORT = Path("proof/load/OPERATIONAL_LOAD_PROOF.md")


def _cmd_readiness(args: argparse.Namespace) -> int:
    report = readiness_engine.run_readiness_checks(
        backup_destination=args.backup_destination,
        restore_destination=args.restore_destination,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(readiness_engine.render_readiness(report))
    return 0 if report.ready else 1


def _cmd_template(args: argparse.Namespace) -> int:
    run = proof_engine.template_run(
        backup_destination=str(args.backup_destination or ""),
        restore_destination=str(args.restore_destination or ""),
    )
    if args.with_readiness:
        run.readiness = readiness_engine.run_readiness_checks(
            backup_destination=args.backup_destination,
            restore_destination=args.restore_destination,
        )
    written = proof_engine.write_proof_report(run, args.output)
    print(run.headline)
    print(f"  wrote {written}")
    print(f"  wrote {written.with_suffix('.json')}")
    print(
        "  Every step is ABSENT. This is a template, not proof. Run `rehearse`, then "
        "perform the steps it leaves to you."
    )
    return 0


def _cmd_rehearse(args: argparse.Namespace) -> int:
    readiness = readiness_engine.run_readiness_checks(
        backup_destination=args.backup_destination,
        restore_destination=args.restore_destination,
    )
    if not readiness.ready and not args.ignore_readiness:
        print(readiness_engine.render_readiness(readiness), file=sys.stderr)
        print(
            "\nRefusing to rehearse: the conditions above are not CONFIGURED. "
            "Fix them, or pass --ignore-readiness to rehearse anyway and have the "
            "report say so.",
            file=sys.stderr,
        )
        return 2

    run = proof_engine.automated_rehearsal(
        actor_id=args.actor,
        label=args.label,
        backup_destination=args.backup_destination,
        restore_destination=args.restore_destination,
    )
    run.readiness = readiness
    if args.machine:
        run.machine = args.machine
    if args.outlook:
        run.outlook_status = args.outlook

    written = proof_engine.write_proof_report(run, args.output)
    print(run.headline)
    for step in run.steps:
        print(f"  {step.number:>2}  {step.performer:<15} {step.status:<13} {step.result}")
    print(f"\n  wrote {written}")
    print(f"  rehearsal session {run.rehearsal_session_id}")
    print(
        "\n  The steps still marked `not performed` need a human at the machine. "
        "The report lists the exact action for each."
    )
    return 1 if run.first_failure is not None else 0


def _cmd_sessions(args: argparse.Namespace) -> int:
    from dispatch import rehearsal

    sessions = rehearsal.list_sessions(status=args.status)
    if not sessions:
        print("No rehearsal sessions recorded.")
        return 0
    for s in sessions:
        print(
            f"  {s['session_id']}  {s['status']:<10} {s['started_at']}  "
            f"{s['actor_id']:<24} {s['label']}"
        )
    return 0


def _cmd_purge_plan(args: argparse.Namespace) -> int:
    from dispatch import rehearsal

    plan = rehearsal.plan_purge(args.session_id)
    print(f"Rehearsal session {plan.session_id}")
    for table, count in sorted(plan.counts.items()):
        print(f"  {table:<16} {count}")
    print(f"  {'TOTAL':<16} {plan.total}")
    if plan.evidence_files:
        print("\n  Evidence files on disk:")
        for path in plan.evidence_files:
            print(f"    {path}")
    print(
        "\n  Nothing was deleted. Purging data on this machine is your decision "
        "(Operational Readiness Mission, Section 8 item 9). This command only reports."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dispatch_proof", description=__doc__.splitlines()[0]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _destinations(p: argparse.ArgumentParser) -> None:
        p.add_argument("--backup-destination", type=Path, default=None)
        p.add_argument("--restore-destination", type=Path, default=None)

    p_ready = sub.add_parser("readiness", help="check this machine before a load")
    _destinations(p_ready)
    p_ready.add_argument("--json", action="store_true", help="machine-readable output")
    p_ready.set_defaults(func=_cmd_readiness)

    p_tmpl = sub.add_parser(
        "template", help="write the proof report with every step ABSENT"
    )
    _destinations(p_tmpl)
    p_tmpl.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    p_tmpl.add_argument(
        "--with-readiness", action="store_true", help="include the readiness table"
    )
    p_tmpl.set_defaults(func=_cmd_template)

    p_reh = sub.add_parser(
        "rehearse", help="run the automatable steps of the proof path"
    )
    _destinations(p_reh)
    p_reh.add_argument(
        "--actor", required=True,
        help="the authenticated account performing this rehearsal. Never defaulted.",
    )
    p_reh.add_argument("--label", required=True, help="a name for this rehearsal")
    p_reh.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    p_reh.add_argument(
        "--machine", default="", help="the machine this ran on, for the report header"
    )
    p_reh.add_argument(
        "--outlook", choices=["LIVE", "SIMULATED", "MANUAL", "ABSENT"], default=None,
        help="step 9's Outlook status, recorded by you",
    )
    p_reh.add_argument(
        "--ignore-readiness", action="store_true",
        help="rehearse even when a readiness condition is not CONFIGURED",
    )
    p_reh.set_defaults(func=_cmd_rehearse)

    p_sess = sub.add_parser("sessions", help="list rehearsal sessions")
    p_sess.add_argument("--status", default=None, choices=["OPEN", "PASSED", "FAILED", "ABANDONED"])
    p_sess.set_defaults(func=_cmd_sessions)

    p_purge = sub.add_parser(
        "purge-plan", help="report what purging a rehearsal session would remove"
    )
    p_purge.add_argument("session_id")
    p_purge.set_defaults(func=_cmd_purge_plan)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
