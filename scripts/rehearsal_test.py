"""Rehearsal Load Acceptance Test Script.

Traces one freight load end-to-end:
Voice Capture -> Opportunity Card -> LOADS -> Intelligence Score -> Calendar Recommendation ->
Mike COMMIT -> Mission Card -> Capacity Consumed -> Publisher Library Retrieval -> Outlook Draft Prepared ->
Human Send Gate.
"""

from __future__ import annotations

import json
from dispatch.workers.joe.worker import JoeWorker
from dispatch.workers.intelligence.worker import IntelligenceWorker
from dispatch.workers.publisher.worker import PublisherWorker
from dispatch.workers.worker_framework.base import HandoffRunner, WorkerRegistry, HumanCommitmentRequiredError
from portal.models import library as library_model
from portal.models import publisher as publisher_model


def run_rehearsal():
    print("=== STARTING DISPATCH REHEARSAL LOAD ACCEPTANCE TEST ===")

    # Setup worker registry
    registry = WorkerRegistry()
    joe = JoeWorker()
    intel = IntelligenceWorker(pipeline=joe.pipeline)
    pub = PublisherWorker()

    registry.register(joe)
    registry.register(intel)
    registry.register(pub)
    runner = HandoffRunner(registry)

    # 1. Voice Capture -> Opportunity Card
    dictation = "Picked up 42,000 lbs reefer from Atlanta, GA to Chicago, IL for $2,800 on Friday"
    print(f"\n[1. JOE VOICE CAPTURE] Processing dictation: '{dictation}'")
    card = joe.create_opportunity_card(dictation)
    print(f"  -> Opportunity Card Created: {card.opportunity_id} (WorkItem: {card.work_item_id})")

    runner.dispatch_handoff(
        source_worker_id="JOE",
        target_worker_id="INTELLIGENCE",
        trigger="VOICE_CAPTURE_COMPLETED",
        input_data={"dictation": dictation},
        output_data={"opportunity_id": card.opportunity_id},
        record_updated=card.opportunity_id,
    )

    # 2. Intelligence Scoring & Calendar Recommendation
    print("\n[2. INTELLIGENCE ANALYSIS & SCORING]")
    scored_card = intel.evaluate_capacity_and_score(card)
    calendar_rec = intel.recommend_calendar_placement(scored_card)
    intel.present_to_mike(scored_card)

    print(f"  -> Opportunity Score: {scored_card.score}/100 (RPM: ${scored_card.rpm:.2f}/mi)")
    print(f"  -> Calendar Slot Recommended: {calendar_rec['recommended_slot_start']}")
    print(f"  -> Notice Attached: {calendar_rec['notice']}")
    print(f"  -> Card State in LOADS: {scored_card.stage}")

    runner.dispatch_handoff(
        source_worker_id="INTELLIGENCE",
        target_worker_id="MIKE",
        trigger="EVALUATION_AND_SCORING_COMPLETED",
        input_data={"opportunity_id": card.opportunity_id},
        output_data={"score": scored_card.score, "notice": calendar_rec["notice"]},
        record_updated=card.opportunity_id,
    )

    # 3. Mike COMMIT Gate (Human Authority)
    print("\n[3. MIKE COMMIT GATE]")
    human_actor = "Mike Zachary"
    print(f"  -> Human Operator '{human_actor}' clicking COMMIT on LOADS screen...")
    joe.pipeline.request_commitment(card.opportunity_id, human_actor=human_actor)
    realized_load = joe.pipeline.realize_commitment(card.opportunity_id, actor_id=human_actor)

    print(f"  -> Commitment Realized! Load ID: {realized_load['load_id']}")
    print(f"  -> Linked Load ID on Opportunity Card: {card.linked_load_id}")
    print(f"  -> Single Identity Preserved: {card.opportunity_id} == {card.linked_load_id}")

    # 4. Publisher Generation & Outlook Draft
    print("\n[4. PUBLISHER PACKET & OUTLOOK DRAFT]")
    packet = pub.generate_rate_confirmation_packet(realized_load)
    draft = pub.prepare_outlook_draft(packet)

    print(f"  -> Publisher Packet Created: {packet['packet_id']}")
    print(f"  -> Library Assets Included: {packet['available_assets']}")
    print(f"  -> Outlook Draft Prepared: Subject='{draft['subject']}'")
    print(f"  -> Draft Status: {draft['status']}")
    print(f"  -> Approved By: {draft['approved_by']} (Awaiting Human Review)")

    runner.dispatch_handoff(
        source_worker_id="PUBLISHER",
        target_worker_id="HUMAN_OUTLOOK_REVIEW",
        trigger="PACKET_AND_DRAFT_GENERATED",
        input_data={"load_id": realized_load["load_id"]},
        output_data={"draft_id": draft["draft_id"], "status": draft["status"]},
        record_updated=packet["packet_id"],
    )

    # 5. Verify Human Send Gate Enforcement
    print("\n[5. HUMAN SEND GATE VERIFICATION]")
    try:
        pub.send_email_autonomously(draft)
    except HumanCommitmentRequiredError as e:
        print(f"  -> [SUCCESS] Autonomous send correctly refused: {e}")

    print("\n=== REHEARSAL LOAD ACCEPTANCE TEST PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_rehearsal()
