"""Tests for Publisher Worker."""

import pytest
from dispatch.workers.publisher.worker import PublisherWorker
from dispatch.workers.worker_framework.base import HumanCommitmentRequiredError


def test_publisher_worker_packet_and_draft_generation():
    publisher = PublisherWorker()
    mission = {
        "load_id": "LOAD-999",
        "customer": "CH ROBINSON",
        "pickup_location": "Atlanta, GA",
        "delivery_location": "Chicago, IL",
        "offered_rate": 2750.0,
        "equipment": "53FT REEFER",
    }

    packet = publisher.generate_rate_confirmation_packet(mission)
    assert packet["load_id"] == "LOAD-999"
    assert packet["customer"] == "CH ROBINSON"
    assert packet["rate"] == 2750.0

    draft = publisher.prepare_outlook_draft(packet)
    assert draft["status"] == "DRAFT_READY_FOR_HUMAN_REVIEW"
    assert draft["approved_by"] is None
    assert "LOAD-999" in draft["subject"]


def test_publisher_worker_refuses_autonomous_send():
    publisher = PublisherWorker()
    mission = {"load_id": "LOAD-888", "customer": "TQL", "offered_rate": 1900.0}
    packet = publisher.generate_rate_confirmation_packet(mission)
    draft = publisher.prepare_outlook_draft(packet)

    with pytest.raises(HumanCommitmentRequiredError):
        publisher.send_email_autonomously(draft)
