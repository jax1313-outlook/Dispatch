"""Automation Layer — CLI orchestrator.

Runs the full Phase-1 pipeline end-to-end:

    acquire -> process (rule modules) -> render checkpoint email
            -> [email mode] store pending decision + send HTML email to reviewer
            -> [CLI mode]   collect decision interactively -> archive + route

Run from the project root:

    python -m cin_lite.run                      # email mode: send checkpoint, await decision
    python -m cin_lite.run --action reject      # non-interactive (same action for all)
    python -m cin_lite.run --list-actions
"""

from __future__ import annotations

import argparse

from cin_lite import control
from cin_lite.pipeline import process_contracts


def run(action_override: str | None) -> None:
    results = process_contracts(action_override)
    if not results:
        print("No contracts acquired. Add JSON files under cin_lite/sample_data/.")
        return

    print(f"Processed {len(results)} contract(s).\n")

    for r in results:
        if r["status"] == "error":
            print(f"  ERROR: {r['title']}")
            print(f"    {r['error']}")
            print()
            continue

        print(f"  {r['contract_id']}: {r['title']}")
        print(f"    recommendation: {r['recommendation']} (priority {r['priority']})")
        print(f"    flags: {r['flag_count']}")
        print(f"    checkpoint email: {r['checkpoint_email']}")
        if r["status"] == "decided":
            print(f"    -> {r['action_label']} -> {r['route']}")
            if "proposal" in r:
                print(f"    proposal triggered: {r['proposal']['proposal_id']}")
        else:
            print(f"    awaiting decision via email or portal")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid CIN-Lite — Phase 1 pipeline")
    parser.add_argument(
        "--action",
        choices=list(control.ACTIONS),
        help="Apply this control action to every contract (non-interactive).",
    )
    parser.add_argument(
        "--list-actions", action="store_true", help="List valid control actions and exit."
    )
    args = parser.parse_args()

    if args.list_actions:
        for key, (label, route) in control.ACTIONS.items():
            print(f"{key:<16} {label}  ->  {route}")
        return

    run(args.action)


if __name__ == "__main__":
    main()
