"""Tests for the pipeline module and pipeline API routes."""

from __future__ import annotations

import json

import pytest

from cin_lite import control, pending, archive
from cin_lite.pipeline import process_contracts, resolve_decision, routing_history


# --------------------------------------------------------------------------- pipeline module

class TestProcessContracts:
    def test_returns_list(self, tmp_archive):
        results = process_contracts()
        assert isinstance(results, list)

    def test_pending_status_by_default(self, tmp_archive):
        results = process_contracts()
        for r in results:
            assert r["status"] == "pending"

    def test_action_override_decides_immediately(self, tmp_archive):
        results = process_contracts(action_override="reject")
        for r in results:
            assert r["status"] == "decided"
            assert r["action"] == "reject"

    def test_result_shape(self, tmp_archive):
        results = process_contracts()
        for r in results:
            assert "contract_id" in r
            assert "title" in r
            assert "agency" in r
            assert "summary" in r
            assert "recommendation" in r
            assert "priority" in r
            assert "flag_count" in r
            assert "checkpoint_email" in r


class TestProcessContractsResilience:
    def test_bad_contract_does_not_abort_batch(self, tmp_archive, monkeypatch):
        from cin_lite import acquisition, processing

        good = {"title": "Good Contract", "solicitation_number": "SOL-GOOD",
                "agency": "GSA", "naics_text": "", "description": "ok",
                "estimated_value": None, "response_date": None, "notes": ""}
        bad = {"title": "Bad Contract"}

        def mock_acquire():
            return [good, bad, good]

        orig_process = processing.process

        call_count = [0]
        def failing_process(contract):
            call_count[0] += 1
            if contract is bad:
                raise RuntimeError("simulated failure")
            return orig_process(contract)

        monkeypatch.setattr(acquisition, "acquire", mock_acquire)
        monkeypatch.setattr(processing, "process", failing_process)

        results = process_contracts()
        assert len(results) == 3
        statuses = [r["status"] for r in results]
        assert statuses.count("error") == 1
        assert statuses.count("pending") == 2
        assert results[1]["status"] == "error"
        assert "simulated failure" in results[1]["error"]


class TestResolveDecision:
    def _seed(self, tmp_archive, contract_id="CIN-RES-001"):
        pending.store(
            contract_id,
            {"title": "Resolve Test", "agency": "DOD",
             "solicitation_number": "SOL-R1", "estimated_value": 500000},
            {"set_aside_detection": {
                "module": "set_aside_detection", "version": "1.0",
                "flags": [], "findings": {}, "summary": "None",
                "score": None, "deterministic": True,
            }},
            "Summary for resolve",
            {"action": "approve_archive", "priority": "medium",
             "recipient": "none", "reason": "r", "notes": "n"},
            ["flag_a"],
        )

    def test_resolve_archives_and_clears_pending(self, tmp_archive):
        self._seed(tmp_archive)
        result = resolve_decision("CIN-RES-001", "approve_archive")
        assert result["action"] == "approve_archive"
        assert result["action_label"] == "Approve for archive"
        assert result["route"] == "ARCHIVE"
        assert result["title"] == "Resolve Test"
        assert pending.load("CIN-RES-001") is None

    def test_resolve_creates_routing_record(self, tmp_archive):
        self._seed(tmp_archive)
        resolve_decision("CIN-RES-001", "reject")
        routing_files = list((tmp_archive / "Routing").glob("*.json"))
        assert len(routing_files) == 1
        data = json.loads(routing_files[0].read_text())
        assert data["action"] == "reject"

    def test_resolve_missing_raises(self, tmp_archive):
        with pytest.raises(ValueError, match="No pending decision"):
            resolve_decision("CIN-NOPE", "reject")

    def test_resolve_proposal_triggers(self, tmp_archive):
        self._seed(tmp_archive, "CIN-RES-002")
        result = resolve_decision("CIN-RES-002", "approve_proposal")
        assert "proposal" in result
        assert "proposal_id" in result["proposal"]

    def test_followed_recommendation(self, tmp_archive):
        self._seed(tmp_archive)
        result = resolve_decision("CIN-RES-001", "approve_archive")
        assert result["followed_recommendation"] is True

    def test_not_followed_recommendation(self, tmp_archive):
        self._seed(tmp_archive)
        result = resolve_decision("CIN-RES-001", "reject")
        assert result["followed_recommendation"] is False


class TestRoutingHistory:
    def test_empty_when_no_routing(self, tmp_archive):
        assert routing_history() == []

    def test_returns_routing_records(self, tmp_archive):
        routing_dir = tmp_archive / "Routing"
        routing_dir.mkdir(parents=True)
        record = {"contract_id": "CIN-H-001", "action": "reject", "route": "REJECTED"}
        (routing_dir / "CIN-H-001.json").write_text(json.dumps(record))
        history = routing_history()
        assert len(history) == 1
        assert history[0]["contract_id"] == "CIN-H-001"

    def test_route_filter(self, tmp_archive):
        routing_dir = tmp_archive / "Routing"
        routing_dir.mkdir(parents=True)
        (routing_dir / "CIN-A.json").write_text(json.dumps(
            {"contract_id": "CIN-A", "action": "reject", "route": "REJECTED"}))
        (routing_dir / "CIN-B.json").write_text(json.dumps(
            {"contract_id": "CIN-B", "action": "flag_review", "route": "HUMAN_REVIEW"}))
        assert len(routing_history(route_filter="HUMAN_REVIEW")) == 1
        assert len(routing_history(route_filter="REJECTED")) == 1
        assert len(routing_history(route_filter="NONEXISTENT")) == 0
        assert len(routing_history()) == 2


# --------------------------------------------------------------------------- pipeline API routes

class TestPipelineAPI:
    @pytest.fixture
    def app(self, tmp_archive, monkeypatch):
        monkeypatch.setattr(pending, "_PENDING_DIR", tmp_archive / "Pending")
        from portal.app import create_app
        app = create_app({"TESTING": True})
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _seed(self, tmp_archive, contract_id="CIN-API-001"):
        pending.store(
            contract_id,
            {"title": "API Test Contract", "agency": "GSA",
             "solicitation_number": "SOL-A1", "estimated_value": 200000},
            {"set_aside_detection": {
                "module": "set_aside_detection", "version": "1.0",
                "flags": [], "findings": {}, "summary": "None",
                "score": None, "deterministic": True,
            }},
            "API summary",
            {"action": "reject", "priority": "low",
             "recipient": "none", "reason": "r", "notes": "n"},
            ["api_flag"],
        )

    def test_run_pipeline(self, client):
        resp = client.post("/api/pipeline/run", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert "processed" in data
        assert "contracts" in data

    def test_run_pipeline_with_action(self, client):
        resp = client.post("/api/pipeline/run", json={"action": "reject"})
        data = resp.get_json()
        assert data["status"] == "ok"
        for c in data["contracts"]:
            assert c["status"] == "decided"

    def test_run_pipeline_invalid_action(self, client):
        resp = client.post("/api/pipeline/run", json={"action": "bogus"})
        assert resp.status_code == 400

    def test_list_pending(self, client, tmp_archive):
        self._seed(tmp_archive)
        resp = client.get("/api/pipeline/pending")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 1
        assert data["pending"][0]["contract_id"] == "CIN-API-001"
        assert data["pending"][0]["title"] == "API Test Contract"

    def test_list_pending_empty(self, client):
        resp = client.get("/api/pipeline/pending")
        data = resp.get_json()
        assert data["count"] == 0

    def test_decide(self, client, tmp_archive):
        self._seed(tmp_archive)
        resp = client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001",
            "action": "approve_archive",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["action"] == "approve_archive"
        assert data["route"] == "ARCHIVE"
        assert pending.load("CIN-API-001") is None

    def test_decide_missing_fields(self, client):
        resp = client.post("/api/pipeline/decide", json={"contract_id": "CIN-X"})
        assert resp.status_code == 400

    def test_decide_invalid_action(self, client):
        resp = client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-X", "action": "bogus",
        })
        assert resp.status_code == 400

    def test_decide_not_found(self, client):
        resp = client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-NOPE", "action": "reject",
        })
        assert resp.status_code == 404

    def test_history_empty(self, client):
        resp = client.get("/api/pipeline/history")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["count"] == 0

    def test_history_after_decision(self, client, tmp_archive):
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "reject",
        })
        resp = client.get("/api/pipeline/history")
        data = resp.get_json()
        assert data["count"] >= 1

    def test_queue_empty(self, client):
        resp = client.get("/api/pipeline/queue/HUMAN_REVIEW")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["count"] == 0

    def test_queue_after_flag_review(self, client, tmp_archive):
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "flag_review",
        })
        resp = client.get("/api/pipeline/queue/HUMAN_REVIEW")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["records"][0]["route"] == "HUMAN_REVIEW"

    def test_archive_list_empty(self, client):
        resp = client.get("/api/pipeline/archive")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["count"] == 0

    def test_archive_list_after_decision(self, client, tmp_archive):
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "approve_archive",
        })
        resp = client.get("/api/pipeline/archive")
        data = resp.get_json()
        assert data["count"] >= 1

    def test_archive_detail(self, client, tmp_archive):
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "approve_archive",
        })
        contracts = client.get("/api/pipeline/archive").get_json()["contracts"]
        cid = contracts[0]["contract_id"]
        resp = client.get(f"/api/pipeline/archive/{cid}")
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["metadata"]["contract_id"] == cid
        assert data["summary"] is not None

    def test_archive_detail_not_found(self, client):
        resp = client.get("/api/pipeline/archive/CIN-NOPE")
        assert resp.status_code == 404

    def test_archive_detail_integrity_mismatch_returns_clean_500(self, client, tmp_archive):
        """A tampered artifact must surface as a clean JSON 500, matching
        the sibling /api/pipeline/archive list route -- not an unhandled
        crash."""
        import json as _json
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "approve_archive",
        })
        contracts = client.get("/api/pipeline/archive").get_json()["contracts"]
        cid = contracts[0]["contract_id"]
        (tmp_archive / "Processed" / f"{cid}.json").write_text(
            _json.dumps({"tampered": True}), encoding="utf-8"
        )

        resp = client.get(f"/api/pipeline/archive/{cid}")
        assert resp.status_code == 500
        assert "error" in resp.get_json()

    def test_archive_list_integrity_mismatch_returns_clean_500(self, client, tmp_archive):
        import json as _json
        self._seed(tmp_archive)
        client.post("/api/pipeline/decide", json={
            "contract_id": "CIN-API-001", "action": "approve_archive",
        })
        contracts = client.get("/api/pipeline/archive").get_json()["contracts"]
        cid = contracts[0]["contract_id"]
        (tmp_archive / "Processed" / f"{cid}.json").write_text(
            _json.dumps({"tampered": True}), encoding="utf-8"
        )

        resp = client.get("/api/pipeline/archive")
        assert resp.status_code == 500
        assert "error" in resp.get_json()


# --------------------------------------------------------------------------- pending page

class TestPendingPage:
    @pytest.fixture
    def app(self, tmp_archive, monkeypatch):
        monkeypatch.setattr(pending, "_PENDING_DIR", tmp_archive / "Pending")
        from portal.app import create_app
        app = create_app({"TESTING": True})
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _seed(self, tmp_archive, contract_id="CIN-PG-001"):
        pending.store(
            contract_id,
            {"title": "Page Test", "agency": "DOD",
             "solicitation_number": "SOL-P1"},
            {}, "Summary", {"action": "reject", "priority": "high",
             "recipient": "none", "reason": "r", "notes": "n"},
            ["flag_x"],
        )

    def test_pending_page_renders(self, client):
        resp = client.get("/pipeline")
        assert resp.status_code == 200
        assert b"Pipeline" in resp.data

    def test_pending_page_shows_contracts(self, client, tmp_archive):
        self._seed(tmp_archive)
        resp = client.get("/pipeline")
        assert resp.status_code == 200
        assert b"Page Test" in resp.data
        assert b"CIN-PG-001" in resp.data

    def test_pending_page_shows_actions(self, client, tmp_archive):
        self._seed(tmp_archive)
        resp = client.get("/pipeline")
        for _, (label, _) in control.ACTIONS.items():
            assert label.encode() in resp.data
