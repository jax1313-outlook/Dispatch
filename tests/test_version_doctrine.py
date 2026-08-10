"""Tests for Version Doctrine (Ver: X / Last Change:) and card_level
retrofitted onto Sandbox and Conflict Notices -- Stage 5 of the
Migration Plan defined in Claude-3's DISPATCH_INTEGRATED_BLUEPRINT_v1.md.
"""

from __future__ import annotations

import pytest

from portal.models import conflict, sandbox


@pytest.fixture(autouse=True)
def portal_data_dir(tmp_path, monkeypatch):
    """Redirect portal data to tmp so tests are isolated -- same pattern
    as tests/test_portal.py."""
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    return tmp_path / "portal_data"


# ── Sandbox: version + last_change ─────────────────────────────────────

class TestSandboxVersioning:
    def test_new_entry_starts_at_version_one(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-001", title="Test", card_data={"rate": 1000},
        )
        assert entry["version"] == 1
        assert entry["last_change"] == "Created"

    def test_meaningful_change_bumps_version(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-002", title="Test", card_data={"rate": 1000},
        )
        updated = sandbox.create_entry(
            source_type="dispatch", source_id="V-002", title="Test", card_data={"rate": 1200},
        )
        assert updated["version"] == 2
        assert updated["last_change"] == "Rate Updated"

    def test_no_meaningful_change_does_not_bump_version(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-003", title="Test", card_data={"rate": 1000},
        )
        unchanged = sandbox.create_entry(
            source_type="dispatch", source_id="V-003", title="Test", card_data={"rate": 1000},
        )
        assert unchanged["version"] == 1
        assert unchanged["last_change"] == "Created"

    def test_score_increase_labeled_correctly(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-004", title="Test", card_data={}, score=70,
        )
        updated = sandbox.create_entry(
            source_type="dispatch", source_id="V-004", title="Test", card_data={}, score=95,
        )
        assert updated["version"] == 2
        assert updated["last_change"] == "Score Increased"

    def test_score_decrease_labeled_correctly(self):
        sandbox.create_entry(
            source_type="dispatch", source_id="V-005", title="Test", card_data={}, score=95,
        )
        updated = sandbox.create_entry(
            source_type="dispatch", source_id="V-005", title="Test", card_data={}, score=70,
        )
        assert updated["last_change"] == "Score Decreased"

    def test_update_status_bumps_version(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-006", title="Test", card_data={},
        )
        updated = sandbox.update_status(entry["id"], "PURSUE")
        assert updated["version"] == 2
        assert updated["last_change"] == "Status Changed to PURSUE"

    def test_update_status_same_status_does_not_bump(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-007", title="Test", card_data={},
        )
        same = sandbox.update_status(entry["id"], "OPEN")
        assert same["version"] == 1

    def test_update_scoring_route_data_changed_without_score_change(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-008", title="Test", card_data={}, score=80,
        )
        updated = sandbox.update_scoring(entry["id"], {"deadhead_miles": 42})
        assert updated["version"] == 2
        assert updated["last_change"] == "Route Data Updated"

    def test_set_inquiry_draft_bumps_version(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="V-009", title="Test", card_data={},
        )
        updated = sandbox.set_inquiry_draft(entry["id"], {"subject": "x", "body": "y"})
        assert updated["version"] == 2
        assert updated["last_change"] == "Inquiry Draft Created"

    def test_legacy_entry_gets_version_backfilled_on_read(self, tmp_path, monkeypatch):
        """An entry written before Stage 5 has no version/card_level keys
        at all -- get()/get_all() must backfill sane defaults rather than
        KeyError or render blank."""
        import json

        data_dir = tmp_path / "portal_data"
        monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
        data_dir.mkdir(parents=True, exist_ok=True)
        legacy = {
            "SBX-DISPATCH-LEGACY": {
                "id": "SBX-DISPATCH-LEGACY",
                "source_type": "dispatch",
                "source_id": "LEGACY",
                "status": "OPEN",
                "title": "Pre-Stage-5 entry",
                "score": None,
                "card_data": {},
                "events": [],
            }
        }
        (data_dir / "sandbox.json").write_text(json.dumps(legacy), encoding="utf-8")

        fetched = sandbox.get("SBX-DISPATCH-LEGACY")
        assert fetched["version"] == 1
        assert fetched["last_change"] == "Created"
        assert fetched["card_level"] in sandbox.CARD_LEVELS

        all_entries = sandbox.get_all()
        assert all_entries["SBX-DISPATCH-LEGACY"]["version"] == 1


# ── Sandbox: card_level derivation and override ────────────────────────

class TestSandboxCardLevel:
    def test_open_status_defaults_to_review_level(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-001", title="Test", card_data={},
        )
        assert entry["card_level"] == 2

    def test_high_score_bumps_open_status_to_decision_level(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-002", title="Test", card_data={}, score=97,
        )
        assert entry["card_level"] == 3

    def test_closed_status_is_silent_log_level(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-003", title="Test", card_data={},
        )
        updated = sandbox.update_status(entry["id"], "CLOSED")
        assert updated["card_level"] == 0

    def test_set_card_level_override_sticks(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-004", title="Test", card_data={},
        )
        overridden = sandbox.set_card_level(entry["id"], 5, note="Mike escalated manually")
        assert overridden["card_level"] == 5
        assert overridden["card_level_override"] is True

        # a subsequent status change must NOT clobber the override
        after_status_change = sandbox.update_status(entry["id"], "CLOSED")
        assert after_status_change["card_level"] == 5

    def test_clear_override_restores_auto_derivation(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-005", title="Test", card_data={},
        )
        sandbox.set_card_level(entry["id"], 5)
        restored = sandbox.clear_card_level_override(entry["id"])
        assert restored["card_level_override"] is False
        assert restored["card_level"] == 2  # back to OPEN's auto-derived level

    def test_set_card_level_rejects_invalid_level(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="CL-006", title="Test", card_data={},
        )
        with pytest.raises(ValueError):
            sandbox.set_card_level(entry["id"], 9)


# ── Conflict Notice: card_level derivation ─────────────────────────────

class TestConflictCardLevel:
    def test_critical_severity_is_conflict_level(self):
        notice = conflict.create_notice(
            "hard_stop", "critical", "SBX-TEST", "explanation", "action",
        )
        assert notice["card_level"] == 4

    def test_warning_with_decision_required_is_decision_level(self):
        notice = conflict.create_notice(
            "missing_rate", "warning", "SBX-TEST", "explanation", "action",
            human_decision_required=True,
        )
        assert notice["card_level"] == 3

    def test_info_without_decision_required_is_silent_level(self):
        notice = conflict.create_notice(
            "library_missing_asset", "info", "LIBRARY", "explanation", "action",
            human_decision_required=False,
        )
        assert notice["card_level"] == 0

    def test_legacy_notice_gets_card_level_backfilled_on_read(self, tmp_path, monkeypatch):
        import json

        data_dir = tmp_path / "portal_data"
        monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
        data_dir.mkdir(parents=True, exist_ok=True)
        legacy = [{
            "id": "CN-0001",
            "conflict_type": "missing_rate",
            "severity": "critical",
            "sandbox_id": "SBX-TEST",
            "explanation": "e",
            "recommended_action": "a",
            "human_decision_required": True,
            "resolved": False,
            "created_at": "2026-01-01T00:00:00Z",
        }]
        (data_dir / "conflicts.json").write_text(json.dumps(legacy), encoding="utf-8")

        fetched = conflict.get_unresolved()
        assert fetched[0]["card_level"] == 4


# ── Portal route: cards render Ver: / Last Change: / card-level badge ──

class TestPortalCardRendering:
    @pytest.fixture
    def app(self):
        from portal.app import create_app

        app = create_app({"TESTING": True, "SECRET_KEY": "test"})
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_home_page_renders_version_and_card_level(self, client):
        sandbox.create_entry(
            source_type="dispatch", source_id="RENDER-001", title="Render Test",
            card_data={"origin": "Jacksonville, FL", "destination": "Atlanta, GA"},
            score=95,
        )
        resp = client.get("/home")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Ver: 1" in html
        assert "Last Change: Created" in html
        assert "card-level-3" in html  # score 95 + OPEN -> Decision level
