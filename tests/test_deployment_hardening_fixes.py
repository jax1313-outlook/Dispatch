"""Tests for the freight-core defect fixes made during the deployment-
matrix hardening pass. One test class per finding, matching the numbering
in the defect-sweep report (findings #1-#11; #8 and #12 were documented,
not fixed -- see the deployment decision register).
"""

from __future__ import annotations

import json

import pytest

from dispatch import acquisition, services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_load(**kw):
    kw.setdefault("customer", "Acme Freight")
    return services.create_load(**kw)


# -- #1: debug must default off ---------------------------------------


class TestDebugDefaultsOff:
    def test_debug_disabled_when_env_unset(self, monkeypatch):
        from portal.app import _debug_enabled
        monkeypatch.delenv("PORTAL_DEBUG", raising=False)
        assert _debug_enabled() is False

    def test_debug_enabled_only_with_explicit_opt_in(self, monkeypatch):
        from portal.app import _debug_enabled
        monkeypatch.setenv("PORTAL_DEBUG", "1")
        assert _debug_enabled() is True
        monkeypatch.setenv("PORTAL_DEBUG", "0")
        assert _debug_enabled() is False


# -- #2: freight decision-email endpoint must survive the real login gate --


class TestDecisionEndpointSurvivesRealLoginGate:
    @pytest.fixture
    def auth_data_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "auth_portal_data"))
        return tmp_path / "auth_portal_data"

    @pytest.fixture
    def auth_app(self, auth_data_dir):
        from portal.app import create_app
        return create_app({"TESTING": True, "SECRET_KEY": "test", "LOGIN_DISABLED": False})

    @pytest.fixture
    def auth_client(self, auth_app):
        return auth_app.test_client()

    def test_other_dispatch_api_routes_still_gated(self, auth_client):
        resp = auth_client.get("/api/dispatch/loads")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_decision_endpoint_reachable_without_a_session(self, auth_app, auth_client):
        from dispatch import notifications
        with auth_app.app_context():
            load = _make_load()
        token = notifications.make_token(load["load_id"], "acknowledge")

        resp = auth_client.get(f"/api/dispatch/decision/{load['load_id']}/acknowledge?token={token}")

        assert resp.status_code == 200
        assert "/login" not in resp.headers.get("Location", "")


# -- #3: PATCH endpoints must not crash when the body echoes the record id --


class TestIdEchoDoesNotCrash:
    def test_update_load_survives_load_id_in_body(self, client):
        load = _make_load()
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            json={"load_id": "some-other-id", "status": "dispatched"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["load"]["status"] == "dispatched"

    def test_update_driver_survives_driver_id_in_body(self, client):
        driver = services.create_driver(name="Test Driver")
        resp = client.patch(
            f"/api/dispatch/drivers/{driver['driver_id']}",
            json={"driver_id": "some-other-id", "phone": "555-0100"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["driver"]["phone"] == "555-0100"


# -- #4: write endpoints must not 500 on a valid-JSON-but-non-dict body ----


class TestNonDictJsonBodyDoesNotCrash:
    def test_update_load_with_list_body_returns_clean_response_not_500(self, client):
        load = _make_load()
        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}",
            data=json.dumps([1, 2, 3]),
            content_type="application/json",
        )
        assert resp.status_code != 500

    def test_batch_status_update_with_string_body_returns_400_not_500(self, client):
        resp = client.post(
            "/api/dispatch/loads/batch-status",
            data=json.dumps("just a string"),
            content_type="application/json",
        )
        assert resp.status_code != 500
        assert resp.status_code == 400


# NOTE on finding #5 (milestones/archive bypassing validate_status_transition):
# an initial fix here was reverted. It assumed milestone-triggered status
# cascades should follow _VALID_TRANSITIONS' strict linear adjacency the same
# way update_load()'s explicit status-setting API does -- but existing,
# passing tests (test_financials.py::test_archive_with_financials) prove
# milestones are meant to skip ahead (e.g. dispatched -> delivered directly,
# without every intermediate step), which is realistic: a driver's report
# doesn't always cover every checkpoint. The full test suite caught this
# before it shipped. See DISPATCH_DEPLOYMENT_BLUEPRINT.md's decision register
# -- this needs more careful, test-verified design (distinguishing legitimate
# skip-ahead from reviving a genuinely terminal state like cancelled/archived)
# before it's safe to touch again, not a second guess under this pass.


# -- #6: a notify failure must not turn a completed write into a 500 -------


class TestNotifyFailureDoesNotFailTheOperation:
    def test_archive_load_succeeds_even_if_notify_raises(self, client, monkeypatch):
        from dispatch import notifications
        load = _make_load()
        services.update_load(load["load_id"], status="dispatched")
        services.update_load(load["load_id"], status="en_route_pickup")
        services.update_load(load["load_id"], status="at_pickup")
        services.update_load(load["load_id"], status="picked_up")
        services.update_load(load["load_id"], status="in_transit")
        services.update_load(load["load_id"], status="at_delivery")
        services.update_load(load["load_id"], status="delivered")

        def _boom(*a, **kw):
            raise RuntimeError("SMTP connection timed out")

        monkeypatch.setattr(notifications, "notify_archived", _boom)

        result = services.archive_load(load["load_id"])  # must not raise
        assert result is not None

        from dispatch import store
        assert store.get_load(load["load_id"])["status"] == "archived"


# -- #7: one bad file must not abort the whole acquisition batch -----------


class TestAcquisitionSkipsBadFilesInsteadOfAborting:
    def test_malformed_file_is_skipped_good_files_still_load(self, tmp_path):
        good1 = {"load_id": "L1", "origin": "A", "destination": "B"}
        good2 = {"load_id": "L2", "origin": "C", "destination": "D"}
        (tmp_path / "a_good.json").write_text(json.dumps(good1))
        (tmp_path / "b_bad.json").write_text("{not valid json,,,")
        (tmp_path / "c_wrong_shape.json").write_text(json.dumps([1, 2, 3]))
        (tmp_path / "d_good.json").write_text(json.dumps(good2))

        loads = acquisition._acquire_local(tmp_path)

        ids = {l["load_id"] for l in loads}
        assert ids == {"L1", "L2"}


# -- #9: a malformed detention ended_at must be rejected, not swallowed ----


class TestDetentionEndedAtValidation:
    def test_malformed_ended_at_returns_400(self, client):
        load = _make_load()
        det = services.start_detention(
            load_id=load["load_id"], location_type="pickup",
        )
        resp = client.post(
            f"/api/dispatch/detentions/{det['detention_id']}/stop",
            json={"ended_at": "not-a-real-timestamp"},
        )
        assert resp.status_code == 400

    def test_empty_ended_at_still_defaults_to_now(self, client):
        load = _make_load()
        det = services.start_detention(
            load_id=load["load_id"], location_type="pickup",
        )
        resp = client.post(f"/api/dispatch/detentions/{det['detention_id']}/stop", json={})
        assert resp.status_code == 200


# -- #10: revenue aggregation must agree across reporting paths ------------


class TestRevenueRoundingConsistency:
    def test_dashboard_and_profitability_totals_agree(self, client):
        # Rates chosen to reproduce the documented sum-then-round vs
        # round-then-sum discrepancy ($3388.198 + $1924.505 -> differs by
        # $0.01 depending on rounding order) if the two paths ever diverge
        # again.
        for rate in (3388.198, 1924.505):
            load = _make_load()
            services.confirm_rate(load["load_id"], rate_type="flat", rate_amount=rate)

        dashboard = services.get_financial_dashboard()
        profitability = services.get_load_profitability()

        assert dashboard["total_revenue"] == profitability["summary"]["total_revenue"]


# -- #11: fuel-estimate must not 500 on a non-numeric query param ----------


class TestFuelEstimateQueryParamValidation:
    def test_non_numeric_distance_returns_400_not_500(self, client):
        resp = client.get("/api/dispatch/fuel-estimate?distance_miles=abc")
        assert resp.status_code == 400

    def test_valid_numeric_params_still_work(self, client):
        resp = client.get("/api/dispatch/fuel-estimate?distance_miles=500&mpg=6.5&fuel_price=3.80")
        assert resp.status_code == 200
