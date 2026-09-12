"""Tests for Intelligence Worker."""

import sys
from pathlib import Path
import pytest

WORKERS_DIR = Path(__file__).resolve().parent.parent
if str(WORKERS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKERS_DIR))

from Joe.worker import JoeWorker
from intelligence.worker import IntelligenceWorker
from worker_framework.base import HumanCommitmentRequiredError


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
