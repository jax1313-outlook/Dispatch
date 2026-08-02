"""Tests for the Dispatch Data Engine — models, store, services, and API."""

from __future__ import annotations

import json

import pytest

from dispatch import db, models, services, store


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def tmp_dispatch_db(tmp_path, monkeypatch):
    """Redirect dispatch database to a per-test temp directory."""
    db_path = tmp_path / "dispatch.db"
    db.set_db_path(db_path)
    yield db_path
    db.set_db_path(None)


@pytest.fixture
def sample_load():
    return services.create_load(
        customer="Acme Freight",
        broker_shipper="Southeast Partners",
        pickup_location="Jacksonville, FL 32202",
        delivery_location="Savannah, GA 31401",
        pickup_datetime="2026-08-03T06:00:00Z",
        delivery_datetime="2026-08-03T14:00:00Z",
        equipment="Dry Van 53'",
        driver="Mike",
        notes="Live load/unload",
    )


@pytest.fixture
def dispatched_load(sample_load):
    services.add_milestone(
        sample_load["load_id"], "dispatched",
        location="Jacksonville, FL", entered_by="dispatcher",
    )
    return sample_load


@pytest.fixture
def delivered_load(dispatched_load):
    load_id = dispatched_load["load_id"]
    services.add_milestone(load_id, "arrived_pickup")
    services.add_milestone(load_id, "loaded")
    services.add_milestone(load_id, "departed_pickup")
    services.add_milestone(load_id, "arrived_delivery")
    services.add_milestone(load_id, "delivered", location="Savannah, GA")
    return dispatched_load


# ── Model tests ───────────────────────────────────────────────────────

class TestModels:
    def test_load_defaults(self):
        load = models.Load(customer="Test")
        assert load.load_id.startswith("LOAD-")
        assert load.status == "created"
        assert load.created_at
        assert load.updated_at

    def test_load_invalid_status(self):
        with pytest.raises(ValueError, match="Invalid status"):
            models.Load(customer="Test", status="bogus")

    def test_milestone_defaults(self):
        ms = models.MilestoneEvent(load_id="L1", event_type="dispatched")
        assert ms.milestone_id.startswith("MS-")
        assert ms.event_time
        assert ms.validation_status == "pending"

    def test_milestone_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid event_type"):
            models.MilestoneEvent(load_id="L1", event_type="bogus")

    def test_milestone_invalid_source(self):
        with pytest.raises(ValueError, match="Invalid source"):
            models.MilestoneEvent(load_id="L1", event_type="dispatched", source="alien")

    def test_evidence_defaults(self):
        ev = models.EvidenceItem(load_id="L1")
        assert ev.evidence_id.startswith("EV-")
        assert ev.evidence_type == "document"

    def test_evidence_checksum(self):
        ev = models.EvidenceItem(load_id="L1")
        result = ev.compute_checksum(b"test data")
        assert result == ev.checksum
        assert len(result) == 64

    def test_evidence_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid evidence_type"):
            models.EvidenceItem(load_id="L1", evidence_type="hologram")

    def test_exception_defaults(self):
        exc = models.ExceptionNotice(load_id="L1")
        assert exc.exception_id.startswith("EXC-")
        assert exc.status == "open"
        assert exc.severity == "medium"

    def test_exception_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid exception_type"):
            models.ExceptionNotice(load_id="L1", exception_type="alien_invasion")

    def test_exception_invalid_severity(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            models.ExceptionNotice(load_id="L1", severity="extreme")

    def test_pod_defaults(self):
        pod = models.PODPackage(load_id="L1")
        assert pod.pod_id.startswith("POD-")
        assert pod.status == "draft"
        assert pod.evidence_ids == []

    def test_pod_invalid_status(self):
        with pytest.raises(ValueError, match="Invalid status"):
            models.PODPackage(load_id="L1", status="bogus")

    def test_retention_defaults(self):
        ret = models.RetentionArchive(load_id="L1")
        assert ret.archive_id.startswith("RET-")
        assert ret.retention_status == "active"

    def test_retention_invalid_status(self):
        with pytest.raises(ValueError, match="Invalid retention_status"):
            models.RetentionArchive(load_id="L1", retention_status="bogus")

    def test_visibility_defaults(self):
        vis = models.LoadVisibilityRecord(load_id="L1")
        assert vis.updated_at
        assert vis.exception_flag is False

    def test_to_dict(self):
        load = models.Load(customer="Test")
        d = load.to_dict()
        assert isinstance(d, dict)
        assert d["customer"] == "Test"
        assert d["load_id"] == load.load_id


# ── Database tests ────────────────────────────────────────────────────

class TestDatabase:
    def test_schema_creates_tables(self, tmp_dispatch_db):
        with db.get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        names = {t["name"] for t in tables}
        assert "loads" in names
        assert "visibility" in names
        assert "milestones" in names
        assert "evidence" in names
        assert "exceptions" in names
        assert "pod_packages" in names
        assert "retention" in names

    def test_connection_rollback_on_error(self, tmp_dispatch_db):
        load = models.Load(customer="Rollback Test")
        store.create_load(load)
        try:
            with db.get_connection() as conn:
                conn.execute("UPDATE loads SET customer='changed' WHERE load_id=?", (load.load_id,))
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        result = store.get_load(load.load_id)
        assert result["customer"] == "Rollback Test"

    def test_foreign_keys_enforced(self, tmp_dispatch_db):
        ms = models.MilestoneEvent(load_id="NONEXISTENT", event_type="dispatched")
        with pytest.raises(Exception):
            store.create_milestone(ms)


# ── Store tests ───────────────────────────────────────────────────────

class TestStore:
    def test_create_and_get_load(self, tmp_dispatch_db):
        load = models.Load(customer="Store Test", broker_shipper="Broker A")
        store.create_load(load)
        result = store.get_load(load.load_id)
        assert result is not None
        assert result["customer"] == "Store Test"
        assert result["broker_shipper"] == "Broker A"

    def test_list_loads_empty(self, tmp_dispatch_db):
        assert store.list_loads() == []

    def test_list_loads_with_filter(self, tmp_dispatch_db):
        l1 = models.Load(customer="A", status="created")
        l2 = models.Load(customer="B", status="created")
        store.create_load(l1)
        store.create_load(l2)
        store.update_load(l2.load_id, status="dispatched")
        assert len(store.list_loads(status="created")) == 1
        assert len(store.list_loads(status="dispatched")) == 1
        assert len(store.list_loads()) == 2

    def test_update_load(self, tmp_dispatch_db):
        load = models.Load(customer="Update Test")
        store.create_load(load)
        result = store.update_load(load.load_id, customer="Updated Name")
        assert result["customer"] == "Updated Name"

    def test_update_load_not_found(self, tmp_dispatch_db):
        assert store.update_load("NONEXISTENT") is None

    def test_delete_load(self, tmp_dispatch_db):
        load = models.Load(customer="Delete Test")
        store.create_load(load)
        assert store.delete_load(load.load_id) is True
        assert store.get_load(load.load_id) is None

    def test_delete_load_not_found(self, tmp_dispatch_db):
        assert store.delete_load("NONEXISTENT") is False

    def test_visibility_upsert(self, tmp_dispatch_db):
        load = models.Load(customer="Vis Test")
        store.create_load(load)
        vis = models.LoadVisibilityRecord(load_id=load.load_id, current_status="dispatched")
        store.upsert_visibility(vis)
        result = store.get_visibility(load.load_id)
        assert result["current_status"] == "dispatched"
        vis2 = models.LoadVisibilityRecord(load_id=load.load_id, current_status="in_transit")
        store.upsert_visibility(vis2)
        result2 = store.get_visibility(load.load_id)
        assert result2["current_status"] == "in_transit"

    def test_milestone_crud(self, tmp_dispatch_db):
        load = models.Load(customer="MS Test")
        store.create_load(load)
        ms = models.MilestoneEvent(load_id=load.load_id, event_type="dispatched")
        store.create_milestone(ms)
        result = store.get_milestone(ms.milestone_id)
        assert result["event_type"] == "dispatched"
        timeline = store.list_milestones(load.load_id)
        assert len(timeline) == 1

    def test_evidence_crud(self, tmp_dispatch_db):
        load = models.Load(customer="Ev Test")
        store.create_load(load)
        ev = models.EvidenceItem(load_id=load.load_id, evidence_type="bol", description="Bill of Lading")
        store.create_evidence(ev)
        result = store.get_evidence(ev.evidence_id)
        assert result["evidence_type"] == "bol"
        items = store.list_evidence(load.load_id)
        assert len(items) == 1

    def test_exception_crud(self, tmp_dispatch_db):
        load = models.Load(customer="Exc Test")
        store.create_load(load)
        exc = models.ExceptionNotice(load_id=load.load_id, exception_type="delay", severity="high")
        store.create_exception(exc)
        items = store.list_exceptions(load_id=load.load_id)
        assert len(items) == 1
        assert items[0]["severity"] == "high"

    def test_exception_update(self, tmp_dispatch_db):
        load = models.Load(customer="Exc Upd Test")
        store.create_load(load)
        exc = models.ExceptionNotice(load_id=load.load_id)
        store.create_exception(exc)
        result = store.update_exception(exc.exception_id, status="resolved", resolution_note="Fixed")
        assert result["status"] == "resolved"
        assert result["resolution_note"] == "Fixed"

    def test_exception_update_not_found(self, tmp_dispatch_db):
        assert store.update_exception("NONEXISTENT") is None

    def test_pod_crud(self, tmp_dispatch_db):
        load = models.Load(customer="POD Test")
        store.create_load(load)
        pod = models.PODPackage(load_id=load.load_id, evidence_ids=["EV-1", "EV-2"], status="complete")
        store.create_pod(pod)
        result = store.get_pod(pod.pod_id)
        assert result["evidence_ids"] == ["EV-1", "EV-2"]
        assert result["status"] == "complete"
        pods = store.list_pods(load.load_id)
        assert len(pods) == 1

    def test_pod_update(self, tmp_dispatch_db):
        load = models.Load(customer="POD Upd")
        store.create_load(load)
        pod = models.PODPackage(load_id=load.load_id)
        store.create_pod(pod)
        result = store.update_pod(pod.pod_id, status="delivered", recipient="broker@example.com")
        assert result["status"] == "delivered"

    def test_pod_update_not_found(self, tmp_dispatch_db):
        assert store.update_pod("NONEXISTENT") is None

    def test_retention_crud(self, tmp_dispatch_db):
        load = models.Load(customer="Ret Test")
        store.create_load(load)
        ret = models.RetentionArchive(load_id=load.load_id, evidence_index=["EV-1"])
        store.create_retention(ret)
        result = store.get_retention(ret.archive_id)
        assert result["evidence_index"] == ["EV-1"]
        by_load = store.get_retention_by_load(load.load_id)
        assert by_load is not None
        all_ret = store.list_retentions()
        assert len(all_ret) == 1


# ── Service tests ─────────────────────────────────────────────────────

class TestServices:
    def test_create_load_creates_visibility(self, sample_load):
        vis = services.get_visibility(sample_load["load_id"])
        assert vis is not None
        assert vis["current_status"] == "created"
        assert vis["next_expected_milestone"] == "dispatched"

    def test_create_load_shape(self, sample_load):
        assert sample_load["load_id"].startswith("LOAD-")
        assert sample_load["customer"] == "Acme Freight"
        assert sample_load["equipment"] == "Dry Van 53'"
        assert sample_load["status"] == "created"

    def test_list_loads(self, sample_load):
        loads = services.list_loads()
        assert len(loads) == 1
        assert loads[0]["load_id"] == sample_load["load_id"]

    def test_list_loads_by_status(self, sample_load):
        assert len(services.list_loads(status="created")) == 1
        assert len(services.list_loads(status="dispatched")) == 0

    def test_update_load(self, sample_load):
        result = services.update_load(sample_load["load_id"], driver="Bob")
        assert result["driver"] == "Bob"

    def test_add_milestone_updates_status(self, sample_load):
        load_id = sample_load["load_id"]
        services.add_milestone(load_id, "dispatched", location="JAX")
        load = services.get_load(load_id)
        assert load["status"] == "dispatched"
        vis = services.get_visibility(load_id)
        assert vis["current_status"] == "dispatched"
        assert vis["last_milestone"] == "dispatched"
        assert vis["next_expected_milestone"] == "en_route_pickup"

    def test_add_milestone_not_found(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.add_milestone("NONEXISTENT", "dispatched")

    def test_full_milestone_chain(self, sample_load):
        load_id = sample_load["load_id"]
        chain = ["dispatched", "en_route_pickup", "arrived_pickup", "loaded",
                 "departed_pickup", "in_transit", "arrived_delivery", "delivered"]
        for event in chain:
            services.add_milestone(load_id, event, location="Test Location")
        timeline = services.get_timeline(load_id)
        assert len(timeline) == 8
        load = services.get_load(load_id)
        assert load["status"] == "delivered"

    def test_checkpoint_does_not_change_status(self, dispatched_load):
        load_id = dispatched_load["load_id"]
        services.add_milestone(load_id, "checkpoint", note="Rest stop")
        load = services.get_load(load_id)
        assert load["status"] == "dispatched"

    def test_attach_evidence(self, sample_load):
        load_id = sample_load["load_id"]
        ev = services.attach_evidence(
            load_id, evidence_type="bol", description="Bill of Lading",
            file_path="/evidence/bol.pdf", uploaded_by="Mike",
        )
        assert ev["evidence_type"] == "bol"
        items = services.list_evidence(load_id)
        assert len(items) == 1

    def test_attach_evidence_with_checksum(self, sample_load):
        ev = services.attach_evidence(
            sample_load["load_id"], description="Photo",
            evidence_type="photo", file_data=b"fake image bytes",
        )
        assert ev["checksum"] is not None
        assert len(ev["checksum"]) == 64

    def test_attach_evidence_not_found(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.attach_evidence("NONEXISTENT")

    def test_open_exception_sets_flag(self, sample_load):
        load_id = sample_load["load_id"]
        exc = services.open_exception(
            load_id, exception_type="delay", severity="high",
            description="Shipper delayed loading",
        )
        assert exc["status"] == "open"
        vis = services.get_visibility(load_id)
        assert vis["exception_flag"] is True

    def test_open_exception_not_found(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.open_exception("NONEXISTENT")

    def test_resolve_exception_clears_flag(self, sample_load):
        load_id = sample_load["load_id"]
        exc = services.open_exception(load_id, description="Delay")
        services.resolve_exception(exc["exception_id"], resolution_note="Resolved")
        vis = services.get_visibility(load_id)
        assert vis["exception_flag"] is False

    def test_resolve_exception_keeps_flag_if_others_open(self, sample_load):
        load_id = sample_load["load_id"]
        exc1 = services.open_exception(load_id, description="Delay 1")
        services.open_exception(load_id, description="Delay 2")
        services.resolve_exception(exc1["exception_id"])
        vis = services.get_visibility(load_id)
        assert vis["exception_flag"] is True

    def test_resolve_exception_not_found(self):
        assert services.resolve_exception("NONEXISTENT") is None

    def test_list_exceptions(self, sample_load):
        load_id = sample_load["load_id"]
        services.open_exception(load_id, description="A")
        services.open_exception(load_id, description="B")
        assert len(services.list_exceptions(load_id=load_id)) == 2
        assert len(services.list_exceptions(load_id=load_id, status="open")) == 2

    def test_generate_pod(self, delivered_load):
        load_id = delivered_load["load_id"]
        services.attach_evidence(load_id, evidence_type="bol", description="BOL")
        services.attach_evidence(load_id, evidence_type="pod", description="POD Photo")
        pod = services.generate_pod(load_id, recipient="broker@example.com")
        assert pod["status"] == "complete"
        assert len(pod["evidence_ids"]) == 2
        assert pod["recipient"] == "broker@example.com"

    def test_generate_pod_not_found(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.generate_pod("NONEXISTENT")

    def test_generate_pod_requires_delivered(self, sample_load):
        with pytest.raises(ValueError, match="must be delivered"):
            services.generate_pod(sample_load["load_id"])

    def test_generate_pod_with_specific_evidence(self, delivered_load):
        load_id = delivered_load["load_id"]
        ev1 = services.attach_evidence(load_id, evidence_type="bol", description="BOL")
        services.attach_evidence(load_id, evidence_type="photo", description="Photo")
        pod = services.generate_pod(load_id, evidence_ids=[ev1["evidence_id"]])
        assert len(pod["evidence_ids"]) == 1

    def test_generate_pod_adds_milestone(self, delivered_load):
        load_id = delivered_load["load_id"]
        services.generate_pod(load_id)
        milestones = services.get_timeline(load_id)
        pod_ms = [m for m in milestones if m["event_type"] == "pod_received"]
        assert len(pod_ms) == 1
        assert pod_ms[0]["source"] == "system"

    def test_list_pods(self, delivered_load):
        load_id = delivered_load["load_id"]
        services.generate_pod(load_id)
        pods = services.list_pods(load_id)
        assert len(pods) == 1

    def test_archive_load(self, delivered_load):
        load_id = delivered_load["load_id"]
        services.attach_evidence(load_id, evidence_type="pod", description="POD")
        services.generate_pod(load_id)
        ret = services.archive_load(load_id)
        assert ret["load_id"] == load_id
        assert ret["archive_id"].startswith("RET-")
        assert len(ret["evidence_index"]) == 1
        assert ret["pod_package_id"] is not None
        load = services.get_load(load_id)
        assert load["status"] == "archived"
        vis = services.get_visibility(load_id)
        assert vis["current_status"] == "archived"

    def test_archive_load_not_found(self):
        with pytest.raises(ValueError, match="Load not found"):
            services.archive_load("NONEXISTENT")

    def test_archive_load_already_archived(self, sample_load):
        services.archive_load(sample_load["load_id"])
        with pytest.raises(ValueError, match="already archived"):
            services.archive_load(sample_load["load_id"])

    def test_get_load_bundle(self, sample_load):
        load_id = sample_load["load_id"]
        services.add_milestone(load_id, "dispatched", location="JAX")
        services.attach_evidence(load_id, evidence_type="bol", description="BOL")
        services.open_exception(load_id, description="Test")
        bundle = services.get_load_bundle(load_id)
        assert bundle["load"]["load_id"] == load_id
        assert bundle["visibility"] is not None
        assert len(bundle["milestones"]) == 1
        assert len(bundle["evidence"]) == 1
        assert len(bundle["exceptions"]) == 1

    def test_get_load_bundle_not_found(self):
        assert services.get_load_bundle("NONEXISTENT") is None

    def test_retention_list(self, sample_load):
        services.archive_load(sample_load["load_id"])
        retentions = services.list_retentions()
        assert len(retentions) == 1

    def test_get_retention(self, sample_load):
        services.archive_load(sample_load["load_id"])
        ret = services.get_retention(sample_load["load_id"])
        assert ret is not None
        assert ret["load_id"] == sample_load["load_id"]


# ── Full workflow test ────────────────────────────────────────────────

class TestFullWorkflow:
    def test_load_lifecycle(self, tmp_dispatch_db):
        """Step 8: dummy load moves from creation through delivery, POD, and archive."""
        load = services.create_load(
            customer="Full Workflow Inc.",
            broker_shipper="Test Broker",
            pickup_location="Jacksonville, FL",
            delivery_location="Savannah, GA",
            equipment="Dry Van 53'",
            driver="Mike",
        )
        load_id = load["load_id"]

        services.add_milestone(load_id, "dispatched", location="Jacksonville, FL", entered_by="dispatcher")
        services.add_milestone(load_id, "en_route_pickup", location="Jacksonville, FL", source="eld")
        services.add_milestone(load_id, "arrived_pickup", location="Jacksonville, FL", source="driver")
        services.attach_evidence(load_id, evidence_type="bol", description="Bill of Lading signed")
        services.add_milestone(load_id, "loaded", location="Jacksonville, FL", entered_by="driver")
        services.add_milestone(load_id, "departed_pickup", location="Jacksonville, FL")
        services.add_milestone(load_id, "in_transit", location="I-95 N")

        exc = services.open_exception(
            load_id, exception_type="detention", severity="low",
            description="30 min wait at pickup — within normal range",
        )
        vis = services.get_visibility(load_id)
        assert vis["exception_flag"] is True
        services.resolve_exception(exc["exception_id"], resolution_note="Cleared")

        services.add_milestone(load_id, "checkpoint", location="I-95 MM 40", note="Rest stop")
        services.add_milestone(load_id, "arrived_delivery", location="Savannah, GA", source="eld")
        services.add_milestone(load_id, "delivered", location="Savannah, GA", source="driver")
        services.attach_evidence(load_id, evidence_type="pod", description="POD photo at dock")
        services.attach_evidence(load_id, evidence_type="photo", description="Delivery confirmation photo")
        services.add_milestone(load_id, "pod_received", location="Savannah, GA")

        pod = services.generate_pod(load_id, recipient="broker@testbroker.com")
        assert pod["status"] == "complete"
        assert len(pod["evidence_ids"]) == 3

        services.add_milestone(load_id, "completed", location="Savannah, GA")

        ret = services.archive_load(load_id)
        assert ret["archive_id"].startswith("RET-")
        assert ret["pod_package_id"] == pod["pod_id"]
        assert len(ret["evidence_index"]) == 3

        final_load = services.get_load(load_id)
        assert final_load["status"] == "archived"

        timeline = services.get_timeline(load_id)
        assert len(timeline) == 11

        bundle = services.get_load_bundle(load_id)
        assert bundle["retention"] is not None


# ── API tests ─────────────────────────────────────────────────────────

class TestDispatchAPI:
    @pytest.fixture
    def app(self, tmp_dispatch_db, tmp_archive, monkeypatch):
        from portal.app import create_app
        from cin_lite import pending
        monkeypatch.setattr(pending, "_PENDING_DIR", tmp_archive / "Pending")
        app = create_app({"TESTING": True})
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _create_load(self, client, **overrides):
        data = {"customer": "API Test Co", "pickup_location": "JAX, FL"}
        data.update(overrides)
        return client.post("/api/dispatch/loads", json=data)

    def _deliver_load(self, client, load_id):
        for evt in ("dispatched", "arrived_pickup", "loaded",
                     "departed_pickup", "arrived_delivery", "delivered"):
            client.post(f"/api/dispatch/loads/{load_id}/milestones",
                        json={"event_type": evt})

    def test_create_load(self, client):
        resp = self._create_load(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["load"]["customer"] == "API Test Co"

    def test_create_load_missing_customer(self, client):
        resp = client.post("/api/dispatch/loads", json={})
        assert resp.status_code == 400

    def test_list_loads(self, client):
        self._create_load(client)
        resp = client.get("/api/dispatch/loads")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1

    def test_list_loads_filter_status(self, client):
        self._create_load(client)
        resp = client.get("/api/dispatch/loads?status=created")
        assert resp.get_json()["count"] == 1
        resp = client.get("/api/dispatch/loads?status=dispatched")
        assert resp.get_json()["count"] == 0

    def test_list_loads_invalid_status(self, client):
        resp = client.get("/api/dispatch/loads?status=bogus")
        assert resp.status_code == 400

    def test_get_load(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.get(f"/api/dispatch/loads/{load_id}")
        assert resp.status_code == 200

    def test_get_load_not_found(self, client):
        resp = client.get("/api/dispatch/loads/NONEXISTENT")
        assert resp.status_code == 404

    def test_update_load(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.patch(f"/api/dispatch/loads/{load_id}", json={"driver": "Bob"})
        assert resp.status_code == 200
        assert resp.get_json()["load"]["driver"] == "Bob"

    def test_update_load_invalid_status(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.patch(f"/api/dispatch/loads/{load_id}", json={"status": "bogus"})
        assert resp.status_code == 400

    def test_update_load_not_found(self, client):
        resp = client.patch("/api/dispatch/loads/NONEXISTENT", json={"driver": "X"})
        assert resp.status_code == 404

    def test_load_bundle(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.get(f"/api/dispatch/loads/{load_id}/bundle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "load" in data
        assert "visibility" in data
        assert "milestones" in data

    def test_load_bundle_not_found(self, client):
        resp = client.get("/api/dispatch/loads/NONEXISTENT/bundle")
        assert resp.status_code == 404

    def test_visibility(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.get(f"/api/dispatch/loads/{load_id}/visibility")
        assert resp.status_code == 200
        assert resp.get_json()["visibility"]["current_status"] == "created"

    def test_visibility_not_found(self, client):
        resp = client.get("/api/dispatch/loads/NONEXISTENT/visibility")
        assert resp.status_code == 404

    def test_add_milestone(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/milestones", json={
            "event_type": "dispatched", "location": "JAX, FL",
        })
        assert resp.status_code == 201
        assert resp.get_json()["milestone"]["event_type"] == "dispatched"

    def test_add_milestone_missing_type(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/milestones", json={})
        assert resp.status_code == 400

    def test_add_milestone_invalid_type(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/milestones", json={
            "event_type": "bogus",
        })
        assert resp.status_code == 400

    def test_add_milestone_invalid_source(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/milestones", json={
            "event_type": "dispatched", "source": "alien",
        })
        assert resp.status_code == 400

    def test_add_milestone_load_not_found(self, client):
        resp = client.post("/api/dispatch/loads/NONEXISTENT/milestones", json={
            "event_type": "dispatched",
        })
        assert resp.status_code == 404

    def test_list_milestones(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/milestones", json={
            "event_type": "dispatched",
        })
        resp = client.get(f"/api/dispatch/loads/{load_id}/milestones")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_attach_evidence(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "bol", "description": "Bill of Lading",
        })
        assert resp.status_code == 201
        assert resp.get_json()["evidence"]["evidence_type"] == "bol"

    def test_attach_evidence_invalid_type(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "hologram",
        })
        assert resp.status_code == 400

    def test_attach_evidence_load_not_found(self, client):
        resp = client.post("/api/dispatch/loads/NONEXISTENT/evidence", json={
            "evidence_type": "bol",
        })
        assert resp.status_code == 404

    def test_list_evidence(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "pod", "description": "Photo",
        })
        resp = client.get(f"/api/dispatch/loads/{load_id}/evidence")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_open_exception(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "exception_type": "delay", "severity": "high", "description": "Late",
        })
        assert resp.status_code == 201
        assert resp.get_json()["exception"]["status"] == "open"

    def test_open_exception_invalid_type(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "exception_type": "bogus",
        })
        assert resp.status_code == 400

    def test_open_exception_invalid_severity(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "severity": "extreme",
        })
        assert resp.status_code == 400

    def test_open_exception_load_not_found(self, client):
        resp = client.post("/api/dispatch/loads/NONEXISTENT/exceptions", json={
            "description": "Late",
        })
        assert resp.status_code == 404

    def test_list_exceptions(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "description": "Issue",
        })
        resp = client.get(f"/api/dispatch/loads/{load_id}/exceptions")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_list_exceptions_filter_status(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "description": "Issue",
        })
        resp = client.get(f"/api/dispatch/loads/{load_id}/exceptions?status=open")
        assert resp.get_json()["count"] == 1
        resp = client.get(f"/api/dispatch/loads/{load_id}/exceptions?status=resolved")
        assert resp.get_json()["count"] == 0

    def test_list_exceptions_invalid_status(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.get(f"/api/dispatch/loads/{load_id}/exceptions?status=bogus")
        assert resp.status_code == 400

    def test_resolve_exception(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        exc_id = client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "description": "Issue",
        }).get_json()["exception"]["exception_id"]
        resp = client.post(f"/api/dispatch/exceptions/{exc_id}/resolve", json={
            "resolution_note": "Fixed",
        })
        assert resp.status_code == 200
        assert resp.get_json()["exception"]["status"] == "resolved"

    def test_resolve_exception_not_found(self, client):
        resp = client.post("/api/dispatch/exceptions/NONEXISTENT/resolve", json={})
        assert resp.status_code == 404

    def test_generate_pod(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        self._deliver_load(client, load_id)
        client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "pod", "description": "POD",
        })
        resp = client.post(f"/api/dispatch/loads/{load_id}/pod", json={
            "recipient": "broker@example.com",
        })
        assert resp.status_code == 201
        assert resp.get_json()["pod"]["status"] == "complete"

    def test_generate_pod_not_found(self, client):
        resp = client.post("/api/dispatch/loads/NONEXISTENT/pod", json={})
        assert resp.status_code == 404

    def test_list_pods(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        self._deliver_load(client, load_id)
        client.post(f"/api/dispatch/loads/{load_id}/pod", json={})
        resp = client.get(f"/api/dispatch/loads/{load_id}/pod")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_archive_load(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        resp = client.post(f"/api/dispatch/loads/{load_id}/archive")
        assert resp.status_code == 201
        load = client.get(f"/api/dispatch/loads/{load_id}").get_json()["load"]
        assert load["status"] == "archived"

    def test_archive_load_not_found(self, client):
        resp = client.post("/api/dispatch/loads/NONEXISTENT/archive")
        assert resp.status_code == 404

    def test_archive_load_already_archived(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/archive")
        resp = client.post(f"/api/dispatch/loads/{load_id}/archive")
        assert resp.status_code == 409

    def test_list_retentions(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/archive")
        resp = client.get("/api/dispatch/retention")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

    def test_get_retention(self, client):
        load_id = self._create_load(client).get_json()["load"]["load_id"]
        client.post(f"/api/dispatch/loads/{load_id}/archive")
        resp = client.get(f"/api/dispatch/retention/{load_id}")
        assert resp.status_code == 200

    def test_get_retention_not_found(self, client):
        resp = client.get("/api/dispatch/retention/NONEXISTENT")
        assert resp.status_code == 404


class TestDispatchEndToEnd:
    """Full lifecycle: create → dispatch → deliver → POD → archive."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        db.set_db_path(tmp_path / "e2e.db")
        yield
        db.set_db_path(None)

    @pytest.fixture()
    def client(self):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_full_lifecycle(self, client):
        # 1. Create load
        resp = client.post("/api/dispatch/loads", json={
            "customer": "E2E Freight Co",
            "pickup_location": "Atlanta, GA",
            "delivery_location": "Savannah, GA",
            "driver": "Driver Mike",
            "equipment": "53ft Dry Van",
        })
        assert resp.status_code == 201
        load = resp.get_json()["load"]
        load_id = load["load_id"]
        assert load["status"] == "created"

        # 2. Verify visibility record was created
        resp = client.get(f"/api/dispatch/loads/{load_id}/visibility")
        assert resp.status_code == 200
        vis = resp.get_json()["visibility"]
        assert vis["current_status"] == "created"
        assert vis["next_expected_milestone"] == "dispatched"

        # 3. Walk through milestone chain
        milestones = [
            ("dispatched", "dispatched"),
            ("en_route_pickup", "en_route_pickup"),
            ("arrived_pickup", "at_pickup"),
            ("loaded", "picked_up"),
            ("departed_pickup", "in_transit"),
            ("in_transit", "in_transit"),
            ("arrived_delivery", "at_delivery"),
            ("delivered", "delivered"),
        ]
        for event_type, expected_status in milestones:
            resp = client.post(f"/api/dispatch/loads/{load_id}/milestones", json={
                "event_type": event_type,
                "source": "driver",
                "location": "On Route",
            })
            assert resp.status_code == 201

            load_resp = client.get(f"/api/dispatch/loads/{load_id}")
            assert load_resp.get_json()["load"]["status"] == expected_status

        # 4. Verify full timeline
        resp = client.get(f"/api/dispatch/loads/{load_id}/milestones")
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 8

        # 5. Attach evidence
        resp = client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "pod",
            "description": "Signed delivery receipt",
            "uploaded_by": "Driver Mike",
        })
        assert resp.status_code == 201
        ev_id = resp.get_json()["evidence"]["evidence_id"]

        resp = client.post(f"/api/dispatch/loads/{load_id}/evidence", json={
            "evidence_type": "photo",
            "description": "Dock photo",
        })
        assert resp.status_code == 201

        resp = client.get(f"/api/dispatch/loads/{load_id}/evidence")
        assert resp.get_json()["count"] == 2

        # 6. Open and resolve an exception
        resp = client.post(f"/api/dispatch/loads/{load_id}/exceptions", json={
            "exception_type": "damage",
            "severity": "low",
            "description": "Minor pallet scratch",
        })
        assert resp.status_code == 201
        exc_id = resp.get_json()["exception"]["exception_id"]

        vis = client.get(f"/api/dispatch/loads/{load_id}/visibility").get_json()["visibility"]
        assert vis["exception_flag"] is True

        resp = client.post(f"/api/dispatch/exceptions/{exc_id}/resolve", json={
            "resolution_note": "Cosmetic only, customer accepted",
        })
        assert resp.status_code == 200
        assert resp.get_json()["exception"]["status"] == "resolved"

        vis = client.get(f"/api/dispatch/loads/{load_id}/visibility").get_json()["visibility"]
        assert vis["exception_flag"] is False

        # 7. Generate POD package
        resp = client.post(f"/api/dispatch/loads/{load_id}/pod", json={
            "recipient": "billing@e2efreight.com",
            "notes": "Complete delivery",
            "evidence_ids": [ev_id],
        })
        assert resp.status_code == 201
        pod = resp.get_json()["pod"]
        assert pod["status"] == "complete"
        assert ev_id in pod["evidence_ids"]

        # pod_received milestone auto-added
        timeline = client.get(f"/api/dispatch/loads/{load_id}/milestones").get_json()
        assert any(m["event_type"] == "pod_received" for m in timeline["milestones"])

        # 8. Archive load
        resp = client.post(f"/api/dispatch/loads/{load_id}/archive")
        assert resp.status_code == 201
        ret = resp.get_json()["retention"]
        assert ret["load_id"] == load_id
        assert ret["final_status"] == "delivered"
        assert len(ret["evidence_index"]) == 2

        # Load status updated to archived
        load = client.get(f"/api/dispatch/loads/{load_id}").get_json()["load"]
        assert load["status"] == "archived"

        # 9. Verify retention record retrievable
        resp = client.get(f"/api/dispatch/retention/{load_id}")
        assert resp.status_code == 200

        # 10. Verify full bundle
        resp = client.get(f"/api/dispatch/loads/{load_id}/bundle")
        assert resp.status_code == 200
        bundle = resp.get_json()
        assert bundle["load"]["status"] == "archived"
        assert len(bundle["milestones"]) == 9  # 8 manual + 1 pod_received
        assert len(bundle["evidence"]) == 2
        assert len(bundle["pods"]) == 1
        assert bundle["retention"] is not None
