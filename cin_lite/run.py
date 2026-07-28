"""Automation Layer — orchestrator.

Runs the full Phase-1 pipeline end-to-end:

    acquire -> process (rule modules) -> render control email
            -> collect decision -> archive + record routing

Run from the project root:

    python -m cin_lite.run                      # interactive decision per contract
    python -m cin_lite.run --action reject      # non-interactive (same action for all)
    python -m cin_lite.run --list-actions
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from cin_lite import acquisition, processing, archive, control, email_delivery
from cin_lite.agents.summarizer import SummarizerAgent
from cin_lite.agents.router import RouterAgent
from cin_lite.agents.manager import AgentManager
from cin_lite.workflows import proposal


def run(action_override: str | None) -> None:
    contracts = acquisition.acquire()
    if not contracts:
        print("No contracts acquired. Add JSON files under cin_lite/sample_data/.")
        return

    print(f"Acquired {len(contracts)} contract(s).\n")

    with AgentManager() as mgr:
        mgr.register(SummarizerAgent())
        mgr.register(RouterAgent())
        mgr.initialize_all({})

        for contract in contracts:
            contract["_acquired_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            intelligence = processing.process(contract)
            flags = processing.all_flags(intelligence)

            summary = mgr.execute("summarizer", {
                "contract": contract,
                "intelligence": intelligence,
                "flags": flags,
            })
            decision = mgr.execute("router", {
                "contract": contract,
                "intelligence": intelligence,
                "summary": summary,
                "flags": flags,
            })

            email = control.render_email(contract, intelligence, summary, flags, decision)
            print(email)

            action = control.collect(default=action_override, recommended=decision["action"])
            label, route = control.resolve(action)

            metadata = archive.store(contract, intelligence, summary)
            routing_path = archive.record_routing(
                metadata["contract_id"], action, route, metadata, decision
            )
            email_status = email_delivery.deliver_decision(
                contract, metadata["contract_id"], summary, decision, action, route, flags
            )

            print(f"\n-> {metadata['contract_id']}: {label} -> routed to {route}")
            print(f"   archived under {archive.ARCHIVE_ROOT}")
            print(f"   routing record: {routing_path}")
            print(f"   email: {email_status}")

            if proposal.is_triggered(action):
                result = proposal.trigger(
                    contract, metadata["contract_id"], intelligence, decision, summary, flags
                )
                print(f"   proposal triggered: {result['proposal_id']}")
                print(f"     outline: {result['outline_path']}")
                print(f"     kickoff email: {result['email_status']}")
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
