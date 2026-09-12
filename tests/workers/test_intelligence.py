"""Tests for Intelligence Worker."""

import pytest
from dispatch.workers.joe.worker import JoeWorker
from dispatch.workers.intelligence.worker import IntelligenceWorker
from dispatch.workers.worker_framework.base import HumanCommitmentRequiredError


def test_intelligence_worker_evaluation_and_scoring():
    joe = JoeWorker()
    intel = IntelligenceWorker(pipeline=joe.pipeline)

    card = joe.create_opportunity_card("Picked up 40000 lbs reefer from Atlanta to Chicago for $3000")
    scored = intel.evaluate_capacity_and_score(card)

    assert scored.score >= 0.0
    assert scored.rpm > 0.0
    assert len(scored.score_reasons) > 0


def test_intelligence_worker_calendar_recommendation():
    joe = JoeWorker()
    intel = IntelligenceWorker(pipeline=joe.pipeline)

    card = joe.create_opportunity_card("Load from Savannah to Charlotte for $1500")
    rec = intel.recommend_calendar_placement(card)

    assert rec["opportunity_id"] == card.opportunity_id
    assert "Mike decides" in rec["notice"]


def test_intelligence_worker_refuses_commitment():
    joe = JoeWorker()
    intel = IntelligenceWorker(pipeline=joe.pipeline)

    card = joe.create_opportunity_card("Load from Denver to Salt Lake for $1800")

    with pytest.raises(HumanCommitmentRequiredError):
        intel.commit_opportunity(card.opportunity_id)
