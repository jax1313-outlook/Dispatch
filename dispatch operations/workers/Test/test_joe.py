"""Tests for Joe Worker."""

import sys
from pathlib import Path
import pytest

WORKERS_DIR = Path(__file__).resolve().parent.parent
if str(WORKERS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKERS_DIR))

from Joe.worker import JoeWorker
from worker_framework.base import HumanCommitmentRequiredError


def test_joe_worker_parse_dictation():
    worker = JoeWorker()
    dictation = "Picked up 42,000 lbs reefer from Atlanta, GA to Chicago, IL for $2,800 on Friday"
    parsed = worker.parse_dictation(dictation)

    assert parsed["origin_location"] == "Atlanta, GA"
    assert parsed["destination_location"] == "Chicago, IL"
    assert parsed["offered_rate"] == 2800.0
    assert parsed["weight_lbs"] == 42000.0
    assert parsed["equipment_type"] == "53FT REEFER"


def test_joe_worker_create_opportunity_card():
    worker = JoeWorker()
    dictation = "Picked up 38,000 lbs van from Dallas, TX to Nashville, TN for $2,100"
    card = worker.create_opportunity_card(dictation)

    assert card.opportunity_id.startswith("OPP-")
    assert card.origin_location == "Dallas, TX"
    assert card.destination_location == "Nashville, TN"
    assert card.offered_rate == 2100.0


def test_joe_worker_refuses_commitment():
    worker = JoeWorker()
    card = worker.create_opportunity_card("Shipment from Miami to Orlando for $900")

    with pytest.raises(HumanCommitmentRequiredError):
        worker.commit_load(card.opportunity_id)
