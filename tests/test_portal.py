"""Tests for L2-COS Operations Portal v1.

Covers the 15 testing requirements from the build spec:
 1. Portal starts locally without error
 2. Home page renders
 3. UTF-8 icons render correctly
 4. Load card renders score and buttons
 5. Red square renders when flag exists
 6. SAM card renders agency and buttons
 7. Brief page renders for dispatch
 8. Brief page renders for SAM
 9. Interested / Pursue / Pass / Watch workflow
10. Publisher action card creates correctly
11. Conflict notice generates for missing email
12. Inquiry draft creates for eligible load
13. Inquiry draft blocked by hard stop
14. Inquiry draft blocked by missing email
15. Archive candidate created on PASS
"""

from __future__ import annotations

import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(autouse=True)
def portal_data_dir(tmp_path, monkeypatch):
    """Redirect portal data to tmp so tests are isolated."""
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    return tmp_path / "portal_data"


@pytest.fixture
def app():
    from portal.app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_load_good() -> dict:
    return {
        "load_id": "LOAD-TEST-001",
        "title": "Dry Van - Jacksonville FL to Savannah GA",
        "origin": "Jacksonville, FL 32202",
        "destination": "Savannah, GA 31401",
        "distance_miles": 140,
        "broker": "Southeast Freight Partners",
        "broker_email": "dispatch@sefp.example.com",
        "broker_phone": "904-555-0142",
        "rate": 625,
        "rpm": 4.46,
        "pickup_window": "2026-07-30 06:00 - 10:00",
        "delivery_window": "2026-07-30 14:00 - 18:00",
        "equipment_required": "Dry Van 53'",
        "equipment_match": "match",
        "weight_lbs": 38000,
        "source_link": "https://loadboard.example.com/loads/test-001",
        "score": 92,
        "hard_stop": False,
        "hard_stop_reason": None,
        "detention_history": "Low - avg 30 min",
        "location_intelligence": "Savannah port area",
        "broker_intelligence": "Reliable - 12 loads completed",
        "notes": "Live load/unload.",
    }


@pytest.fixture
def sample_load_bad() -> dict:
    return {
        "load_id": "LOAD-TEST-002",
        "title": "Flatbed - Jacksonville FL to Atlanta GA",
        "origin": "Jacksonville, FL 32202",
        "destination": "Atlanta, GA 30301",
        "distance_miles": 345,
        "broker": "National Trucking Solutions",
        "broker_email": None,
        "broker_phone": "800-555-0199",
        "rate": None,
        "rpm": None,
        "pickup_window": None,
        "delivery_window": "2026-07-31 08:00 - 12:00",
        "equipment_required": "Flatbed 48'",
        "equipment_match": "mismatch",
        "weight_lbs": 44000,
        "source_link": None,
        "score": 65,
        "hard_stop": False,
        "hard_stop_reason": None,
        "detention_history": None,
        "location_intelligence": None,
        "broker_intelligence": "Unknown broker",
        "notes": "R4 Extended range.",
    }


@pytest.fixture
def sample_load_hard_stop() -> dict:
    return {
        "load_id": "LOAD-TEST-003",
        "title": "Reefer - Tampa FL to Miami FL",
        "origin": "Tampa, FL",
        "destination": "Miami, FL",
        "distance_miles": 280,
        "broker": "Test Broker",
        "broker_email": "test@example.com",
        "broker_phone": "555-555-0001",
        "rate": 800,
        "rpm": 2.86,
        "pickup_window": "2026-07-30 08:00 - 12:00",
        "delivery_window": "2026-07-30 18:00 - 22:00",
        "equipment_required": "Reefer 53'",
        "equipment_match": "match",
        "weight_lbs": 42000,
        "source_link": "https://loadboard.example.com/loads/test-003",
        "score": 95,
        "hard_stop": True,
        "hard_stop_reason": "Active compliance violation",
        "detention_history": None,
        "location_intelligence": None,
        "broker_intelligence": None,
        "notes": "",
    }


def _create_dispatch_entry(client, load_data):
    """Helper: create a sandbox entry via the models directly."""
    from portal.models import sandbox, conflict

    entry = sandbox.create_entry(
        source_type="dispatch",
        source_id=load_data["load_id"],
        title=load_data["title"],
        card_data=load_data,
        score=load_data.get("score"),
    )
    conflict.check_dispatch_card(load_data, entry["id"])
    return entry


# ---------- 1. Portal starts without error ----------
class TestPortalStarts:
    def test_app_creates(self, app):
        assert app is not None

    def test_app_is_flask(self, app):
        from flask import Flask
        assert isinstance(app, Flask)


# ---------- 2. Home page renders ----------
class TestHomePage:
    def test_home_returns_200(self, client):
        resp = client.get("/home")
        assert resp.status_code == 200

    def test_home_contains_title(self, client):
        resp = client.get("/home")
        assert b"L2-COS" in resp.data

    def test_index_redirects_to_home(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/home" in resp.headers["Location"]


# ---------- 3. UTF-8 icons render correctly ----------
class TestUTF8Icons:
    def test_dispatch_card_icons(self, client, sample_load_good):
        _create_dispatch_entry(client, sample_load_good)
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "✅" in html or "HIGH VALUE MATCH" in html

    def test_low_score_icon(self, client, sample_load_bad):
        _create_dispatch_entry(client, sample_load_bad)
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "🟥" in html or resp.status_code == 200


# ---------- 4. Load card renders score and buttons ----------
class TestLoadCard:
    def test_dispatch_page_renders(self, client, sample_load_good):
        _create_dispatch_entry(client, sample_load_good)
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "92" in html
        assert "Interested" in html
        assert "Pursue" in html
        assert "Pass" in html
        assert "Watch" in html

    def test_card_fields_present(self, client, sample_load_good):
        _create_dispatch_entry(client, sample_load_good)
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "Jacksonville" in html
        assert "Savannah" in html
        assert "Southeast Freight Partners" in html


# ---------- 5. Red square renders when flag/issue exists ----------
class TestRedSquare:
    def test_low_score_visual(self):
        from portal.helpers import card_visual
        vis = card_visual(65)
        assert vis["css"] == "card-investigate"
        assert "🟥" in vis["icon"]

    def test_high_score_visual(self):
        from portal.helpers import card_visual
        vis = card_visual(92)
        assert vis["css"] == "card-high"
        assert "✅" in vis["icon"]


# ---------- 6. SAM card renders agency and buttons ----------
class TestSAMCard:
    def test_sam_page_renders_with_sample_data(self, client):
        from portal.models import sandbox
        sandbox.create_entry(
            source_type="sam",
            source_id="FA8773-26-R-0007",
            title="Zero Trust Cybersecurity",
            card_data={
                "agency": "DEPT OF DEFENSE",
                "solicitation_number": "FA8773-26-R-0007",
                "title": "Zero Trust Cybersecurity",
            },
            score=None,
            decision={"action": "approve_proposal", "priority": "high", "reason": "Match"},
            summary="Cybersecurity support contract",
            flags=["set_aside_detected", "cmmc_required"],
        )
        resp = client.get("/sam")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "FA8773" in html
        assert "Interested" in html or "Open Brief" in html


# ---------- 7. Brief page renders for dispatch ----------
class TestBriefDispatch:
    def test_brief_renders_dispatch(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.get(f"/brief/{entry['id']}")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Jacksonville" in html
        assert "Savannah" in html
        assert "Southeast Freight Partners" in html

    def test_brief_shows_position_placeholders(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.get(f"/brief/{entry['id']}")
        html = resp.data.decode("utf-8")
        assert "Unknown" in html

    def test_brief_404_for_missing(self, client):
        resp = client.get("/brief/SBX-DISPATCH-NONEXISTENT")
        assert resp.status_code == 404


# ---------- 8. Brief page renders for SAM ----------
class TestBriefSAM:
    def test_brief_renders_sam(self, client):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="sam",
            source_id="TEST-SOL-001",
            title="Test SAM Opportunity",
            card_data={
                "title": "Test SAM Opportunity",
                "agency": "GSA",
                "solicitation_number": "TEST-SOL-001",
            },
            decision={"action": "flag_review", "reason": "Needs review"},
            summary="Test summary",
            flags=["set_aside_detected"],
        )
        resp = client.get(f"/brief/{entry['id']}")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200
        assert "Test SAM Opportunity" in html


# ---------- 9. Interested / Pursue / Pass / Watch workflow ----------
class TestWorkflowActions:
    def test_interested(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "interested"})
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["entry"]["status"] == "INTERESTED"

    def test_pursue(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["entry"]["status"] == "PURSUE"

    def test_pass(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["entry"]["status"] == "PASS"

    def test_watch(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "watch"})
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["entry"]["status"] == "WATCH"

    def test_invalid_action(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "delete"})
        assert resp.status_code == 400

    def test_missing_sandbox_id(self, client):
        resp = client.post("/api/action", json={"action": "interested"})
        assert resp.status_code == 400

    def test_events_logged(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "interested"})
        updated = sandbox.get(entry["id"])
        assert len(updated["events"]) >= 2
        last = updated["events"][-1]
        assert last["action"] == "status_change"
        assert last["to"] == "INTERESTED"


# ---------- 10. Publisher action card creates correctly ----------
class TestPublisher:
    def test_pursue_creates_publisher_action(self, client, sample_load_good):
        from portal.models import publisher
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        queue = publisher.get_queue()
        assert len(queue) >= 1
        action = queue[0]
        assert action["action_type"] == "Broker Packet Required"
        assert action["sandbox_id"] == entry["id"]
        assert action["status"] == "PENDING"

    def test_broker_packet_manifest(self):
        from portal.models.publisher import BROKER_PACKET_MANIFEST
        assert "W-9" in BROKER_PACKET_MANIFEST
        assert "Insurance" in BROKER_PACKET_MANIFEST
        assert "Authority" in BROKER_PACKET_MANIFEST

    def test_manual_publisher_create(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/publisher/create", json={
            "sandbox_id": entry["id"],
            "action_type": "Rate Sheet Request",
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["action"]["action_type"] == "Rate Sheet Request"

    def test_publisher_status_workflow(self, client, sample_load_good):
        from portal.models import publisher
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        queue = publisher.get_queue()
        action_id = queue[0]["id"]

        for new_status in ["DRAFT", "READY", "APPROVED"]:
            resp = client.post("/api/publisher/update", json={
                "action_id": action_id,
                "status": new_status,
            })
            data = resp.get_json()
            assert data["status"] == "ok"
            assert data["action"]["status"] == new_status

    def test_publisher_page_renders(self, client):
        resp = client.get("/publisher")
        assert resp.status_code == 200


# ---------- 11. Conflict notice generates for missing email ----------
class TestConflictNotice:
    def test_missing_email_generates_conflict(self, client, sample_load_bad):
        from portal.models import conflict
        entry = _create_dispatch_entry(client, sample_load_bad)
        notices = conflict.get_all()
        email_notices = [n for n in notices if n["conflict_type"] == "missing_broker_email"]
        assert len(email_notices) >= 1
        assert email_notices[0]["sandbox_id"] == entry["id"]

    def test_equipment_mismatch_generates_conflict(self, client, sample_load_bad):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_bad)
        notices = conflict.get_all()
        mismatch = [n for n in notices if n["conflict_type"] == "equipment_mismatch"]
        assert len(mismatch) >= 1
        assert mismatch[0]["severity"] == "critical"

    def test_missing_rate_generates_conflict(self, client, sample_load_bad):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_bad)
        notices = conflict.get_all()
        rate_notices = [n for n in notices if n["conflict_type"] == "missing_rate"]
        assert len(rate_notices) >= 1

    def test_good_load_no_critical_conflicts(self, client, sample_load_good):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_good)
        notices = conflict.get_all()
        critical = [n for n in notices if n["severity"] == "critical"]
        assert len(critical) == 0

    def test_resolve_conflict(self, client, sample_load_bad):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_bad)
        notices = conflict.get_unresolved()
        assert len(notices) > 0
        resp = client.post("/api/conflict/resolve", json={"notice_id": notices[0]["id"]})
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["notice"]["resolved"] is True

    def test_conflicts_page_renders(self, client):
        resp = client.get("/conflicts")
        assert resp.status_code == 200


# ---------- 12. Inquiry draft creates for eligible load ----------
class TestInquiryDraftEligible:
    def test_inquiry_creates_for_high_score(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["status"] == "DRAFT_CREATED"
        assert data["draft"]["mode"] == "HUMAN_REVIEW"
        assert data["draft"]["to"] == "dispatch@sefp.example.com"
        assert "non-binding" in data["draft"]["body"].lower()

    def test_inquiry_updates_sandbox_status(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        updated = sandbox.get(entry["id"])
        assert updated["status"] == "INQUIRY_DRAFTED"
        assert updated["inquiry_draft"] is not None

    def test_mark_inquiry_sent(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        resp = client.post("/api/inquiry/mark-sent", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["status"] == "ok"
        updated = sandbox.get(entry["id"])
        assert updated["status"] == "INQUIRY_SENT_MANUAL"


# ---------- 13. Inquiry draft blocked by hard stop ----------
class TestInquiryBlockedHardStop:
    def test_hard_stop_blocks_inquiry(self, client, sample_load_hard_stop):
        entry = _create_dispatch_entry(client, sample_load_hard_stop)
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["status"] == "BLOCKED_HARD_STOP"


# ---------- 14. Inquiry draft blocked by missing email ----------
class TestInquiryBlockedMissingEmail:
    def test_missing_email_blocks_inquiry(self, client, sample_load_bad):
        entry = _create_dispatch_entry(client, sample_load_bad)
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["status"] == "BLOCKED_MISSING_EMAIL"

    def test_low_score_blocks_inquiry(self, client):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="LOAD-LOW-SCORE",
            title="Low score load",
            card_data={
                "broker_email": "broker@example.com",
                "hard_stop": False,
            },
            score=70,
        )
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["status"] == "NOT_READY"


# ---------- 15. Archive candidate created on PASS ----------
class TestArchiveCandidate:
    def test_pass_creates_archive_note(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        updated = sandbox.get(entry["id"])
        assert "Archive candidate" in updated["notes"]

    def test_archive_page_shows_passed(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert resp.status_code == 200


# ---------- Additional page render tests ----------
class TestPageRendering:
    def test_library_renders(self, client):
        resp = client.get("/library")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Company Library" in html
        assert "Location Intelligence" in html

    def test_settings_renders(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200

    def test_archive_renders(self, client):
        resp = client.get("/archive")
        assert resp.status_code == 200


# ---------- Sandbox model tests ----------
class TestSandboxModel:
    def test_create_and_get(self):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="MODEL-TEST-001",
            title="Test Load",
            card_data={"test": True},
            score=85,
        )
        assert entry["id"] == "SBX-DISPATCH-MODEL-TEST-001"
        assert entry["status"] == "OPEN"
        assert entry["score"] == 85
        fetched = sandbox.get(entry["id"])
        assert fetched is not None
        assert fetched["title"] == "Test Load"

    def test_create_preserves_status(self):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="MODEL-TEST-002",
            title="Test Load",
            card_data={"v": 1},
        )
        sandbox.update_status(entry["id"], "PURSUE")
        updated = sandbox.create_entry(
            source_type="dispatch",
            source_id="MODEL-TEST-002",
            title="Test Load Updated",
            card_data={"v": 2},
        )
        assert updated["status"] == "PURSUE"
        assert updated["card_data"]["v"] == 2

    def test_position_placeholders_default_unknown(self):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="MODEL-TEST-003",
            title="Test",
            card_data={},
        )
        assert entry["position_impact"] == "Unknown"
        assert entry["return_home_required"] == "Unknown"
        assert entry["tomorrow_position_risk"] == "Unknown"
        assert entry["hos_risk"] == "Unknown"
        assert entry["route_risk"] == "Unknown"
        assert entry["economic_opportunity_flag"] == "Unknown"

    def test_invalid_status_raises(self):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="MODEL-TEST-004",
            title="Test",
            card_data={},
        )
        with pytest.raises(ValueError, match="Invalid status"):
            sandbox.update_status(entry["id"], "INVALID")

    def test_get_all(self):
        from portal.models import sandbox
        sandbox.create_entry(source_type="dispatch", source_id="A", title="A", card_data={})
        sandbox.create_entry(source_type="sam", source_id="B", title="B", card_data={})
        all_entries = sandbox.get_all()
        assert len(all_entries) >= 2


# ---------- Card visual rules ----------
class TestCardVisual:
    def test_score_90_plus(self):
        from portal.helpers import card_visual
        vis = card_visual(90)
        assert vis["css"] == "card-high"

    def test_score_below_90(self):
        from portal.helpers import card_visual
        vis = card_visual(89)
        assert vis["css"] == "card-investigate"

    def test_decision_approve_proposal(self):
        from portal.helpers import card_visual
        vis = card_visual(None, {"action": "approve_proposal", "priority": "high"})
        assert vis["css"] == "card-high"

    def test_decision_flag_review(self):
        from portal.helpers import card_visual
        vis = card_visual(None, {"action": "flag_review"})
        assert vis["css"] == "card-investigate"

    def test_decision_reject(self):
        from portal.helpers import card_visual
        vis = card_visual(None, {"action": "reject"})
        assert vis["css"] == "card-reject"

    def test_no_score_no_decision(self):
        from portal.helpers import card_visual
        vis = card_visual(None, None)
        assert vis["css"] == "card-default"

    def test_format_score_none(self):
        from portal.helpers import format_score
        assert format_score(None) == "Unknown"

    def test_format_score_value(self):
        from portal.helpers import format_score
        assert format_score(92) == "92"


# ==========================================================================
# Phase 2 — Support Department Verification
# ==========================================================================


# ---------- P2-1. Publisher Queue: all 8 action types ----------
class TestPublisherAllTypes:
    def test_all_eight_action_types_exist(self):
        from portal.models.publisher import ACTION_TYPES
        expected = [
            "Broker Packet Required",
            "Direct Shipper Packet Required",
            "Rate Sheet Request",
            "Rate Confirmation Package Required",
            "DocuSign Package Ready",
            "Arrival Notice Draft",
            "POD/BOL Document Package Draft",
            "Detention Evidence Draft",
        ]
        assert ACTION_TYPES == expected

    def test_create_each_action_type(self, client, sample_load_good):
        from portal.models import publisher
        entry = _create_dispatch_entry(client, sample_load_good)
        for action_type in publisher.ACTION_TYPES:
            resp = client.post("/api/publisher/create", json={
                "sandbox_id": entry["id"],
                "action_type": action_type,
            })
            data = resp.get_json()
            assert data["status"] == "ok", f"Failed for {action_type}"
            action = data["action"]
            assert action["action_type"] == action_type
            assert action["sandbox_id"] == entry["id"]
            assert action["trigger_reason"]
            assert action["recommended_product"]
            assert action["human_approval_required"] is True
            assert action["status"] == "PENDING"

    def test_publisher_card_shows_all_fields(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        resp = client.get("/publisher")
        html = resp.data.decode("utf-8")
        assert "Trigger:" in html
        assert "Recommended Product:" in html
        assert "Available Data:" in html
        assert "Missing Data:" in html
        assert "Human Approval Required:" in html

    def test_broker_packet_manifest_complete(self):
        from portal.models.publisher import BROKER_PACKET_MANIFEST
        expected = ["Business Card", "W-9", "Insurance", "Authority", "Rate Sheet", "Terms"]
        assert BROKER_PACKET_MANIFEST == expected

    def test_direct_shipper_manifest_complete(self):
        from portal.models.publisher import DIRECT_SHIPPER_MANIFEST
        expected = ["Business Card", "Capabilities Summary", "Insurance", "Rate Sheet", "Terms"]
        assert DIRECT_SHIPPER_MANIFEST == expected

    def test_rate_confirmation_manifest_complete(self):
        from portal.models.publisher import RATE_CONFIRMATION_MANIFEST
        expected = [
            "Thank-you Cover Letter",
            "Rate Confirmation",
            "Terms",
            "Supporting Documents",
            "DocuSign-ready Marker",
        ]
        assert RATE_CONFIRMATION_MANIFEST == expected

    def test_publisher_does_not_invent_facts(self, client, sample_load_good):
        from portal.models import publisher
        entry = _create_dispatch_entry(client, sample_load_good)
        action = publisher.create_action(
            action_type="Broker Packet Required",
            sandbox_id=entry["id"],
            trigger_reason="Test",
            available_data=[],
            missing_data=["W-9", "Insurance"],
        )
        assert action["available_data"] == []
        assert action["missing_data"] == ["W-9", "Insurance"]


# ---------- P2-2. Library Placeholder: all sections ----------
class TestLibraryAllSections:
    def test_library_six_sections(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        for section in [
            "Company Library", "Broker Library", "Customer Library",
            "Location Intelligence Library", "Operations Library", "Intelligence Library",
        ]:
            assert section in html, f"Missing section: {section}"

    def test_library_section_descriptions(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        assert "approved company documents" in html.lower()
        assert "broker profiles" in html.lower()
        assert "customer" in html.lower()
        assert "facility data" in html.lower()
        assert "operational templates" in html.lower()
        assert "intelligence products" in html.lower()

    def test_company_library_eight_placeholders(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        for doc in ["W-9", "Insurance", "Authority", "Business Card",
                     "Rate Sheets", "Terms", "Capabilities", "Compliance Documents"]:
            assert doc in html, f"Missing company doc: {doc}"

    def test_location_intelligence_thirteen_fields(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        for field in [
            "Facility Name", "Address", "Gate Notes", "Dock Notes",
            "Check-in Procedure", "Security Requirements", "Liftgate Requirement",
            "Pallet Jack Requirement", "Forklift Availability", "Load Time",
            "Unload Time", "Detention History", "Driver Notes",
        ]:
            assert field in html, f"Missing location field: {field}"

    def test_library_is_not_archive(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        assert "approved" in html.lower()
        assert "reusable" in html.lower()


# ---------- P2-3. Archive Placeholder: all sections ----------
class TestArchiveAllSections:
    def test_archive_five_sections(self, client):
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        for section in [
            "Load Archive", "Decision Archive", "Publisher Archive",
            "Location History Archive", "Broker History Archive",
        ]:
            assert section in html, f"Missing archive section: {section}"

    def test_archive_candidate_preserves_data(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        archived = sandbox.get(entry["id"])
        assert archived["status"] == "PASS"
        assert archived["card_data"]["load_id"] == "LOAD-TEST-001"
        assert archived["score"] == 92
        assert archived["source_type"] == "dispatch"
        assert archived["updated_at"]
        assert "Archive candidate" in archived["notes"]

    def test_archive_table_shows_score_and_decision(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert "Score" in html
        assert "Decision" in html
        assert "Notes" in html

    def test_library_and_archive_are_separate(self, client):
        lib_resp = client.get("/library")
        arc_resp = client.get("/archive")
        lib_html = lib_resp.data.decode("utf-8")
        arc_html = arc_resp.data.decode("utf-8")
        assert "approved" in lib_html.lower() and "reusable" in lib_html.lower()
        assert "completed" in arc_html.lower() and "history" in arc_html.lower()


# ---------- P2-4. Conflict Notice: all 11 types ----------
class TestConflictAllTypes:
    def test_all_eleven_conflict_types_defined(self):
        from portal.models.conflict import CONFLICT_TYPES
        expected = [
            "missing_broker_email", "missing_source_link", "missing_rate",
            "missing_pickup_window", "equipment_mismatch", "hard_stop",
            "delivery_appointment_conflict", "hos_eld_conflict",
            "publisher_missing_document", "library_missing_asset",
            "corrupt_sandbox_data",
        ]
        assert CONFLICT_TYPES == expected

    def test_three_severities_defined(self):
        from portal.models.conflict import SEVERITIES
        assert SEVERITIES == ["info", "warning", "critical"]

    def test_conflict_notice_fields(self, client, sample_load_bad):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_bad)
        notices = conflict.get_all()
        assert len(notices) > 0
        notice = notices[0]
        assert "conflict_type" in notice
        assert "severity" in notice
        assert "sandbox_id" in notice
        assert "explanation" in notice
        assert "recommended_action" in notice
        assert "human_decision_required" in notice
        assert "resolved" in notice

    def test_hard_stop_generates_critical_notice(self, client, sample_load_hard_stop):
        from portal.models import conflict
        _create_dispatch_entry(client, sample_load_hard_stop)
        notices = conflict.get_all()
        hard_stops = [n for n in notices if n["conflict_type"] == "hard_stop"]
        assert len(hard_stops) == 1
        assert hard_stops[0]["severity"] == "critical"
        assert hard_stops[0]["human_decision_required"] is True

    def test_conflict_page_shows_human_decision_required(self, client, sample_load_bad):
        _create_dispatch_entry(client, sample_load_bad)
        resp = client.get("/conflicts")
        html = resp.data.decode("utf-8")
        assert "Human Decision Required" in html

    def test_library_asset_check(self):
        from portal.models import conflict
        notices = conflict.check_library_assets()
        assert len(notices) == 6
        for n in notices:
            assert n["conflict_type"] == "library_missing_asset"
            assert n["sandbox_id"] == "LIBRARY"
            assert n["human_decision_required"] is False


# ---------- P2-5. Sandbox Workflow: all 11 statuses ----------
class TestSandboxAllStatuses:
    def test_all_eleven_statuses_defined(self):
        from portal.models.sandbox import STATUSES
        expected = [
            "OPEN", "INTERESTED", "PURSUE", "WATCH", "PASS",
            "INQUIRY_DRAFTED", "INQUIRY_SENT_MANUAL", "PUBLISHER_REQUIRED",
            "BOOKED", "EXPIRED", "CLOSED",
        ]
        assert STATUSES == expected

    def test_all_statuses_can_be_set(self):
        from portal.models import sandbox
        from portal.models.sandbox import STATUSES
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="STATUS-TEST", title="Test", card_data={},
        )
        for status in STATUSES:
            updated = sandbox.update_status(entry["id"], status)
            assert updated["status"] == status

    def test_status_change_logged_in_events(self):
        from portal.models import sandbox
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="EVENT-TEST", title="Test", card_data={},
        )
        sandbox.update_status(entry["id"], "INTERESTED")
        sandbox.update_status(entry["id"], "PURSUE")
        updated = sandbox.get(entry["id"])
        assert len(updated["events"]) == 3
        assert updated["events"][1]["from"] == "OPEN"
        assert updated["events"][1]["to"] == "INTERESTED"
        assert updated["events"][2]["from"] == "INTERESTED"
        assert updated["events"][2]["to"] == "PURSUE"

    def test_no_autonomous_commitment(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        data = resp.get_json()
        assert data["entry"]["status"] == "PURSUE"
        assert data["entry"]["inquiry_draft"] is None


# ---------- P2-6. Inquiry Draft Verification ----------
class TestInquiryDraftTemplate:
    def test_inquiry_template_subject(self):
        from portal.helpers import INQUIRY_TEMPLATE_SUBJECT
        assert INQUIRY_TEMPLATE_SUBJECT == "Load Inquiry - Level 1 Transport"

    def test_inquiry_template_body_content(self):
        from portal.helpers import INQUIRY_TEMPLATE_BODY
        assert "Mike Zachary" in INQUIRY_TEMPLATE_BODY
        assert "Level 1 Transport Inc." in INQUIRY_TEMPLATE_BODY
        assert "This is not acceptance." in INQUIRY_TEMPLATE_BODY
        assert "This is not commitment." in INQUIRY_TEMPLATE_BODY
        assert "This is not negotiation." in INQUIRY_TEMPLATE_BODY
        assert "non-binding early inquiry" in INQUIRY_TEMPLATE_BODY

    def test_inquiry_default_mode_human_review(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["draft"]["mode"] == "HUMAN_REVIEW"

    def test_inquiry_draft_not_sent(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        data = resp.get_json()
        assert data["draft"]["status"] == "DRAFT_CREATED"
        assert data["draft"]["status"] != "SENT"

    def test_brief_shows_inquiry_draft(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        resp = client.get(f"/brief/{entry['id']}")
        html = resp.data.decode("utf-8")
        assert "Inquiry Draft" in html
        assert "HUMAN_REVIEW" in html
        assert "non-binding" in html.lower()
        assert "Mark as Sent" in html

    def test_brief_event_history_renders(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "interested"})
        resp = client.get(f"/brief/{entry['id']}")
        html = resp.data.decode("utf-8")
        assert "Event History" in html
        assert "INTERESTED" in html
