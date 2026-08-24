#!/usr/bin/env python3
"""Operator entry point for the read-only Sandbox survey.

    python scripts\\sandbox_survey.py --dry-run
    python scripts\\sandbox_survey.py

Defaults target ``D:\\Sandbox\\Play Pen``, writing to ``D:\\Sandbox\\Play Pen\\Dispatch``.
Both are overridable; the output folder must be inside the Sandbox folder or the
run is refused, because that subfolder is the only write location this work is
authorised to touch.

WHAT THIS COMMAND DOES: opens every file under the Sandbox in read-only mode,
hashes it, reads the first `--max-bytes` for heuristics, classifies it against
named deterministic rules, groups exact and near duplicates, flags sensitive
material by path and category, and writes ten timestamped documents into the
output folder.

WHAT IT DOES NOT DO, EVER: move, rename, delete, overwrite, deduplicate,
convert, archive, upload or commit anything; execute any script, notebook or
binary it finds; follow a link out of the Sandbox; open a network connection; or
act on any of the actions it proposes. Executing PROPOSED_ORGANIZATION_ACTIONS
is a separate decision by Mike, with tooling that is not this tool.

Kept as a thin shell over `dispatch.sandbox_survey`, in the same shape as
`scripts/dispatch_backup.py`: every rule that decides what is read, what is
written and what is refused lives in the package, so the behaviour an operator
gets is the behaviour the test suite exercises.

Exit codes: 0 success, 2 a safety rule refused the run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Importable from a checkout that has not been `pip install -e .`-ed: Mike runs
# this on a Windows machine, possibly straight out of a cloned folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dispatch.sandbox_survey import safety, scanner, survey  # noqa: E402

DEFAULT_SANDBOX_ROOT = r"D:\Sandbox\Play Pen"
DEFAULT_OUTPUT_FOLDER_NAME = "Dispatch"


def _resolve_output_argument(sandbox_root: str, output_root: str | None) -> str:
    """Default the output folder to `<sandbox>\\Dispatch`, whatever the sandbox is.

    Hard-coding the full default output path would mean that pointing
    `--sandbox-root` at a copy of the folder silently kept writing into the
    original D: drive location -- the one way this tool could touch a directory
    the operator did not mean to touch.
    """
    if output_root:
        return output_root
    return str(Path(sandbox_root) / DEFAULT_OUTPUT_FOLDER_NAME)


def _print_summary(result: survey.SurveyResult, written: list[Path], dry_run: bool) -> None:
    counts = result.counts()
    print()
    print("DISPATCH Sandbox survey — READ-ONLY PASS, NO FILES WERE MODIFIED")
    print(f"  Sandbox read : {result.sandbox_root}")
    print(f"  Output folder: {result.output_root}")
    print(f"  Run id       : {result.run_id}")
    print()
    print(f"  {counts['files']:,} files inventoried across {counts['directories']:,} folders "
          f"({counts['total_bytes']:,} bytes)")
    print(f"  {counts['dispatch_related']:,} look Dispatch-related, "
          f"{counts['files'] - counts['dispatch_related']:,} do not")
    print(f"  {counts['unreadable']:,} could not be read, or were links that were not followed "
          "(inventoried as Unknown, never skipped)")
    print()
    print("  by primary class:")
    for name, value in counts["by_primary_class"].items():
        if value:
            print(f"    {name:<12} {value:>7,}")
    print()
    print(f"  {counts['exact_duplicate_groups']:,} byte-identical duplicate groups, "
          f"{counts['near_duplicate_groups']:,} near-duplicate groups")
    print(f"  {counts['sensitive_files']:,} files tripped a sensitive-material detector "
          "(paths and categories only — no contents are reported anywhere)")
    print(f"  {counts['doctrine_candidates']:,} doctrine CANDIDATES, {counts['doctrine']:,} matched "
          "doctrine already locked")
    print(f"  {counts['decision_candidates']:,} decision CANDIDATES, {counts['decisions']:,} record a "
          "decision with an identifiable actor")
    print(f"  {counts['prior_output_files']:,} files were already in the output folder; they are "
          "listed separately and were not overwritten")
    print()
    for note in result.notes:
        print(f"  note: {note}")
    if result.notes:
        print()
    verb = "would write" if dry_run else "wrote"
    print(f"  {verb} {len(written)} documents:")
    for path in written:
        print(f"    {path.name}")
    print()
    print("  Nothing in these reports is accepted doctrine or a Mike decision.")
    print("  PROPOSED_ORGANIZATION_ACTIONS has not been executed and this tool cannot")
    print("  execute it. Read docs/readiness/SANDBOX_SURVEY_PROCEDURE.md before acting.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sandbox_survey",
        description="Read-only survey of a Sandbox working folder. Writes nothing "
                    "outside the designated output folder and modifies nothing at all.",
    )
    parser.add_argument(
        "--sandbox-root", default=DEFAULT_SANDBOX_ROOT,
        help=f"folder to survey, read-only (default: {DEFAULT_SANDBOX_ROOT})",
    )
    parser.add_argument(
        "--output-root", default=None,
        help="the ONE folder this tool may write to; must be inside --sandbox-root "
             f"(default: <sandbox-root>\\{DEFAULT_OUTPUT_FOLDER_NAME})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="scan and report to stdout; create no folder and write no file",
    )
    parser.add_argument(
        "--max-bytes", type=int, default=scanner.DEFAULT_MAX_BYTES,
        help="how much of each file is read for classification heuristics "
             f"(default: {scanner.DEFAULT_MAX_BYTES}); the whole file is always hashed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_bytes < 1:
        print("refused: --max-bytes must be at least 1", file=sys.stderr)
        return 2

    output_root = _resolve_output_argument(args.sandbox_root, args.output_root)
    try:
        result = survey.run_survey(
            args.sandbox_root, output_root,
            max_bytes=args.max_bytes, dry_run=args.dry_run,
        )
        writer = safety.OutputWriter(output_root=Path(result.output_root), dry_run=args.dry_run)
        written = survey.write_reports(result, writer)
    except safety.SandboxSafetyError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        print("Nothing was read and nothing was written.", file=sys.stderr)
        return 2

    _print_summary(result, written, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
