"""Automation Layer — L2-COS Dispatch orchestrator.

Cloned from cin_lite/run.py (Rule 15). Runs the full pipeline end-to-end:

    acquire -> look up Location/Broker intelligence (capture once, Rule 14)
            -> process (rule modules) -> render dispatch control email
            -> collect action -> archive + advance lifecycle stage
            -> [if Intelligence Score >= 90] publisher/auto-contact workflow

Run from the project root:

    python -m l2_cos.run                       # interactive decision per load
    python -m l2_cos.run --action hold_for_review   # non-interactive (same action for all)

The publisher/auto-contact step (System Rule 4) fires on its own — it is
not gated by the human `--action`/interactive decision above. Set
`L2_COS_EMAIL_DRY_RUN=1` to force its outbound email to the safe `.eml`
fallback regardless of SMTP configuration (see l2_cos/email_delivery.py).
"""

from __future__ import annotations

import argparse

from l2_cos import acquisition, archive, control, intelligence_store, processing
from l2_cos.models.state import Load
from l2_cos.workflows import publisher


def run(action_override: str | None) -> None:
    loads = acquisition.acquire()
    if not loads:
        print("No loads acquired. Add JSON files under l2_cos/sample_data/.")
        return

    facilities = intelligence_store.load_facilities()
    brokers = intelligence_store.load_brokers()
    carrier_documents = intelligence_store.load_carrier_documents()

    print(f"Acquired {len(loads)} load(s).\n")

    for raw_load in loads:
        facility_pickup = facilities.get(raw_load.get("pickup_facility_id"))
        facility_delivery = facilities.get(raw_load.get("delivery_facility_id"))
        broker = brokers.get(raw_load.get("broker_id"))

        intelligence = processing.process(
            raw_load,
            facility_pickup=facility_pickup,
            facility_delivery=facility_delivery,
            broker=broker,
        )
        score = processing.overall_score(intelligence)
        metadata = archive.store(raw_load, intelligence, score)

        load = Load(
            load_id=metadata["load_id"],
            pickup_facility_id=raw_load.get("pickup_facility_id"),
            delivery_facility_id=raw_load.get("delivery_facility_id"),
            broker_id=raw_load.get("broker_id"),
            intelligence_score=score,
        )

        email = control.render_email(load, intelligence, facility_pickup, facility_delivery, broker)
        print(email)

        actions = control.available_actions(load)
        action = control.collect(actions, default=action_override)
        target = control.resolve(action, load)

        if target is not None:
            load.advance(target, actor="dispatcher-cli")

        archive.record_dispatch(load)

        print(f"\n-> {load.load_id}: stage {load.stage.value}")

        if publisher.is_triggered(score):
            result = publisher.trigger(load, raw_load, broker, carrier_documents)
            archive.store_inquiry(load.load_id, result)
            if result["sent"]:
                print(f"   publisher: {result['email_status']}")
            else:
                print(f"   publisher: declined to send ({result['reason']})")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="L2-COS Dispatch pipeline")
    parser.add_argument(
        "--action",
        help="Apply this control action to every load (non-interactive), "
        "e.g. BOOKED or hold_for_review.",
    )
    args = parser.parse_args()
    run(args.action)


if __name__ == "__main__":
    main()
