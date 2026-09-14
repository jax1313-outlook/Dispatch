"""Retention classes on the archive record (Company Library, Visibility SOP section 8).

"Do not use one purge clock for every load. Retention class should be stored
with each load/archive record." Build requirement: "Archive must support a
retention_class field. The system should warn when a record cannot purge under
the normal commercial rule." (Mike Zachary, 2026-09-13: "build retention class".)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from dispatch import notifications, retention, services
from dispatch.db import set_db_path

NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


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


def delivered(client, customer="Retention Co"):
    load = client.post("/api/dispatch/loads", json={"customer": customer}).get_json()["load"]
    for status in ("dispatched", "en_route_pickup", "at_pickup", "picked_up", "in_transit", "at_delivery", "delivered"):
        client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
    return load


def archived(client, **body):
    load = delivered(client)
    resp = client.post(f"/api/dispatch/loads/{load['load_id']}/archive", json=body)
    assert resp.status_code == 201, resp.get_json()
    return load, resp.get_json()["retention"]


class TestPurgeCheck:
    def record(self, **kw):
        base = {"retention_class": "normal_commercial", "legal_hold": False, "archived_at": "2026-01-01T00:00:00Z"}
        base.update(kw)
        return retention.purge_check(base, now=NOW)

    def test_normal_commercial_follows_the_normal_rule(self):
        check = self.record()
        assert check["normal_rule_applies"] is True and check["reasons"] == []

    def test_a_legal_hold_blocks_any_class(self):
        check = self.record(legal_hold=True, legal_hold_note="insurance claim 44")
        assert not check["normal_rule_applies"] and "insurance claim 44" in check["reasons"][0]

    def test_government_keeps_four_years(self):
        check = self.record(retention_class="government")
        assert not check["normal_rule_applies"] and check["earliest_purge"].startswith("2030-01-01")
        assert self.record(retention_class="government", archived_at="2021-01-01T00:00:00Z")["normal_rule_applies"]

    def test_high_value_securement_keeps_four_years(self):
        assert not self.record(retention_class="high_value_securement")["normal_rule_applies"]

    def test_far_counts_three_years_from_final_payment(self):
        assert "final payment date is not recorded" in self.record(retention_class="far_contract")["reasons"][0]
        check = self.record(retention_class="far_contract", final_payment_at="2025-06-30")
        assert not check["normal_rule_applies"] and check["earliest_purge"].startswith("2028-06-30")
        assert self.record(retention_class="far_contract", final_payment_at="2023-01-01")["normal_rule_applies"]

    def test_a_dispute_holds_until_resolved_and_then_still_needs_confirming(self):
        assert "not recorded as resolved" in self.record(retention_class="dispute_detention_claim")["reasons"][0]
        resolved = self.record(retention_class="dispute_detention_claim", dispute_resolved_at="2026-08-01")
        assert not resolved["normal_rule_applies"] and "still has to be confirmed" in resolved["reasons"][0]

    def test_legal_insurance_audit_hold_class_never_purges_on_its_own(self):
        assert not self.record(retention_class="legal_insurance_audit_hold", archived_at="2000-01-01")["normal_rule_applies"]

    def test_unknown_classes_are_refused(self):
        with pytest.raises(ValueError):
            retention.validate_class("forever")


class TestArchiveRecord:
    def test_archiving_defaults_to_normal_commercial(self, client):
        load, ret = archived(client)
        stored = client.get(f"/api/dispatch/retention/{load['load_id']}").get_json()["retention"]
        assert (stored["retention_class"], stored["legal_hold"]) == ("normal_commercial", False)
        assert stored["purge_check"]["normal_rule_applies"] is True

    def test_archiving_with_a_class_and_hold(self, client):
        load, ret = archived(client, retention_class="government", legal_hold=True, legal_hold_note="FEMA audit")
        assert ret["retention_class"] == "government"
        stored = client.get(f"/api/dispatch/retention/{load['load_id']}").get_json()["retention"]
        assert stored["legal_hold"] is True and not stored["purge_check"]["normal_rule_applies"]

    def test_archiving_with_an_unknown_class_is_refused(self, client):
        load = delivered(client)
        resp = client.post(f"/api/dispatch/loads/{load['load_id']}/archive", json={"retention_class": "forever"})
        assert resp.status_code in (400, 409) and "retention class" in resp.get_json()["error"]
        assert services.get_retention(load["load_id"]) is None

    def test_class_hold_and_dates_can_change_after_archiving(self, client):
        load, _ = archived(client)
        url = f"/api/dispatch/retention/{load['load_id']}"
        resp = client.patch(url, json={"retention_class": "far_contract", "final_payment_at": "2026-09-01"})
        body = resp.get_json()["retention"]
        assert resp.status_code == 200 and body["retention_class"] == "far_contract"
        assert body["purge_check"]["earliest_purge"].startswith("2029-09-01")
        released = client.patch(url, json={"legal_hold": False}).get_json()["retention"]
        assert released["legal_hold"] is False

    def test_bad_changes_are_refused(self, client):
        load, _ = archived(client)
        url = f"/api/dispatch/retention/{load['load_id']}"
        assert client.patch(url, json={"retention_class": "forever"}).status_code == 400
        assert client.patch(url, json={"final_payment_at": "someday"}).status_code == 400
        assert client.patch(url, json={"archived_at": "2000-01-01"}).status_code == 400
        assert client.patch("/api/dispatch/retention/LOAD-NONE", json={"legal_hold": True}).status_code == 404

    def test_the_list_carries_the_purge_check(self, client):
        archived(client, retention_class="high_value_securement")
        items = client.get("/api/dispatch/retention").get_json()["archives"]
        assert items and not items[0]["purge_check"]["normal_rule_applies"]


class TestRetentionAlertCard:
    def test_a_record_that_cannot_purge_normally_raises_a_card(self, client):
        from portal.models import operations_feed
        archived(client)  # normal: no card
        load, _ = archived(client, retention_class="government")
        cards = [c for c in operations_feed.build_feed()["cards"] if c["source"] == "retention"]
        assert len(cards) == 1 and "Government / FEMA / DLA" in cards[0]["title"]
        assert "Normal purge does not apply" in cards[0]["summary"] and load["load_id"] in cards[0]["url"]


class TestBoundaries:
    def test_the_customer_never_sees_the_retention_class_or_hold(self, client):
        load, _ = archived(client, retention_class="dispute_detention_claim", legal_hold=True, legal_hold_note="claim 9")
        token = notifications.make_stakeholder_token(load["load_id"])
        body = client.get(f"/portal/loads/{load['load_id']}?token={token}&format=json").get_json()
        text = str(body["retention"])
        assert "dispute" not in text and "claim 9" not in text and "legal_hold" not in text

    def test_an_existing_database_gains_the_columns_as_normal_commercial(self, tmp_path):
        from dispatch import store
        path = tmp_path / "old.db"
        set_db_path(path)
        try:
            load = services.create_load(customer="Before Retention Classes")
            # The retention table as it was before this change: no class, no hold.
            conn = sqlite3.connect(path)
            conn.executescript("""
                DROP TABLE retention;
                CREATE TABLE retention (archive_id TEXT PRIMARY KEY, load_id TEXT NOT NULL REFERENCES loads(load_id),
                  final_status TEXT NOT NULL DEFAULT 'completed', pod_package_id TEXT,
                  evidence_index TEXT NOT NULL DEFAULT '[]', financial_summary TEXT NOT NULL DEFAULT '{}',
                  archive_location TEXT NOT NULL DEFAULT '', retention_status TEXT NOT NULL DEFAULT 'active',
                  archived_at TEXT NOT NULL);
            """)
            conn.execute("INSERT INTO retention (archive_id, load_id, archived_at) VALUES ('RET-OLD', ?, ?)",
                         (load["load_id"], "2026-01-01T00:00:00Z"))
            conn.commit()
            conn.close()
            old = store.get_retention_by_load(load["load_id"])
        finally:
            set_db_path(None)
        assert (old["retention_class"], old["legal_hold"], old["legal_hold_note"]) == ("normal_commercial", 0, "")
