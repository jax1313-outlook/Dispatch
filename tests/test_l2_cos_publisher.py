"""Tests for the Publisher / Auto-Contact workflow (System Rule 4)."""

from __future__ import annotations

from l2_cos import archive, email_delivery, intelligence_store
from l2_cos.models.intelligence import PUBLISH_THRESHOLD, InquiryArtifacts
from l2_cos.models.state import Load
from l2_cos.workflows import publisher

RAW_LOAD = {
    "origin": "Riverside, CA",
    "destination": "Dallas, TX",
    "equipment_type": "Dry Van",
    "rate_per_mile": 2.2,
}

COMPLETE_ARTIFACTS = InquiryArtifacts(
    business_card=True,
    w9=True,
    insurance=True,
    authority=True,
    rate_sheet=True,
    terms=True,
    rate_confirmation_package=True,
)


def test_is_triggered_threshold():
    assert not publisher.is_triggered(PUBLISH_THRESHOLD - 1)
    assert publisher.is_triggered(PUBLISH_THRESHOLD)


def test_build_artifacts_defaults_to_all_missing():
    artifacts = publisher.build_artifacts(None)
    assert not artifacts.is_complete()
    assert artifacts.business_card is False


def test_trigger_sends_when_artifacts_complete(clean_broker):
    load = Load(load_id="LOAD-TEST-1", intelligence_score=95, broker_id="BRK-001")
    result = publisher.trigger(load, RAW_LOAD, clean_broker, COMPLETE_ARTIFACTS)

    assert result["sent"] is True
    assert result["recipients"] == [clean_broker.contact_email]
    assert "not sent (SMTP not configured)" in result["email_status"]  # offline fallback
    eml = email_delivery._OUTBOX / "LOAD-TEST-1-inquiry.eml"
    assert eml.exists()
    body = eml.read_text(encoding="utf-8")
    assert "Riverside, CA -> Dallas, TX" in body
    assert "Rate Confirmation Package" in body


def test_trigger_uses_fallback_address_without_broker_contact():
    load = Load(load_id="LOAD-TEST-2", intelligence_score=95)
    result = publisher.trigger(load, RAW_LOAD, None, COMPLETE_ARTIFACTS)
    assert result["recipients"] == [email_delivery.fallback_broker_address()]


def test_trigger_declines_when_artifacts_incomplete(clean_broker):
    load = Load(load_id="LOAD-TEST-3", intelligence_score=95)
    incomplete = InquiryArtifacts(business_card=True, w9=True)  # insurance etc. missing
    result = publisher.trigger(load, RAW_LOAD, clean_broker, incomplete)

    assert result["sent"] is False
    assert "Insurance" in result["reason"]
    assert "Rate Confirmation Package" in result["reason"]
    # no email should have been written for a declined inquiry
    assert not (email_delivery._OUTBOX / "LOAD-TEST-3-inquiry.eml").exists()


def test_trigger_result_is_archivable(clean_broker):
    load = Load(load_id="LOAD-TEST-4", intelligence_score=95, broker_id="BRK-001")
    result = publisher.trigger(load, RAW_LOAD, clean_broker, COMPLETE_ARTIFACTS)
    path = archive.store_inquiry(load.load_id, result)
    assert path.exists()


def test_load_carrier_documents_from_sample_data():
    artifacts = intelligence_store.load_carrier_documents()
    assert artifacts.is_complete()
