"""Tests for Worker Framework Handoff Pipeline."""

import pytest
from dispatch.workers.joe.worker import JoeWorker
from dispatch.workers.intelligence.worker import IntelligenceWorker
from dispatch.workers.publisher.worker import PublisherWorker
from dispatch.workers.worker_framework.base import (
    HandoffRunner,
    WorkerRegistry,
)


def test_full_worker_pipeline_handoffs():
    registry = WorkerRegistry()
    joe = JoeWorker()
    intel = IntelligenceWorker(pipeline=joe.pipeline)
    pub = PublisherWorker()

    registry.register(joe)
    registry.register(intel)
    registry.register(pub)

    runner = HandoffRunner(registry)

    # 1. Joe captures voice & creates Opportunity Card
    card = joe.create_opportunity_card("Picked up 42000 lbs reefer from Atlanta to Chicago for $2800")
    ho1 = runner.dispatch_handoff(
        source_worker_id="JOE",
        target_worker_id="INTELLIGENCE",
        trigger="VOICE_CAPTURE_COMPLETED",
        input_data={"dictation": "Picked up 42000 lbs reefer..."},
        output_data={"opportunity_id": card.opportunity_id},
        record_updated=card.opportunity_id,
    )
    assert ho1.source_worker == "JOE"
    assert ho1.target_worker == "INTELLIGENCE"

    # 2. Intelligence scores card & presents for Mike
    scored = intel.evaluate_capacity_and_score(card)
    intel.present_to_mike(card)
    ho2 = runner.dispatch_handoff(
        source_worker_id="INTELLIGENCE",
        target_worker_id="MIKE",
        trigger="EVALUATION_AND_SCORING_COMPLETED",
        input_data={"opportunity_id": card.opportunity_id},
        output_data={"score": scored.score, "notice": intel.RECOMMENDATION_NOTICE},
        record_updated=card.opportunity_id,
    )
    assert ho2.source_worker == "INTELLIGENCE"
    assert ho2.target_worker == "MIKE"

    # 3. Simulated Mike Commitment Gate (Human action)
    realized_load = joe.pipeline.request_commitment(card.opportunity_id, human_actor="Mike Zachary")
    realized_dict = joe.pipeline.realize_commitment(card.opportunity_id, actor_id="Mike Zachary")

    # 4. Publisher consumes committed Mission Card and produces packet + email draft
    packet = pub.generate_rate_confirmation_packet(realized_dict)
    draft = pub.prepare_outlook_draft(packet)

    ho3 = runner.dispatch_handoff(
        source_worker_id="PUBLISHER",
        target_worker_id="HUMAN_OUTLOOK_REVIEW",
        trigger="PACKET_AND_DRAFT_GENERATED",
        input_data={"load_id": realized_dict["load_id"]},
        output_data={"draft_id": draft["draft_id"], "status": draft["status"]},
        record_updated=packet["packet_id"],
    )
    assert ho3.source_worker == "PUBLISHER"
    assert ho3.target_worker == "HUMAN_OUTLOOK_REVIEW"
    assert len(runner.history) == 3
