"""Tests for reconciliation.adapters.archive_adapter (Stage 4 — pure translation, no I/O)."""
from __future__ import annotations

from reconciliation.adapters.archive_adapter import (
    adapt_all,
    dispatch_archive_record_to_canonical_view,
    unverified_publisher_archive_count,
)


def _publisher_archive_record(**overrides):
    base = {
        "id": "ARC-PUB-0001",
        "section": "publisher",
        "source_id": "PUB-0001",
        "title": "Broker Packet Required — SBX-1",
        "record_data": {"id": "PUB-0001", "status": "ARCHIVED"},
        "decision_summary": "Publisher action completed: ARCHIVED",
        "evidence": {},
        "archived_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_publisher_record_with_no_approved_by_is_unverified():
    view = dispatch_archive_record_to_canonical_view(_publisher_archive_record())
    assert view.had_verified_approval is False


def test_publisher_record_with_real_approver_is_verified():
    record = _publisher_archive_record()
    record["record_data"]["approved_by"] = "Mike Zachary"
    view = dispatch_archive_record_to_canonical_view(record)
    assert view.had_verified_approval is True


def test_publisher_record_with_system_identity_approver_is_not_verified():
    record = _publisher_archive_record()
    record["record_data"]["approved_by"] = "PUBLISHER"
    view = dispatch_archive_record_to_canonical_view(record)
    assert view.had_verified_approval is False


def test_non_publisher_section_reports_false_not_applicable():
    record = _publisher_archive_record(section="load", id="ARC-LOA-0001")
    view = dispatch_archive_record_to_canonical_view(record)
    assert view.had_verified_approval is False
    assert view.section == "load"


def test_unverified_publisher_archive_count_counts_correctly():
    verified = _publisher_archive_record(id="ARC-PUB-0001")
    verified["record_data"]["approved_by"] = "Mike Zachary"
    unverified = _publisher_archive_record(id="ARC-PUB-0002", source_id="PUB-0002")
    non_publisher = _publisher_archive_record(id="ARC-LOA-0001", section="load")

    data = {
        "publisher": [verified, unverified],
        "load": [non_publisher],
    }
    # Only the one unverified publisher record should count -- the verified publisher record
    # and the non-publisher-section record must not.
    assert unverified_publisher_archive_count(data) == 1


def test_adapt_all_processes_every_section():
    data = {
        "publisher": [_publisher_archive_record()],
        "load": [_publisher_archive_record(id="ARC-LOA-0001", section="load")],
    }
    views = adapt_all(data)
    assert len(views) == 2
