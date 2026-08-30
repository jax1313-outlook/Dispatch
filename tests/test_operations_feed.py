"""Tests for the Operations Feed (portal/models/operations_feed.py) -- the
consequence-sorted, single-screen view of every open decision-worthy item
across Publisher, Conflicts, CIN-Lite pending decisions, Dispatch
exceptions, settlements, stalled loads, review/analysis queues, and
Library asset gaps.

Covers: each source's own card-level mapping, that resolved/closed items
from every source are excluded, that the required "Mike decides" closing
statement appears on level 3+ cards and only those, sort order (highest
consequence first, most-recent-within-level second), and that the
`/operations` page renders the feed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cin_lite import archive as cin_archive, pending as cin_pending
from dispatch import services, store as dispatch_store
from dispatch.db import set_db_path
from portal.models import conflict, library as lib_model, operations_feed, publisher


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _portal_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _age_load(load_id: str, hours: int) -> None:
    old_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dispatch_store.update_load(load_id, updated_at=old_time)


def _satisfy_all_company_assets() -> None:
    for name in lib_model.COMPANY_ASSETS:
        lib_model.add_record("company", name, submitted_by="human")


# ── Empty feed ────────────────────────────────────────────────────────


class TestEmptyFeed:
    def test_nothing_open_is_a_fully_empty_feed(self):
        _satisfy_all_company_assets()
        feed = operations_feed.build_feed()
        assert feed["total"] == 0
        assert feed["cards"] == []
        assert all(count == 0 for count in feed["counts_by_level"].values())

    def test_default_state_only_has_library_gaps(self):
        """With no company assets uploaded, the only cards present should
        be the 10 Library gap cards -- nothing else fabricated."""
        feed = operations_feed.build_feed()
        assert feed["total"] == len(lib_model.COMPANY_ASSETS)
        assert all(c["source"] == "library_gap" for c in feed["cards"])
        assert all(c["card_level"] == 1 for c in feed["cards"])


# ── Publisher -> Authority (5) ──────────────────────────────────────


class TestPublisherCards:
    def test_pending_action_is_authority_level_with_closing(self):
        publisher.create_action(
            "Broker Packet Required", sandbox_id="SBX-1", trigger_reason="New broker lane",
        )
        feed = operations_feed.build_feed()
        pub_cards = [c for c in feed["cards"] if c["source"] == "publisher"]
        assert len(pub_cards) == 1
        assert pub_cards[0]["card_level"] == 5
        assert pub_cards[0]["level_label"] == "Authority"
        assert pub_cards[0]["closing"] == operations_feed.REQUIRED_CARD_CLOSING

    def test_approved_and_archived_actions_excluded(self):
        a1 = publisher.create_action("Rate Sheet Request", sandbox_id="SBX-2", trigger_reason="x")
        publisher.update_action_status(a1["id"], "APPROVED", approved_by="mike")
        a2 = publisher.create_action("Rate Sheet Request", sandbox_id="SBX-3", trigger_reason="y")
        publisher.update_action_status(a2["id"], "DRAFT")
        publisher.update_action_status(a2["id"], "READY")
        publisher.update_action_status(a2["id"], "APPROVED", approved_by="mike")
        publisher.update_action_status(a2["id"], "ARCHIVED")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "publisher"] == []


# ── Conflicts ─────────────────────────────────────────────────────────


class TestConflictCards:
    def test_critical_unresolved_is_conflict_level(self):
        conflict.create_notice(
            "hard_stop", "critical", sandbox_id="SBX-4",
            explanation="Equipment mismatch", recommended_action="Reassign equipment",
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "conflict"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 4
        assert cards[0]["closing"] == operations_feed.REQUIRED_CARD_CLOSING

    def test_info_with_no_human_decision_required_is_capped_at_review(self):
        conflict.create_notice(
            "missing_source_link", "info", sandbox_id="SBX-5",
            explanation="Cosmetic gap", recommended_action="none",
            human_decision_required=False,
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "conflict"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 2
        assert cards[0]["closing"] == ""

    def test_resolved_notice_excluded(self):
        cn = conflict.create_notice(
            "missing_rate", "warning", sandbox_id="SBX-6",
            explanation="No rate on file", recommended_action="Confirm rate",
        )
        conflict.resolve_notice(cn["id"], resolution_note="Rate confirmed")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "conflict"] == []


# ── CIN-Lite pending contract decisions ────────────────────────────────


class TestGovconPendingCards:
    def test_high_priority_pending_decision_is_conflict_level(self):
        cin_pending.store(
            "CIN-TEST-0001",
            contract={"title": "Zero Trust Support"},
            intelligence={},
            summary="Set-aside, sole-source indicators.",
            decision={"action": "approve_archive", "priority": "high"},
            flags=["set_aside", "sole_source"],
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "govcon_pending"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 4
        assert cards[0]["title"] == "Zero Trust Support"

    def test_default_priority_pending_decision_is_decision_level(self):
        cin_pending.store(
            "CIN-TEST-0002",
            contract={"title": "Routine Custodial"},
            intelligence={},
            summary="No flags.",
            decision={"action": "approve_archive"},
            flags=[],
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "govcon_pending"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 3

    def test_completed_decision_excluded(self):
        cin_pending.store(
            "CIN-TEST-0003", contract={"title": "Done Deal"}, intelligence={},
            summary="", decision={"action": "reject"}, flags=[],
        )
        cin_pending.complete("CIN-TEST-0003")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "govcon_pending"] == []


# ── Dispatch exceptions ─────────────────────────────────────────────


class TestExceptionCards:
    def test_critical_open_exception_is_conflict_level(self):
        load = services.create_load(customer="Exception Feed Co")
        services.open_exception(load["load_id"], exception_type="damage", severity="critical", description="Cargo damaged")
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "exception"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 4
        assert "Exception Feed Co" in cards[0]["title"]

    def test_resolved_exception_excluded(self):
        load = services.create_load(customer="Resolved Exc Co")
        exc = services.open_exception(load["load_id"], exception_type="delay", severity="high", description="Traffic")
        services.resolve_exception(exc["exception_id"], resolution_note="Cleared")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "exception"] == []


# ── Settlements ──────────────────────────────────────────────────────


class TestSettlementCards:
    def test_disputed_settlement_is_conflict_level(self):
        load = services.create_load(customer="Disputed Settle Co")
        services.confirm_rate(load["load_id"], rate_amount=1000, distance_miles=300)
        services.create_settlement(load["load_id"])
        services.dispute_settlement(load["load_id"], reason="Rate mismatch")
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "settlement"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 4

    def test_overdue_settlement_is_decision_level(self):
        load = services.create_load(customer="Overdue Settle Co")
        services.confirm_rate(load["load_id"], rate_amount=1000, distance_miles=300)
        services.create_settlement(load["load_id"], due_date="2020-01-01")
        services.check_overdue_settlements()
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "settlement"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 3

    def test_paid_settlement_excluded(self):
        load = services.create_load(customer="Paid Settle Co")
        services.confirm_rate(load["load_id"], rate_amount=1000, distance_miles=300)
        services.create_settlement(load["load_id"])
        services.record_payment(load["load_id"], payment_amount=1000, payment_method="ach")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "settlement"] == []


# ── Stalled loads ────────────────────────────────────────────────────


class TestStalledLoadCards:
    def test_stalled_load_is_review_level(self):
        load = services.create_load(customer="Stalled Feed Co")
        _age_load(load["load_id"], 30)
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "stalled_load"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 2
        assert cards[0]["closing"] == ""

    def test_fresh_load_not_included(self):
        services.create_load(customer="Fresh Feed Co")
        feed = operations_feed.build_feed()
        assert [c for c in feed["cards"] if c["source"] == "stalled_load"] == []


# ── Queues ───────────────────────────────────────────────────────────


class TestQueueCards:
    def test_human_review_route_is_review_level(self):
        """cin_archive.ARCHIVE_ROOT is already redirected to a per-test tmp
        dir by conftest.py's autouse tmp_archive fixture."""
        cin_archive.ensure_tree()
        cin_archive.record_routing(
            "CIN-Q-0001", action="flag_review", route="HUMAN_REVIEW",
            metadata={}, action_label="Flag for review", summary="Needs a second look",
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "queue_review"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 2

    def test_deep_analysis_route_is_status_level(self):
        cin_archive.ensure_tree()
        cin_archive.record_routing(
            "CIN-Q-0002", action="deeper_analysis", route="DEEP_ANALYSIS_QUEUE",
            metadata={}, action_label="Request deeper analysis", summary="Needs research",
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "queue_analysis"]
        assert len(cards) == 1
        assert cards[0]["card_level"] == 1


# ── Library gaps ─────────────────────────────────────────────────────


class TestLibraryGapCards:
    def test_missing_asset_is_status_level(self):
        feed = operations_feed.build_feed()
        gap_cards = [c for c in feed["cards"] if c["source"] == "library_gap"]
        assert len(gap_cards) == len(lib_model.COMPANY_ASSETS)
        assert all(c["card_level"] == 1 for c in gap_cards)
        assert all(c["closing"] == "" for c in gap_cards)

    def test_uploaded_asset_no_longer_a_gap(self):
        lib_model.add_record("company", "W-9", submitted_by="human")
        feed = operations_feed.build_feed()
        gap_titles = [c["title"] for c in feed["cards"] if c["source"] == "library_gap"]
        assert not any("W-9" in t for t in gap_titles)
        assert len(gap_titles) == len(lib_model.COMPANY_ASSETS) - 1


# ── Sorting ──────────────────────────────────────────────────────────


class TestSorting:
    def test_highest_consequence_sorts_first(self):
        _satisfy_all_company_assets()
        conflict.create_notice(
            "missing_rate", "warning", sandbox_id="SBX-SORT",
            explanation="x", recommended_action="y",
        )  # level 3
        publisher.create_action("Rate Sheet Request", sandbox_id="SBX-SORT", trigger_reason="z")  # level 5
        load = services.create_load(customer="Sort Order Co")
        _age_load(load["load_id"], 30)  # level 2

        feed = operations_feed.build_feed()
        levels = [c["card_level"] for c in feed["cards"]]
        assert levels == sorted(levels, reverse=True)
        assert feed["cards"][0]["source"] == "publisher"

    def test_within_level_most_recent_first(self, monkeypatch):
        """create_notice()'s timestamp has only 1-second resolution, so two
        real calls in the same test can tie -- force distinct clock values
        instead of relying on wall-clock ordering."""
        _satisfy_all_company_assets()
        monkeypatch.setattr(conflict, "_utc_now", lambda: "2026-01-01T00:00:00Z")
        older = conflict.create_notice(
            "missing_rate", "warning", sandbox_id="SBX-OLD",
            explanation="older", recommended_action="y",
        )
        monkeypatch.setattr(conflict, "_utc_now", lambda: "2026-01-02T00:00:00Z")
        newer = conflict.create_notice(
            "missing_pickup_window", "warning", sandbox_id="SBX-NEW",
            explanation="newer", recommended_action="y",
        )
        feed = operations_feed.build_feed()
        cards = [c for c in feed["cards"] if c["source"] == "conflict"]
        assert cards[0]["card_id"] == f"conflict-{newer['id']}"
        assert cards[1]["card_id"] == f"conflict-{older['id']}"


# ── Route ────────────────────────────────────────────────────────────


class TestOperationsRoute:
    def test_page_renders(self, client):
        resp = client.get("/operations")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Operations" in html

    def test_page_shows_a_card(self, client):
        publisher.create_action("Broker Packet Required", sandbox_id="SBX-ROUTE", trigger_reason="x")
        resp = client.get("/operations")
        html = resp.data.decode("utf-8")
        assert "Broker Packet Required" in html
        assert operations_feed.REQUIRED_CARD_CLOSING in html
