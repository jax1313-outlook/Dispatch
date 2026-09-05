"""Tests for the Archive Review Queue -- Stage 6 build, per
DISPATCH_STAGE6_ARCHIVE_BUILD_DESIGN_v1.md.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from portal.models import archive as arc_model


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect the JSON-file portal archive store to a per-test temp directory.

    The branch's version also redirected the SQLite dispatch.db, which only the
    decision-route tests needed -- those were not recovered (see the note at the
    end of this file), and the Review Queue model itself touches no database."""
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    yield


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


# The Stage 6 decision route (`POST /api/archive/review-decision`), its page
# rendering and their nine tests were NOT recovered with this model. They
# depend on `dispatch/security/` -- the role/session/audit stack superseded by
# main's Portal PIN gate (CF-03) and deliberately excluded from recovery. The
# route is scheduled as its own unit: rewrite it against main's identity layer,
# leaving ApprovalEvent's optional session_id and role null, rather than
# importing a second authentication stack to satisfy nine tests.

