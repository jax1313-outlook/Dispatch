"""The connected operating path, end to end, in one test.

The campaign's cross-workstream requirement: the workstreams must not become
separate islands. Each of the pieces below is proven in its own file; this
file exists to prove they are joined, in the order Dispatch actually runs, and
that the security and durability controls protect the real path rather than a
diagram of it.

    Opportunity discovered
      -> analysed, with Dynamic Capacity and Truck Arrangement consulted
      -> presented for a human decision
      -> human decision recorded
      -> Spine validates and applies the transition
      -> Current Reality created by Spine, never by Opportunity
      -> driver receives the mission
      -> driver reports a milestone and uploads evidence, with CSRF enforced
      -> stakeholder visibility stays controlled and revocable
      -> everything created above is backed up and restored
"""

from __future__ import annotations

import io
import os

import pytest

from dispatch import backup, notifications, services
from dispatch import store as dispatch_store
from dispatch.capacity import DynamicCapacity
from dispatch.db import set_db_path
from dispatch.opportunities import OpportunityPipeline
from dispatch.spine.store import list_approval_events, list_events
from dispatch.truck_arrangement import TruckArrangement
from portal.app import create_app
from portal.models import driver_pin_registry as pin_registry


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    set_db_path(tmp_path / "e2e.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    yield
    set_db_path(None)


@pytest.fixture()
def app():
    return create_app({"TESTING": True})


def _csrf(client) -> str:
    cookie = client.get_cookie("csrf_token")
    return cookie.value if cookie else ""


class TestTheConnectedPath:
    def test_opportunity_to_driver_to_stakeholder_to_backup(self, app, tmp_path):
        pipeline = OpportunityPipeline()

        # 1. DISCOVERED -------------------------------------------------------
        card = pipeline.ingest_opportunities([{
            "source": "intelligence",
            "origin_location": "Jacksonville, FL",
            "destination_location": "Atlanta, GA",
            "offered_rate": 2400.0,
            "estimated_miles": 350.0,
            "weight_lbs": 18000.0,
            "pallets": 12,
            "equipment_type": "dry_van",
        }])[0]
        assert card.stage == "CREATED"

        # 2. ANALYSED, with capacity and arrangement consulted ----------------
        capacity = DynamicCapacity()
        capacity.physical.max_weight_lbs = 44000.0
        capacity.physical.max_pallets = 26
        arrangement = TruckArrangement(load_id="", pallet_count=12, total_weight_lbs=18000.0)

        pipeline.analyze_opportunity(
            card.opportunity_id, capacity=capacity, arrangement=arrangement
        )
        pipeline.score_opportunity(card.opportunity_id)
        assert card.stage == "SCORED"
        assert card.weight_consumption_pct > 0      # capacity was actually consulted
        assert card.score_reasons                    # scoring produced a rationale

        # 3. PRESENTED for a decision ----------------------------------------
        shortlist = pipeline.present(min_score=0.0)
        assert card.opportunity_id in [c.opportunity_id for c in shortlist]
        assert card.stage == "WAITING_FOR_MIKE"

        # 4. HUMAN DECISION, recorded with the actor -------------------------
        pipeline.request_commitment(card.opportunity_id, "mike")
        approvals = list_approval_events(card.work_item_id)
        assert approvals and approvals[0]["user_id"] == "mike"
        assert card.stage == "MIKE_APPROVED"

        # 5. SPINE validated every step -- the audit trail is the proof -------
        states = [e["new_state"] for e in list_events(card.work_item_id)]
        assert states[:2] == ["VALIDATION_PENDING", "VALIDATED"]
        assert "MIKE_APPROVED" in states

        # 6. CURRENT REALITY, created by Spine -------------------------------
        load = pipeline.realize_commitment(card.opportunity_id, actor_id="mike")
        assert card.linked_load_id == load["load_id"]
        assert services.get_rate_confirmation(load["load_id"])["confirmed_by"] == "mike"

        # 7. DRIVER RECEIVES THE MISSION -------------------------------------
        driver = services.create_driver(name="Mike Zachary", phone="904-555-0199")
        pin_registry.create_pin_card(driver["driver_id"], "1234", "anchor", "mike")
        services.assign_driver(load["load_id"], driver["driver_id"])
        services.add_milestone(load["load_id"], event_type="dispatched")

        client = app.test_client()
        client.post("/driver/login", data={"phone": driver["phone"], "pin": "1234"}, csrf=False)
        home = client.get("/driver/home").data.decode("utf-8")
        assert "Jacksonville, FL" in home and "Atlanta, GA" in home

        # 8. DRIVER REPORTS -- and CSRF protects the report -------------------
        forged = client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "en_route_pickup"}, csrf=False,
        )
        assert forged.status_code == 403
        assert services.get_load(load["load_id"])["status"] == "dispatched"

        client.post(
            f"/driver/loads/{load['load_id']}/milestone",
            data={"milestone_event": "en_route_pickup", "csrf_token": _csrf(client)},
            csrf=False, follow_redirects=True,
        )
        assert services.get_load(load["load_id"])["status"] == "en_route_pickup"

        client.post(
            f"/driver/loads/{load['load_id']}/pod",
            data={"pod_file": (io.BytesIO(b"signed pod bytes"), "pod.jpg"),
                  "csrf_token": _csrf(client)},
            content_type="multipart/form-data", csrf=False, follow_redirects=True,
        )
        evidence = services.list_evidence(load["load_id"])
        assert len(evidence) == 1 and evidence[0]["checksum"]

        # 9. STAKEHOLDER VISIBILITY, controlled and revocable -----------------
        token = notifications.make_stakeholder_token(load["load_id"], issued_by="mike")
        viewer = app.test_client()
        assert viewer.get(f"/portal/loads/{load['load_id']}?token={token}").status_code == 200

        notifications.revoke_stakeholder_access(load["load_id"], reason="done", actor="mike")
        assert viewer.get(f"/portal/loads/{load['load_id']}?token={token}").status_code == 403

        # 10. BACKED UP AND RESTORABLE ---------------------------------------
        # Not "a backup ran" -- the load, the milestone the driver reported and
        # the POD he photographed all have to come back out of it.
        result = backup.create_backup(tmp_path / "backup")
        assert backup.verify(result.archive_path).ok

        restored = backup.restore(result.archive_path, tmp_path / "restored")
        assert restored.database_path is not None

        set_db_path(restored.database_path)
        for name, value in restored.env.items():
            os.environ[name] = value
        try:
            recovered = services.get_load(load["load_id"])
            assert recovered is not None
            assert recovered["status"] == "en_route_pickup"
            assert recovered["pickup_location"] == "Jacksonville, FL"

            milestones = [m["event_type"] for m in dispatch_store.list_milestones(load["load_id"])]
            assert "en_route_pickup" in milestones

            recovered_evidence = services.list_evidence(load["load_id"])
            assert len(recovered_evidence) == 1
            path, _name = services.get_evidence_file(recovered_evidence[0]["evidence_id"])
            assert path.read_bytes() == b"signed pod bytes"
        finally:
            set_db_path(tmp_path / "e2e.db")

    def test_opportunity_cannot_shortcut_the_path(self, app):
        """The whole chain exists to make a human decision unavoidable. An
        opportunity that skips the decision must not reach Current Reality."""
        from dispatch.spine.commitment import CommitmentNotAuthorized

        pipeline = OpportunityPipeline()
        card = pipeline.ingest_opportunities([{
            "source": "intelligence", "origin_location": "A",
            "destination_location": "B", "offered_rate": 1000.0,
            "estimated_miles": 100.0,
        }])[0]
        pipeline.analyze_opportunity(card.opportunity_id)
        pipeline.score_opportunity(card.opportunity_id)

        before = len(services.list_loads())
        with pytest.raises(CommitmentNotAuthorized):
            pipeline.realize_commitment(card.opportunity_id, actor_id="mike")
        assert len(services.list_loads()) == before
        assert card.linked_load_id == ""
