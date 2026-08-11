"""Tests for the Archive Review Queue -- Stage 6 build, per
DISPATCH_STAGE6_ARCHIVE_BUILD_DESIGN_v1.md.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from dispatch import db
from dispatch.spine.store import list_approval_events
from portal.models import archive as arc_model


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect both the SQLite dispatch.db (Spine ApprovalEvent/Security)
    and the JSON-file portal archive store to a per-test temp directory."""
    db.set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    yield
    db.set_db_path(None)


def _make_archive_record(days_old: int, section: str = "load") -> dict:
    record = arc_model.create_record(
        section=section, source_id=f"SRC-{days_old}", title="Test Archive Record",
        record_data={"status": "closed"},
    )
    backdated = (datetime.now(timezone.utc) - timedelta(days=days_old)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    data = arc_model._load()
    for r in data[section]:
        if r["id"] == record["id"]:
            r["archived_at"] = backdated
    arc_model._save(data)
    return {**record, "archived_at": backdated}


# ── list_review_queue ────────────────────────────────────────────────────

def test_new_record_defaults_to_pending_review_status():
    record = arc_model.create_record(
        section="load", source_id="SRC-1", title="Test", record_data={},
    )
    assert record["review_status"] == "pending"
    assert record["reviewed_at"] is None


def test_record_older_than_threshold_appears_in_queue():
    _make_archive_record(days_old=200)
    queue = arc_model.list_review_queue(age_days=180)
    assert len(queue) == 1
    assert queue[0]["age_days"] >= 180


def test_record_younger_than_threshold_not_in_queue():
    _make_archive_record(days_old=30)
    queue = arc_model.list_review_queue(age_days=180)
    assert queue == []


def test_already_reviewed_record_not_in_queue():
    record = _make_archive_record(days_old=200)
    arc_model.mark_reviewed(record["id"], "load", "kept")
    queue = arc_model.list_review_queue(age_days=180)
    assert queue == []


def test_queue_sorted_oldest_first():
    _make_archive_record(days_old=200, section="load")
    _make_archive_record(days_old=400, section="decision")
    queue = arc_model.list_review_queue(age_days=180)
    assert len(queue) == 2
    assert queue[0]["age_days"] > queue[1]["age_days"]


# ── mark_reviewed ────────────────────────────────────────────────────────

def test_mark_reviewed_kept():
    record = _make_archive_record(days_old=200)
    updated = arc_model.mark_reviewed(record["id"], "load", "kept", reason="Still relevant")
    assert updated["review_status"] == "kept"
    assert updated["disposition_reason"] == "Still relevant"
    assert updated["reviewed_at"] is not None


def test_mark_reviewed_deleted_does_not_remove_record():
    record = _make_archive_record(days_old=200)
    arc_model.mark_reviewed(record["id"], "load", "deleted")
    all_records = arc_model.get_section("load")
    assert len(all_records) == 1
    assert all_records[0]["id"] == record["id"]
    assert all_records[0]["review_status"] == "deleted"


def test_mark_reviewed_invalid_disposition_raises():
    record = _make_archive_record(days_old=200)
    with pytest.raises(ValueError):
        arc_model.mark_reviewed(record["id"], "load", "maybe")


def test_mark_reviewed_not_found_raises_keyerror():
    with pytest.raises(KeyError):
        arc_model.mark_reviewed("ARC-LOA-9999", "load", "kept")


def test_mark_reviewed_twice_refuses_second_decision():
    record = _make_archive_record(days_old=200)
    arc_model.mark_reviewed(record["id"], "load", "kept")
    with pytest.raises(ValueError):
        arc_model.mark_reviewed(record["id"], "load", "deleted")


def test_no_physical_deletion_anywhere_in_module():
    """Structural guard: portal/models/archive.py must never unlink or
    remove any file as part of a review decision."""
    source = inspect.getsource(arc_model)
    assert "unlink(" not in source
    assert "rmtree(" not in source
    assert "os.remove(" not in source


# ── Portal API: authorization boundary ─────────────────────────────────

@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    return app.test_client()


def test_review_decision_unauthenticated_rejected(client):
    record = _make_archive_record(days_old=200)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "kept"},
    )
    assert resp.status_code in (302, 403)
    # Underlying record must be untouched.
    stored = arc_model.get_section("load")[0]
    assert stored["review_status"] == "pending"


def test_review_decision_non_authority_role_rejected(client):
    from dispatch.security import auth

    auth.create_user_with_pin("Driver Dana", "Driver", "9911")
    resp = client.post("/login", data={"display_name": "Driver Dana", "pin": "9911"})
    assert resp.status_code == 302

    record = _make_archive_record(days_old=200)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "kept"},
    )
    assert resp.status_code == 403
    stored = arc_model.get_section("load")[0]
    assert stored["review_status"] == "pending"


def test_review_decision_authority_role_succeeds(client, login_as_authority):
    login_as_authority(client)
    record = _make_archive_record(days_old=200)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "kept", "reason": "test"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["record"]["review_status"] == "kept"


# ── ApprovalEvent + AuditEvent correctness ──────────────────────────────

def test_review_decision_writes_approval_event_with_real_identity(client, login_as_authority):
    login_as_authority(client)
    record = _make_archive_record(days_old=200)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "deleted", "reason": "stale"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    approval_event_id = body["approval_event_id"]

    events = list_approval_events(body["work_item_id"])
    matches = [e for e in events if e["approval_event_id"] == approval_event_id]
    assert len(matches) == 1
    approval = matches[0]
    assert approval["action"] == "APPROVE_ARCHIVE_DELETE"
    assert approval["object_type"] == "archive_record"
    assert approval["object_id"] == record["id"]
    assert approval["session_id"] is not None
    assert approval["user_id"] is not None
    assert approval["role"] == "Authority"
    assert approval["audit_id"]


def test_review_decision_keep_writes_correct_approval_action(client, login_as_authority):
    login_as_authority(client)
    record = _make_archive_record(days_old=200)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "kept"},
    )
    body = resp.get_json()
    events = list_approval_events(body["work_item_id"])
    matches = [e for e in events if e["approval_event_id"] == body["approval_event_id"]]
    assert matches[0]["action"] == "APPROVE_ARCHIVE_KEEP"


def test_review_decision_missing_fields_returns_400(client, login_as_authority):
    login_as_authority(client)
    resp = client.post("/api/archive/review-decision", json={"record_id": "X"})
    assert resp.status_code == 400


def test_review_decision_unknown_record_returns_404(client, login_as_authority):
    login_as_authority(client)
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": "ARC-LOA-9999", "section": "load", "disposition": "kept"},
    )
    assert resp.status_code == 404


def test_review_decision_repeat_call_returns_409(client, login_as_authority):
    login_as_authority(client)
    record = _make_archive_record(days_old=200)
    client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "kept"},
    )
    resp = client.post(
        "/api/archive/review-decision",
        json={"record_id": record["id"], "section": "load", "disposition": "deleted"},
    )
    assert resp.status_code == 409


# ── Portal rendering ─────────────────────────────────────────────────────

def test_archive_page_renders_review_queue(client):
    _make_archive_record(days_old=200)
    resp = client.get("/archive")
    assert resp.status_code == 200
    assert b"Archive Review Queue" in resp.data


def test_archive_page_renders_without_review_queue_when_empty(client):
    resp = client.get("/archive")
    assert resp.status_code == 200
    assert b"Archive Review Queue" not in resp.data
