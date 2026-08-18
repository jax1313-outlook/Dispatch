"""Tests for the System Keys integrations registry (D4: "a generic System Keys Card
integrations registry inside the Driver Portal, covering Accounting, ELD, Scanner, Printer,
DAT, TruckSmart, and Other -- each holding an API Key, Credentials, Token, and
Configuration.").

Covers: portal.models.integrations_registry (CRUD, upsert idempotency, clear), the
/api/integrations routes, and that the Settings page renders the new System Keys section.
"""

from __future__ import annotations

import pytest

from dispatch.db import set_db_path
from portal.models import integrations_registry as reg


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    set_db_path(tmp_path / "test.db")

    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

    set_db_path(None)


# ── portal.models.integrations_registry ─────────────────────────────────


class TestIntegrationTypes:
    def test_seven_types_specified_by_d4(self):
        assert reg.INTEGRATION_TYPES == [
            "Accounting", "ELD", "Scanner", "Printer", "DAT", "TruckSmart", "Other",
        ]


class TestListEntries:
    def test_returns_all_seven_types_before_any_upsert(self, client):
        entries = reg.list_entries()
        assert len(entries) == 7
        assert [e["integration_type"] for e in entries] == reg.INTEGRATION_TYPES

    def test_unconfigured_entries_have_null_fields_and_timestamps(self, client):
        entries = reg.list_entries()
        for e in entries:
            assert e["api_key"] is None
            assert e["credentials"] is None
            assert e["token"] is None
            assert e["configuration"] is None
            assert e["created_at"] is None
            assert e["updated_at"] is None


class TestGetEntry:
    def test_get_entry_unconfigured_type_returns_template(self, client):
        entry = reg.get_entry("DAT")
        assert entry["integration_type"] == "DAT"
        assert entry["api_key"] is None

    def test_get_entry_rejects_unknown_type(self, client):
        with pytest.raises(ValueError, match="Invalid integration_type"):
            reg.get_entry("Nonsense")

    def test_get_entry_after_upsert_reflects_stored_value(self, client):
        reg.upsert_entry("DAT", api_key="dat-key-123")
        entry = reg.get_entry("DAT")
        assert entry["api_key"] == "dat-key-123"


class TestUpsertEntry:
    def test_rejects_unknown_type(self, client):
        with pytest.raises(ValueError, match="Invalid integration_type"):
            reg.upsert_entry("Nonsense", api_key="x")

    def test_creates_entry_with_created_and_updated_at(self, client):
        entry = reg.upsert_entry("Accounting", api_key="acct-key")
        assert entry["integration_type"] == "Accounting"
        assert entry["api_key"] == "acct-key"
        assert entry["created_at"] is not None
        assert entry["updated_at"] == entry["created_at"]

    def test_upsert_is_idempotent_by_integration_type(self, client):
        first = reg.upsert_entry("ELD", api_key="v1")
        second = reg.upsert_entry("ELD", api_key="v2")
        entries = [e for e in reg.list_entries() if e["integration_type"] == "ELD"]
        assert len(entries) == 1
        assert second["api_key"] == "v2"
        assert first["created_at"] == second["created_at"]

    def test_upsert_only_changes_fields_explicitly_passed(self, client):
        reg.upsert_entry(
            "Printer", api_key="key1", credentials="cred1", token="tok1",
            configuration="conf1",
        )
        updated = reg.upsert_entry("Printer", token="tok2")
        assert updated["api_key"] == "key1"
        assert updated["credentials"] == "cred1"
        assert updated["token"] == "tok2"
        assert updated["configuration"] == "conf1"

    def test_upsert_accepts_dict_for_credentials_and_configuration(self, client):
        entry = reg.upsert_entry(
            "TruckSmart",
            credentials={"user": "bob"},
            configuration={"region": "us-east"},
        )
        assert entry["credentials"] == {"user": "bob"}
        assert entry["configuration"] == {"region": "us-east"}

    def test_all_seven_types_can_be_upserted_independently(self, client):
        for t in reg.INTEGRATION_TYPES:
            reg.upsert_entry(t, api_key=f"{t}-key")
        entries = {e["integration_type"]: e for e in reg.list_entries()}
        for t in reg.INTEGRATION_TYPES:
            assert entries[t]["api_key"] == f"{t}-key"


class TestClearEntry:
    def test_clear_unconfigured_type_is_a_safe_no_op(self, client):
        entry = reg.clear_entry("Scanner")
        assert entry["integration_type"] == "Scanner"
        assert entry["api_key"] is None

    def test_clear_wipes_fields_but_keeps_the_row_and_created_at(self, client):
        created = reg.upsert_entry(
            "Scanner", api_key="k", credentials="c", token="t", configuration="cfg",
        )
        cleared = reg.clear_entry("Scanner")
        assert cleared["api_key"] is None
        assert cleared["credentials"] is None
        assert cleared["token"] is None
        assert cleared["configuration"] is None
        assert cleared["created_at"] == created["created_at"]
        # updated_at has 1-second resolution (see _utc_now()); assert it's stamped fresh
        # (present, well-formed) rather than asserting it differs from created_at, which
        # would be flaky when both calls land in the same second.
        assert cleared["updated_at"] is not None

    def test_clear_rejects_unknown_type(self, client):
        with pytest.raises(ValueError, match="Invalid integration_type"):
            reg.clear_entry("Nonsense")


# ── /api/integrations routes ─────────────────────────────────────────


class TestIntegrationsListRoute:
    def test_list_returns_all_seven(self, client):
        resp = client.get("/api/integrations")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert len(data["entries"]) == 7


class TestIntegrationsGetRoute:
    def test_get_known_type(self, client):
        resp = client.get("/api/integrations/DAT")
        assert resp.status_code == 200
        assert resp.get_json()["entry"]["integration_type"] == "DAT"

    def test_get_unknown_type_400s(self, client):
        resp = client.get("/api/integrations/Nonsense")
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestIntegrationsUpsertRoute:
    def test_patch_creates_and_updates(self, client):
        resp = client.patch("/api/integrations/DAT", json={"api_key": "abc123"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["entry"]["api_key"] == "abc123"

        resp2 = client.get("/api/integrations/DAT")
        assert resp2.get_json()["entry"]["api_key"] == "abc123"

    def test_post_also_accepted(self, client):
        resp = client.post("/api/integrations/TruckSmart", json={"token": "tok"})
        assert resp.status_code == 200
        assert resp.get_json()["entry"]["token"] == "tok"

    def test_upsert_unknown_type_400s(self, client):
        resp = client.patch("/api/integrations/Nonsense", json={"api_key": "x"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_upsert_is_idempotent_via_route(self, client):
        client.patch("/api/integrations/Other", json={"api_key": "v1"})
        client.patch("/api/integrations/Other", json={"api_key": "v2"})
        entries = client.get("/api/integrations").get_json()["entries"]
        matches = [e for e in entries if e["integration_type"] == "Other"]
        assert len(matches) == 1
        assert matches[0]["api_key"] == "v2"


class TestIntegrationsClearRoute:
    def test_clear_route_wipes_fields(self, client):
        client.patch("/api/integrations/Accounting", json={"api_key": "k"})
        resp = client.post("/api/integrations/Accounting/clear")
        assert resp.status_code == 200
        assert resp.get_json()["entry"]["api_key"] is None

    def test_clear_route_unknown_type_400s(self, client):
        resp = client.post("/api/integrations/Nonsense/clear")
        assert resp.status_code == 400


# ── Settings page renders System Keys section ──────────────────────────


class TestSettingsPageSystemKeys:
    def test_settings_page_renders_system_keys_section(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"System Keys" in resp.data

    def test_settings_page_lists_all_seven_integration_types(self, client):
        resp = client.get("/settings")
        html = resp.data.decode("utf-8")
        for t in reg.INTEGRATION_TYPES:
            assert t in html

    def test_settings_page_reflects_configured_status_after_upsert(self, client):
        client.patch("/api/integrations/DAT", json={"api_key": "dat-secret"})
        resp = client.get("/settings")
        html = resp.data.decode("utf-8")
        assert "dat-secret" in html
        assert "Configured" in html
