"""Tests for Lane C: Stakeholder Portal API Contract.

Covers three additions to the external, non-PIN-gated stakeholder portal
(portal/routes/stakeholder.py):

  1. The token-scoped evidence download route (the security-sensitive
     part) -- GET /portal/loads/<load_id>/evidence/<evidence_id>?token=...
     Most important test in this file: a valid token for load A must not
     be able to download evidence that actually belongs to load B (IDOR).
  2. The `?format=json` contract variant of the existing stakeholder_view
     route.
  3. The "Include Stakeholder Portal Link" opt-in checkbox on the Email
     Helper draft, implemented as a server-side `include_stakeholder_link`
     body param on the existing PATCH /email-package endpoint.

Follows tests/test_stakeholder_portal.py's exact test-isolation pattern
(set_db_path, PORTAL_UPLOAD_DIR for real files, the `_url()` helper).
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _url(load_id: str, token: str | None = None) -> str:
    token = notifications.make_stakeholder_token(load_id) if token is None else token
    return f"/portal/loads/{load_id}?token={token}"


def _evidence_url(load_id: str, evidence_id: str, token: str | None = None) -> str:
    token = notifications.make_stakeholder_token(load_id) if token is None else token
    return f"/portal/loads/{load_id}/evidence/{evidence_id}?token={token}"


# ── Token-scoped evidence download ──────────────────────────────────────


class TestStakeholderEvidenceDownload:
    def test_valid_token_and_matching_evidence_downloads_file(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = services.create_load(customer="Evidence DL Co")
        ev = services.attach_evidence(
            load["load_id"],
            evidence_type="pod",
            description="Signed POD",
            file_data=b"hello world pod bytes",
            original_filename="pod.jpg",
        )
        resp = client.get(_evidence_url(load["load_id"], ev["evidence_id"]))
        assert resp.status_code == 200
        assert resp.data == b"hello world pod bytes"
        assert "pod.jpg" in resp.headers.get("Content-Disposition", "")

    def test_evidence_belonging_to_a_different_load_is_404_not_leaked(self, client, monkeypatch, tmp_path):
        """THE MOST IMPORTANT TEST IN THIS FILE (IDOR).

        A valid stakeholder token for load A must never be usable to pull
        evidence that actually belongs to a different load B, even though
        the evidence_id itself is real and has a real file on disk.
        """
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load_a = services.create_load(customer="Load A Co")
        load_b = services.create_load(customer="Load B Co")

        ev_b = services.attach_evidence(
            load_b["load_id"],
            evidence_type="pod",
            description="Load B's own POD",
            file_data=b"this belongs to load b only",
            original_filename="secret-b.jpg",
        )

        # A valid token, but for load A -- while ev_b belongs to load B.
        resp = client.get(_evidence_url(load_a["load_id"], ev_b["evidence_id"]))
        assert resp.status_code == 404
        assert b"this belongs to load b only" not in resp.data

    def test_invalid_token_is_403(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = services.create_load(customer="Bad Token Co")
        ev = services.attach_evidence(
            load["load_id"], evidence_type="pod", file_data=b"data",
            original_filename="pod.jpg",
        )
        resp = client.get(_evidence_url(load["load_id"], ev["evidence_id"], token="not-the-real-token"))
        assert resp.status_code == 403

    def test_missing_token_is_403(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = services.create_load(customer="Missing Token Co")
        ev = services.attach_evidence(
            load["load_id"], evidence_type="pod", file_data=b"data",
            original_filename="pod.jpg",
        )
        resp = client.get(f"/portal/loads/{load['load_id']}/evidence/{ev['evidence_id']}")
        assert resp.status_code == 403

    def test_unknown_evidence_id_is_404(self, client):
        load = services.create_load(customer="Unknown Evidence Co")
        resp = client.get(_evidence_url(load["load_id"], "EV-DOES-NOT-EXIST"))
        assert resp.status_code == 404

    def test_metadata_only_evidence_with_no_file_is_404_not_crash(self, client):
        """attach_evidence() with no file_data/file_path -- a real, valid evidence
        record, but nothing to serve. Must 404 cleanly, never 500."""
        load = services.create_load(customer="Metadata Only Co")
        ev = services.attach_evidence(
            load["load_id"], evidence_type="photo", description="Described but never uploaded",
        )
        resp = client.get(_evidence_url(load["load_id"], ev["evidence_id"]))
        assert resp.status_code == 404


# ── ?format=json contract variant ───────────────────────────────────────


class TestStakeholderViewJsonContract:
    def test_json_format_returns_same_fields_as_html_view(self, client):
        load = services.create_load(
            customer="JSON Contract Co",
            broker_shipper="Some Brokerage",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
        )
        resp = client.get(_url(load["load_id"]) + "&format=json")
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/json")
        data = resp.get_json()

        expected = services.build_stakeholder_view(load["load_id"])
        assert data == expected
        assert data["load"]["customer"] == "JSON Contract Co"
        assert data["load"]["broker_shipper"] == "Some Brokerage"

    def test_invalid_token_with_json_format_returns_json_403(self, client):
        load = services.create_load(customer="JSON 403 Co")
        resp = client.get(_url(load["load_id"], token="bad-token") + "&format=json")
        assert resp.status_code == 403
        assert resp.content_type.startswith("application/json")
        assert resp.get_json()["error"]

    def test_nonexistent_load_with_json_format_returns_json_404(self, client):
        resp = client.get(_url("LOAD-DOES-NOT-EXIST") + "&format=json")
        assert resp.status_code == 404
        assert resp.content_type.startswith("application/json")
        assert resp.get_json()["error"]

    def test_default_no_format_param_still_renders_html(self, client):
        load = services.create_load(customer="Default HTML Co")
        resp = client.get(_url(load["load_id"]))
        assert resp.content_type.startswith("text/html")

    def test_unrecognized_format_value_still_renders_html(self, client):
        load = services.create_load(customer="Weird Format Co")
        resp = client.get(_url(load["load_id"]) + "&format=xml")
        assert resp.content_type.startswith("text/html")


# ── Email Helper: opt-in Stakeholder Portal Link inclusion ─────────────


def _token_in(body: str) -> str:
    """Pull the ?token=... value out of a rendered stakeholder link."""
    import re
    match = re.search(r"[?&]token=([^\s&]+)", body)
    assert match, f"no stakeholder token found in: {body!r}"
    return match.group(1)


class TestEmailHelperStakeholderLinkInclusion:
    """Implemented server-side: the PATCH /email-package endpoint accepts an
    optional `include_stakeholder_link` bool and appends the link to whichever
    of broker_body/customer_body are present in that request. The frontend
    checkbox in dispatch_detail.html just sets that flag on save -- see
    portal/routes/dispatch_api.py::update_email_package().
    """

    def _delivered_load_with_client(self, client, **overrides):
        payload = {"customer": "Link Include Co"}
        payload.update(overrides)
        r = client.post("/api/dispatch/loads", json=payload)
        load = r.get_json()["load"]
        for status in (
            "dispatched", "en_route_pickup", "at_pickup", "picked_up",
            "in_transit", "at_delivery", "delivered",
        ):
            client.patch(f"/api/dispatch/loads/{load['load_id']}", json={"status": status})
        return load

    def _draft(self, client, load_id):
        client.post(f"/api/dispatch/loads/{load_id}/end-load")
        r = client.post(f"/api/dispatch/loads/{load_id}/email-package/draft")
        assert r.status_code == 201
        return r.get_json()["package"]

    def test_checkbox_flag_appends_stakeholder_link_to_both_bodies(self, client):
        load = self._delivered_load_with_client(client)
        self._draft(client, load["load_id"])

        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={
                "broker_body": "Broker body text.",
                "customer_body": "Customer body text.",
                "include_stakeholder_link": True,
            },
        )
        assert resp.status_code == 200
        package = resp.get_json()["package"]
        assert f"/portal/loads/{load['load_id']}" in package["broker_body"]
        # Tokens carry a nonce and an expiry now, so a second call produces a
        # different string and comparing against a separately-minted token
        # proves nothing. Assert the stronger property instead: the token that
        # actually landed in the email verifies for this load.
        embedded = _token_in(package["broker_body"])
        assert notifications.verify_stakeholder_token(load["load_id"], embedded)
        assert f"/portal/loads/{load['load_id']}" in package["customer_body"]
        assert "Broker body text." in package["broker_body"]
        assert "Customer body text." in package["customer_body"]

    def test_unchecked_leaves_existing_behavior_unchanged(self, client):
        load = self._delivered_load_with_client(client)
        self._draft(client, load["load_id"])

        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_body": "Broker body text, unmodified."},
        )
        assert resp.status_code == 200
        package = resp.get_json()["package"]
        assert package["broker_body"] == "Broker body text, unmodified."
        assert "/portal/loads/" not in package["broker_body"]

    def test_omitting_flag_entirely_matches_pre_existing_behavior(self, client):
        """No `include_stakeholder_link` key at all -- exactly what every
        pre-existing caller of this endpoint (incl. test_email_helper.py) sends."""
        load = self._delivered_load_with_client(client)
        self._draft(client, load["load_id"])

        resp = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_email": "edited-broker@test.com"},
        )
        assert resp.status_code == 200
        package = resp.get_json()["package"]
        assert package["broker_email"] == "edited-broker@test.com"
        assert "/portal/loads/" not in package["broker_body"]

    def test_re_saving_with_flag_still_set_does_not_duplicate_link(self, client):
        load = self._delivered_load_with_client(client)
        self._draft(client, load["load_id"])

        client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={"broker_body": "Broker body text.", "include_stakeholder_link": True},
        )
        resp2 = client.patch(
            f"/api/dispatch/loads/{load['load_id']}/email-package",
            json={
                "broker_body": client.get(
                    f"/api/dispatch/loads/{load['load_id']}/email-package"
                ).get_json()["package"]["broker_body"],
                "include_stakeholder_link": True,
            },
        )
        assert resp2.status_code == 200
        body = resp2.get_json()["package"]["broker_body"]
        assert body.count(f"/portal/loads/{load['load_id']}") == 1

    def test_checkbox_present_in_dispatch_detail_template(self, client):
        load = self._delivered_load_with_client(client)
        self._draft(client, load["load_id"])
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert b'id="eh-include-stakeholder-link"' in resp.data
        assert b"Include Stakeholder Portal Link" in resp.data
