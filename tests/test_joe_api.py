"""The Dispatch API Joe works through. Phase 1 — the Dispatch Workstation.

    Dispatch is one of Joe's workstations.
    Joe may think broadly. Joe may act within delegated authority.
    Joe may never replace human command authority.

Joe's intelligence is rented. Nothing here is AI: these are the endpoints a
brain calls to read a mission, report a status, and -- after reading it back --
change one.

The tests that matter are the authority boundaries, because those are what a
delegated agent erodes if nothing holds them:

    Class 1  answered and reported
    Class 2  read back, then executed on confirmation
    Class 3  refused, with the staff work done

And the platform rule: Joe is an operational role. Microsoft is the first
certified brain and workstation stack, not the definition, so nothing in this
contract may name it.
"""

from __future__ import annotations

import pytest

from dispatch import audit, joe_authority as authority
from portal.models import sandbox


TOKEN = "test-token-not-a-real-secret"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DISPATCH_JOE_TOKEN", TOKEN)
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def mission():
    entry = sandbox.create_entry(
        source_type="dispatch", source_id="API-1", title="API probe",
        card_data={"load_id": "API-1"}, summary="")
    data = sandbox._load()
    data[entry["id"]].update({
        "load_number": "L1-APITEST",
        "committed_at": "2026-09-01T10:00:00Z",
        "pickup_location": "XPO Logistics, Savannah, GA",
        "pickup_window": "2026-09-08 06:00",
        "delivery_location": "Mayo Clinic, Jacksonville, FL",
    })
    sandbox._save(data)
    return entry["id"]


def _head(driver="Mike", channel="CHAT"):
    return {"Authorization": "Bearer " + TOKEN,
            "X-Driver": driver, "X-Channel": channel}


class TestEveryActionCarriesSomebodysAuthority:
    """The one hard wall: Mike remains commander."""

    def test_an_unauthenticated_call_is_refused(self, client):
        assert client.get("/api/joe/mission-status").status_code == 401

    def test_a_wrong_token_is_refused(self, client):
        response = client.get("/api/joe/mission-status",
                              headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401

    def test_a_call_with_no_driver_is_refused(self, client):
        response = client.get("/api/joe/mission-status",
                              headers={"Authorization": "Bearer " + TOKEN})
        assert response.status_code == 400
        assert "authority" in response.get_json()["note"]

    def test_an_unconfigured_node_accepts_nothing(self, client, monkeypatch):
        """An unauthenticated write path into the Mission Record is worse than
        no API at all."""
        monkeypatch.delenv("DISPATCH_JOE_TOKEN", raising=False)
        response = client.get("/api/joe/mission-status", headers=_head())
        assert response.status_code == 503


class TestClassOneAnswersAndReports:
    def test_mission_status_reads_the_committed_mission(self, client, mission):
        body = client.get("/api/joe/mission-status",
                          headers=_head()).get_json()
        assert body["ok"] is True
        assert body["mission"]["load_number"] == "L1-APITEST"
        assert body["mission"]["state"] == "COMMITTED"

    def test_a_mission_can_be_asked_for_by_load_number(self, client, mission):
        """It is the retrieval key the system is built on, and what he says
        out loud."""
        body = client.get("/api/joe/mission-status?mission=L1-APITEST",
                          headers=_head()).get_json()
        assert body["mission"]["load_number"] == "L1-APITEST"

    def test_driver_status_holds_the_locked_vocabulary(self, client, mission):
        for status in authority.STATUS_VOCABULARY:
            response = client.post("/api/joe/driver-status", headers=_head(),
                                   json={"status": status})
            assert response.status_code == 200

    def test_a_status_outside_the_vocabulary_is_refused(self, client, mission):
        """A status that means whatever the sender felt like is not a status."""
        response = client.post("/api/joe/driver-status", headers=_head(),
                               json={"status": "RUNNING A BIT BEHIND"})
        assert response.status_code == 400

    def test_facility_intel_reports_only_what_is_known(self, client, mission):
        body = client.get("/api/joe/facility-intel/Savannah",
                          headers=_head()).get_json()
        assert body["known"][0]["facility"] == "XPO Logistics, Savannah, GA"

    def test_an_unknown_facility_says_so_rather_than_inventing(self, client,
                                                               mission):
        body = client.get("/api/joe/facility-intel/Nowhere",
                          headers=_head()).get_json()
        assert body["known"] == []
        assert "Nothing on record" in body["note"]

    def test_schedule_fit_reports_the_board_and_decides_nothing(self, client,
                                                                mission):
        body = client.get("/api/joe/schedule-fit", headers=_head()).get_json()
        assert "unsold_days" in body and "depth" in body
        assert "recommendation" not in body
        assert "should" not in str(body).lower()


class TestClassTwoReadsBackFirst:
    """Not politeness. A phone number heard wrongly and written silently is a
    corrupted record nobody knows is corrupted."""

    def test_an_unconfirmed_change_changes_nothing(self, client, mission):
        body = client.patch("/api/joe/mission-record/L1-APITEST",
                            headers=_head(),
                            json={"field": "customer_phone",
                                  "value": "904-555-0199"}).get_json()
        assert body["applied"] is False
        assert body["needs_confirmation"] is True
        assert not sandbox.get(mission).get("customer_phone")

    def test_the_read_back_states_the_material_effect(self, client, mission):
        body = client.patch("/api/joe/mission-record/L1-APITEST",
                            headers=_head(),
                            json={"field": "customer_phone",
                                  "value": "904-555-0199"}).get_json()
        assert "904-555-0199" in body["read_back"]
        assert "Confirm?" in body["read_back"]

    def test_a_confirmed_change_is_applied(self, client, mission):
        client.patch("/api/joe/mission-record/L1-APITEST", headers=_head(),
                     json={"field": "customer_phone", "value": "904-555-0199",
                           "confirmed": True})
        assert sandbox.get(mission)["customer_phone"] == "904-555-0199"

    def test_it_returns_old_and_new_for_the_audit_log(self, client, mission):
        client.patch("/api/joe/mission-record/L1-APITEST", headers=_head(),
                     json={"field": "rate", "value": "950", "confirmed": True})
        body = client.patch("/api/joe/mission-record/L1-APITEST",
                            headers=_head(),
                            json={"field": "rate", "value": "1050",
                                  "confirmed": True}).get_json()
        assert body["old_value"] == "950"
        assert body["new_value"] == "1050"

    def test_a_spoken_sentence_works_too(self, client, mission):
        body = client.patch("/api/joe/mission-record/L1-APITEST",
                            headers=_head(),
                            json={"said": "broker email is sally@xpo.example",
                                  "confirmed": True}).get_json()
        assert body["applied"] is True
        assert sandbox.get(mission)["customer_email"] == "sally@xpo.example"

    def test_send_notice_sends_nothing_unconfirmed(self, client, mission):
        body = client.post("/api/joe/send-notice", headers=_head(),
                           json={"mission": "L1-APITEST", "to": "a@b.test",
                                 "subject": "S", "message": "M"}).get_json()
        assert body["sent"] is False
        assert body["needs_confirmation"] is True

    def test_a_failed_send_reports_failure_not_silence(self, client, mission):
        """No false success. No silent failure."""
        response = client.post("/api/joe/send-notice", headers=_head(),
                               json={"mission": "L1-APITEST", "to": "a@b.test",
                                     "subject": "S", "message": "M",
                                     "confirmed": True})
        body = response.get_json()
        assert body["sent"] is False
        assert "NOT SENT" in body["report"]
        assert "NOTHING WAS CHANGED" in body["report"]


class TestClassThreeIsReservedByAbsence:
    """There is no commit endpoint, and that is the enforcement.

    An earlier version had one returning 403, on the argument that a caller
    asking to commit should get a clear refusal rather than a 404 that looks
    like a bug. Doctrine specifies six Phase 1 endpoints, and a door with a
    lock is still a door where doctrine says there should be none. A provider's
    convenience is not a reason to widen the contract.
    """

    def test_there_is_no_commit_endpoint(self, client, mission):
        assert client.post("/api/joe/commit/L1-APITEST",
                           headers=_head()).status_code == 404

    def test_the_authority_model_still_classifies_it(self):
        """Nothing routed through the authority model can run one."""
        assert authority.is_reserved("commit-load") is True
        assert authority.class_of("commit-load") == authority.CLASS_HOLD

    def test_an_unclassified_action_is_held_not_run(self):
        """An action nobody classified is an action nobody thought about."""
        assert authority.class_of("do-something-clever") == authority.CLASS_HOLD

    def test_the_hold_answer_does_the_staff_work_first(self):
        """Limits on authority do not limit awareness or recommendation."""
        held = authority.held("commit-load", "the brief shows what is open")
        assert held["held"] is True
        assert held["reasoning"]


class TestTheAuditLog:
    def test_every_action_is_attributed(self, client, mission):
        client.get("/api/joe/mission-status", headers=_head(driver="Mike"))
        entries = audit.entries()
        assert entries[-1]["driver"] == "Mike"
        assert entries[-1]["action"] == "mission-status"

    def test_a_change_records_old_and_new(self, client, mission):
        client.patch("/api/joe/mission-record/L1-APITEST", headers=_head(),
                     json={"field": "rate", "value": "950", "confirmed": True})
        entry = [e for e in audit.entries()
                 if e["action"] == "mission-record-update"][-1]
        assert entry["old_value"] == "" and entry["new_value"] == "950"
        assert entry["result"] == audit.RESULT_SUCCESS

    def test_a_read_back_is_logged_as_partial(self, client, mission):
        """It happened, and it did not finish. Both are true."""
        client.patch("/api/joe/mission-record/L1-APITEST", headers=_head(),
                     json={"field": "rate", "value": "950"})
        entry = audit.entries()[-1]
        assert entry["result"] == audit.RESULT_PARTIAL

    def test_the_channel_is_recorded_not_inferred(self, client, mission):
        client.get("/api/joe/mission-status", headers=_head(channel="CHAT"))
        assert audit.entries()[-1]["channel"] == "CHAT"

    def test_a_channel_nobody_anticipated_is_still_recorded(self, client,
                                                            mission):
        """Any string a caller sends is stored, so a new channel is never a
        schema change and never a code branch."""
        client.get("/api/joe/mission-status", headers=_head(channel="SATPHONE"))
        assert audit.entries()[-1]["channel"] == "SATPHONE"

    def test_it_is_append_only(self, client, mission):
        client.get("/api/joe/mission-status", headers=_head())
        first = len(audit.entries())
        client.get("/api/joe/mission-status", headers=_head())
        assert len(audit.entries()) == first + 1
        source = open("dispatch/audit.py", encoding="utf-8").read()
        assert '"a"' in source, "the log must be opened for append"
        assert "def delete" not in source and "def edit" not in source


class TestJoeIsARoleNotAMicrosoftFeature:
    """The operator's ruling: build Joe as a platform-agnostic operational role
    with Microsoft as the first certified brain and workstation stack, not as a
    Microsoft feature."""

    @pytest.mark.parametrize("path", [
        "portal/routes/joe_api.py",
        "dispatch/joe_authority.py",
        "dispatch/audit.py",
    ])
    def test_the_contract_names_no_vendor(self, path):
        source = open(path, encoding="utf-8").read()
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        # Prose may explain the first certified stack; the contract may not
        # depend on it. No endpoint, parameter or field names a vendor.
        for vendor in ("copilot", "graph.microsoft", "m365", "msal"):
            assert vendor not in code.lower(), "%s names %s" % (path, vendor)

    def test_identity_is_a_token_and_a_name_any_caller_can_present(self):
        source = open("portal/routes/joe_api.py", encoding="utf-8").read()
        assert "bearer" in source.lower()
        assert "X-Driver" in source

    def test_the_channel_is_data_rather_than_a_code_path(self):
        """Adding a channel is a new constant, never a new branch."""
        source = open("dispatch/audit.py", encoding="utf-8").read()
        assert "CHANNEL_CHAT" in source
        assert "if channel ==" not in source


class TestTheAdapterFollowsTheContract:
    """Contracts first, adapters second -- and the adapter must not drift.

    `adapters/joe_connector.yaml` is one way of reaching the contract, from one
    stack, certified first. Being first does not make it the definition, so it
    is checked *against* the routes rather than the routes being built to suit
    it.
    """

    def _spec(self):
        yaml = pytest.importorskip("yaml")
        with open("adapters/joe_connector.yaml", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def _live_paths(self):
        from portal.app import create_app

        app = create_app()
        return {str(r.rule) for r in app.url_map.iter_rules()
                if "/api/joe" in str(r.rule)}

    @staticmethod
    def _normalise(path):
        return (path.replace("{missionId}", "<path:mission_id>")
                    .replace("{facilityId}", "<path:facility_id>"))

    def test_it_describes_every_endpoint_and_no_others(self):
        described = {self._normalise(p) for p in self._spec()["paths"]}
        assert described == self._live_paths()

    def test_the_vendor_name_is_allowed_here_and_only_here(self):
        """The adapter is where a stack may be named. The contract is not."""
        readme = open("adapters/README.md", encoding="utf-8").read()
        assert "vendor" in readme.lower()
        contract = open("portal/routes/joe_api.py", encoding="utf-8").read()
        assert "adapter" in contract.lower(), (
            "the contract should say the connector is one adapter to it")

    def test_the_locked_status_vocabulary_is_carried_across(self):
        status = self._spec()["paths"]["/api/joe/driver-status"]["post"]
        schema = status["requestBody"]["content"]["application/json"]["schema"]
        assert schema["properties"]["status"]["enum"] == list(
            authority.STATUS_VOCABULARY)

    def test_class_two_endpoints_document_the_confirmation(self):
        spec = self._spec()
        for path in ("/api/joe/mission-record/{missionId}",
                     "/api/joe/send-notice"):
            operation = spec["paths"][path]
            body = list(operation.values())[0]["requestBody"]
            schema = body["content"]["application/json"]["schema"]
            assert "confirmed" in schema["properties"], path

    def test_it_describes_no_operation_the_contract_does_not_have(self):
        """The adapter followed the contract when two endpoints were removed.
        An adapter describing an operation that does not exist is a connector
        that fails at the moment it is used."""
        described = set(self._spec()["paths"])
        assert not any("commit" in p for p in described)
        assert not any("audit" in p for p in described)

    def test_it_says_why_class_three_is_absent(self):
        """So that whoever builds the connector knows it is reserved rather
        than forgotten."""
        text = open("adapters/joe_connector.yaml", encoding="utf-8").read().lower()
        assert "reserved to human command" in text
        assert "no commit operation" in text
