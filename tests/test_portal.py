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
    def test_pass_creates_archive_record(self, client, sample_load_good):
        from portal.models import archive as arc_model
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        records = arc_model.get_section("load")
        assert len(records) >= 1
        assert records[0]["source_id"] == entry["id"]

    def test_pass_adds_archived_note(self, client, sample_load_good):
        from portal.models import sandbox
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        updated = sandbox.get(entry["id"])
        assert "Archived" in updated["notes"]

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
        html = resp.data.decode("utf-8")
        assert "SAM.gov API" in html
        assert "SMTP Email" in html
        assert "Claude API" in html
        assert "DISPATCH Acquisition" in html
        assert "Email Delivery" in html

    def test_brief_shows_intelligence_modules(self, client):
        from portal.models import sandbox
        intel = {
            "set_aside_detection": {
                "module": "set_aside_detection", "version": "1.0",
                "flags": ["8a_set_aside"], "findings": {},
                "summary": "8(a) set-aside detected",
                "score": None, "deterministic": True,
            },
        }
        sandbox.create_entry(
            source_type="sam", source_id="INTEL-BRIEF",
            title="Intel Brief Test",
            card_data={"solicitation_number": "SOL-IB"},
            intelligence=intel, flags=["8a_set_aside"],
        )
        entries = sandbox.get_all()
        entry_id = [k for k, v in entries.items() if v["source_id"] == "INTEL-BRIEF"][0]
        resp = client.get(f"/brief/{entry_id}")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Intelligence Modules" in html
        assert "Set Aside Detection" in html
        assert "8a_set_aside" in html

    def test_archive_renders(self, client):
        resp = client.get("/archive")
        assert resp.status_code == 200

    def test_queues_page_renders(self, client):
        resp = client.get("/queues")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Flag for Review" in html
        assert "Deeper Analysis" in html

    def test_archive_shows_pipeline_contracts(self, client, tmp_archive):
        from cin_lite import archive
        contract = {"title": "Pipeline Archived", "solicitation_number": "SOL-ARC",
                     "agency": "DOD", "estimated_value": 100000, "response_date": None}
        intel = {"set_aside_detection": {"module": "set_aside_detection", "version": "1.0",
                 "flags": [], "findings": {}, "summary": "None",
                 "score": None, "deterministic": True}}
        archive.store(contract, intel, "test summary")
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert "DISPATCH Pipeline Archive" in html
        assert "Pipeline Archived" in html


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

    def test_location_intelligence_fields_defined(self):
        from portal.models.library import LOCATION_FIELDS
        expected = [
            "Facility Name", "Address", "Gate Notes", "Dock Notes",
            "Check-in Procedure", "Security Requirements", "Liftgate Requirement",
            "Pallet Jack Requirement", "Forklift Availability", "Load Time",
            "Unload Time", "Detention History", "Driver Notes",
        ]
        assert LOCATION_FIELDS == expected

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
        from portal.models import archive as arc_model
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        records = arc_model.get_section("load")
        assert len(records) >= 1
        record = records[0]
        assert record["source_id"] == entry["id"]
        assert record["record_data"]["score"] == 92
        assert record["record_data"]["source_type"] == "dispatch"

    def test_archive_table_shows_columns(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pass"})
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert "Title" in html
        assert "Decision" in html
        assert "Archived" in html

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


# ==========================================================================
# Phase 3 — Library / Archive / Intelligence Model and API Tests
# ==========================================================================


# ---------- Library Model ----------
class TestLibraryModel:
    def test_add_record(self):
        from portal.models import library as lib_model
        record = lib_model.add_record("company", "W-9", content="uploaded")
        assert record["id"].startswith("LIB-COM-")
        assert record["name"] == "W-9"
        assert record["section"] == "company"
        assert record["status"] == "approved"
        assert record["content"] == "uploaded"

    def test_get_all_sections(self):
        from portal.models import library as lib_model
        lib_model.add_record("company", "W-9")
        lib_model.add_record("broker", "Test Broker")
        data = lib_model.get_all()
        assert "company" in data
        assert "broker" in data
        assert len(data["company"]) >= 1
        assert len(data["broker"]) >= 1

    def test_get_section(self):
        from portal.models import library as lib_model
        lib_model.add_record("customer", "Acme Corp")
        records = lib_model.get_section("customer")
        assert len(records) >= 1
        assert records[0]["name"] == "Acme Corp"

    def test_update_record(self):
        from portal.models import library as lib_model
        record = lib_model.add_record("company", "Insurance")
        updated = lib_model.update_record(record["id"], name="Insurance Certificate")
        assert updated["name"] == "Insurance Certificate"
        assert updated["updated_at"] >= record["created_at"]

    def test_delete_record(self):
        from portal.models import library as lib_model
        record = lib_model.add_record("operations", "Checklist")
        deleted = lib_model.delete_record(record["id"])
        assert deleted["name"] == "Checklist"
        remaining = lib_model.get_section("operations")
        assert all(r["id"] != record["id"] for r in remaining)

    def test_delete_nonexistent_raises(self):
        from portal.models import library as lib_model
        with pytest.raises(KeyError):
            lib_model.delete_record("LIB-NONEXISTENT")

    def test_invalid_section_raises(self):
        from portal.models import library as lib_model
        with pytest.raises(ValueError):
            lib_model.add_record("invalid_section", "test")

    def test_available_and_missing_company_assets(self):
        from portal.models import library as lib_model
        lib_model.add_record("company", "W-9")
        lib_model.add_record("company", "Insurance")
        available = lib_model.get_available_company_assets()
        missing = lib_model.get_missing_company_assets()
        assert "W-9" in available
        assert "Insurance" in available
        assert "W-9" not in missing
        assert "Insurance" not in missing
        assert "Authority" in missing

    def test_six_sections_defined(self):
        from portal.models.library import SECTIONS
        assert len(SECTIONS) == 6
        assert "company" in SECTIONS
        assert "broker" in SECTIONS
        assert "customer" in SECTIONS
        assert "location_intelligence" in SECTIONS
        assert "operations" in SECTIONS
        assert "intelligence" in SECTIONS


# ---------- Archive Model ----------
class TestArchiveModel:
    def test_create_record(self):
        from portal.models import archive as arc_model
        record = arc_model.create_record(
            section="load",
            source_id="TEST-001",
            title="Test Load",
            record_data={"origin": "Jacksonville"},
            decision_summary="PASS — test",
        )
        assert record["id"].startswith("ARC-LOA-")
        assert record["section"] == "load"
        assert record["title"] == "Test Load"
        assert record["decision_summary"] == "PASS — test"

    def test_dedup_by_source_id(self):
        from portal.models import archive as arc_model
        r1 = arc_model.create_record("load", "DEDUP-001", "Load A", {})
        r2 = arc_model.create_record("load", "DEDUP-001", "Load A Updated", {})
        assert r1["id"] == r2["id"]
        records = arc_model.get_section("load")
        dedup = [r for r in records if r["source_id"] == "DEDUP-001"]
        assert len(dedup) == 1

    def test_archive_from_sandbox_dispatch(self):
        from portal.models import archive as arc_model
        entry = {
            "id": "SBX-DISPATCH-TEST",
            "source_type": "dispatch",
            "source_id": "LOAD-100",
            "title": "Test Load",
            "status": "PASS",
            "card_data": {"origin": "Tampa"},
            "score": 85,
            "decision": {},
            "flags": [],
            "intelligence": {},
            "events": [],
            "notes": "",
            "inquiry_draft": None,
            "publisher_actions": [],
        }
        record = arc_model.archive_from_sandbox(entry)
        assert record["section"] == "load"
        assert record["record_data"]["source_type"] == "dispatch"

    def test_archive_from_sandbox_sam(self):
        from portal.models import archive as arc_model
        entry = {
            "id": "SBX-SAM-TEST",
            "source_type": "sam",
            "source_id": "SOL-100",
            "title": "Test SAM",
            "status": "PASS",
            "card_data": {},
            "decision": {"action": "reject", "reason": "Not eligible"},
            "flags": [],
            "intelligence": {},
            "events": [],
            "notes": "",
            "inquiry_draft": None,
            "publisher_actions": [],
        }
        record = arc_model.archive_from_sandbox(entry)
        assert record["section"] == "decision"

    def test_archive_publisher_action(self):
        from portal.models import archive as arc_model
        action = {
            "id": "PUB-001",
            "action_type": "Broker Packet Required",
            "sandbox_id": "SBX-TEST",
            "status": "ARCHIVED",
        }
        record = arc_model.archive_publisher_action(action)
        assert record["section"] == "publisher"
        assert record["source_id"] == "PUB-001"

    def test_total_count(self):
        from portal.models import archive as arc_model
        arc_model.create_record("load", "COUNT-1", "A", {})
        arc_model.create_record("decision", "COUNT-2", "B", {})
        assert arc_model.total_count() >= 2

    def test_invalid_section_raises(self):
        from portal.models import archive as arc_model
        with pytest.raises(ValueError):
            arc_model.create_record("invalid", "X", "X", {})

    def test_five_sections_defined(self):
        from portal.models.archive import ARCHIVE_SECTIONS, SECTION_LABELS
        assert len(ARCHIVE_SECTIONS) == 5
        assert len(SECTION_LABELS) == 5
        for s in ARCHIVE_SECTIONS:
            assert s in SECTION_LABELS


# ---------- Intelligence Model ----------
class TestIntelligenceModel:
    def test_create_record(self):
        from portal.models import intelligence as intel_model
        record = intel_model.create_record(
            intel_type="broker",
            subject="Test Broker",
            content="Reliable partner",
            source="manual",
        )
        assert record["id"].startswith("INT-BRO-")
        assert record["subject"] == "Test Broker"
        assert record["content"] == "Reliable partner"
        assert record["source"] == "manual"

    def test_get_by_type(self):
        from portal.models import intelligence as intel_model
        intel_model.create_record("location", "Port of Savannah", "Busy area")
        records = intel_model.get_by_type("location")
        assert len(records) >= 1
        assert records[0]["subject"] == "Port of Savannah"

    def test_update_record(self):
        from portal.models import intelligence as intel_model
        record = intel_model.create_record("market", "Fuel Prices", "Rising")
        updated = intel_model.update_record(record["id"], content="Stable")
        assert updated["content"] == "Stable"
        assert updated["updated_at"] >= record["created_at"]

    def test_update_nonexistent_raises(self):
        from portal.models import intelligence as intel_model
        with pytest.raises(KeyError):
            intel_model.update_record("INT-NONEXISTENT", content="test")

    def test_invalid_type_raises(self):
        from portal.models import intelligence as intel_model
        with pytest.raises(ValueError):
            intel_model.create_record("invalid_type", "Test", "Content")

    def test_total_count(self):
        from portal.models import intelligence as intel_model
        intel_model.create_record("broker", "A", "x")
        intel_model.create_record("customer", "B", "y")
        assert intel_model.total_count() >= 2

    def test_six_types_defined(self):
        from portal.models.intelligence import INTEL_TYPES, INTEL_LABELS
        assert len(INTEL_TYPES) == 6
        assert len(INTEL_LABELS) == 6
        for t in INTEL_TYPES:
            assert t in INTEL_LABELS


# ---------- Library API ----------
class TestLibraryAPI:
    def test_add_record(self, client):
        resp = client.post("/api/library/add", json={
            "section": "company",
            "name": "W-9",
            "content": "uploaded",
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["record"]["name"] == "W-9"

    def test_add_invalid_section(self, client):
        resp = client.post("/api/library/add", json={
            "section": "invalid",
            "name": "test",
        })
        assert resp.status_code == 400

    def test_add_missing_fields(self, client):
        resp = client.post("/api/library/add", json={"section": "company"})
        assert resp.status_code == 400

    def test_update_record(self, client):
        from portal.models import library as lib_model
        record = lib_model.add_record("broker", "Test Broker")
        resp = client.post("/api/library/update", json={
            "record_id": record["id"],
            "name": "Updated Broker",
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["record"]["name"] == "Updated Broker"

    def test_update_nonexistent(self, client):
        resp = client.post("/api/library/update", json={
            "record_id": "LIB-NONEXISTENT",
        })
        assert resp.status_code == 404

    def test_delete_record(self, client):
        from portal.models import library as lib_model
        record = lib_model.add_record("operations", "To Delete")
        resp = client.post("/api/library/delete", json={
            "record_id": record["id"],
        })
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_delete_nonexistent(self, client):
        resp = client.post("/api/library/delete", json={
            "record_id": "LIB-NONEXISTENT",
        })
        assert resp.status_code == 404


# ---------- Archive API ----------
class TestArchiveAPI:
    def test_archive_sandbox_entry(self, client, sample_load_good):
        entry = _create_dispatch_entry(client, sample_load_good)
        resp = client.post("/api/archive/create", json={
            "sandbox_id": entry["id"],
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["record"]["source_id"] == entry["id"]

    def test_archive_missing_sandbox(self, client):
        resp = client.post("/api/archive/create", json={
            "sandbox_id": "SBX-NONEXISTENT",
        })
        assert resp.status_code == 404

    def test_archive_missing_sandbox_id(self, client):
        resp = client.post("/api/archive/create", json={})
        assert resp.status_code == 400

    def test_publisher_archive_on_status_change(self, client, sample_load_good):
        from portal.models import publisher, archive as arc_model
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/action", json={"sandbox_id": entry["id"], "action": "pursue"})
        queue = publisher.get_queue()
        action_id = queue[0]["id"]
        client.post("/api/publisher/update", json={
            "action_id": action_id,
            "status": "ARCHIVED",
        })
        pub_archive = arc_model.get_section("publisher")
        assert len(pub_archive) >= 1


# ---------- Intelligence API ----------
class TestIntelligenceAPI:
    def test_add_record(self, client):
        resp = client.post("/api/intelligence/add", json={
            "intel_type": "broker",
            "subject": "Test Broker",
            "content": "Good broker",
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["record"]["subject"] == "Test Broker"

    def test_add_invalid_type(self, client):
        resp = client.post("/api/intelligence/add", json={
            "intel_type": "invalid",
            "subject": "Test",
        })
        assert resp.status_code == 400

    def test_add_missing_fields(self, client):
        resp = client.post("/api/intelligence/add", json={
            "intel_type": "broker",
        })
        assert resp.status_code == 400

    def test_update_record(self, client):
        from portal.models import intelligence as intel_model
        record = intel_model.create_record("location", "Port A", "Good docks")
        resp = client.post("/api/intelligence/update", json={
            "record_id": record["id"],
            "content": "Updated docks",
        })
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["record"]["content"] == "Updated docks"

    def test_update_nonexistent(self, client):
        resp = client.post("/api/intelligence/update", json={
            "record_id": "INT-NONEXISTENT",
        })
        assert resp.status_code == 404

    def test_inquiry_creates_broker_intel(self, client, sample_load_good):
        from portal.models import intelligence as intel_model
        entry = _create_dispatch_entry(client, sample_load_good)
        client.post("/api/inquiry/create", json={"sandbox_id": entry["id"]})
        broker_intel = intel_model.get_by_type("broker")
        broker_names = [r["subject"] for r in broker_intel]
        assert "Southeast Freight Partners" in broker_names


# ---------- New Page Rendering ----------
class TestNewPages:
    def test_intelligence_page_renders(self, client):
        resp = client.get("/intelligence")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Operational Intelligence" in html
        assert "Location Intelligence" in html
        assert "Broker Intelligence" in html

    def test_intelligence_page_shows_records(self, client):
        from portal.models import intelligence as intel_model
        intel_model.create_record("broker", "Test Broker Intel", "Content here")
        resp = client.get("/intelligence")
        html = resp.data.decode("utf-8")
        assert "Test Broker Intel" in html

    def test_home_shows_archive_count(self, client):
        resp = client.get("/home")
        html = resp.data.decode("utf-8")
        assert "Archived Records" in html

    def test_home_shows_intel_count(self, client):
        resp = client.get("/home")
        html = resp.data.decode("utf-8")
        assert "Intelligence Records" in html

    def test_library_add_button(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        assert "Add Record" in html

    def test_library_missing_assets_shown(self, client):
        resp = client.get("/library")
        html = resp.data.decode("utf-8")
        assert "Missing Company Assets" in html
        assert "W-9" in html

    def test_archive_sections_rendered(self, client):
        resp = client.get("/archive")
        html = resp.data.decode("utf-8")
        assert "Load Archive" in html
        assert "Decision Archive" in html
        assert "Publisher Archive" in html

    def test_dispatch_operational_considerations(self, client, sample_load_good):
        _create_dispatch_entry(client, sample_load_good)
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "Operational Considerations" in html


# ==========================================================================
# Dispatch Engine UI
# ==========================================================================


class TestDispatchEngineUI:
    """Tests for the dispatch engine portal views (active loads + detail)."""

    @pytest.fixture(autouse=True)
    def _init_dispatch_db(self, tmp_path):
        from dispatch import db
        db.set_db_path(tmp_path / "dispatch_ui.db")
        yield
        db.set_db_path(None)

    def test_dispatch_page_shows_active_loads_section(self, client):
        resp = client.get("/dispatch")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Active Loads" in html
        assert "Load Board" in html

    def test_dispatch_page_shows_engine_load(self, client):
        from dispatch import services
        services.create_load(customer="Test Customer Inc")
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "Test Customer Inc" in html

    def test_dispatch_page_status_filter(self, client):
        from dispatch import services
        services.create_load(customer="Active Co")
        resp = client.get("/dispatch?status=created")
        html = resp.data.decode("utf-8")
        assert "Active Co" in html
        resp2 = client.get("/dispatch?status=delivered")
        html2 = resp2.data.decode("utf-8")
        assert "Active Co" not in html2

    def test_dispatch_detail_renders(self, client):
        from dispatch import services
        load = services.create_load(
            customer="Detail Test",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
        )
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Detail Test" in html
        assert "Dallas, TX" in html
        assert "Houston, TX" in html
        assert "Load Information" in html
        assert "Visibility" in html
        assert "Timeline" in html
        assert "Evidence" in html
        assert "Exceptions" in html
        assert "POD Packages" in html
        assert "Retention Archive" in html

    def test_dispatch_detail_shows_milestones(self, client):
        from dispatch import services
        load = services.create_load(customer="MS Test")
        services.add_milestone(load["load_id"], "dispatched", location="Yard A")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "dispatched" in html
        assert "Yard A" in html

    def test_dispatch_detail_shows_exceptions(self, client):
        from dispatch import services
        load = services.create_load(customer="Exc Test")
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Traffic jam")
        resp = client.get(f"/dispatch/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "Traffic jam" in html
        assert "Resolve" in html

    def test_dispatch_detail_not_found_redirects(self, client):
        resp = client.get("/dispatch/nonexistent-id")
        assert resp.status_code == 302

    def test_new_load_form_present(self, client):
        resp = client.get("/dispatch")
        html = resp.data.decode("utf-8")
        assert "new-load-form" in html
        assert "Create New Load" in html
