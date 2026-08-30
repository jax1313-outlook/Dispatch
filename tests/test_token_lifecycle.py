"""Workstream E: operational tokens expire, scope, and can be revoked.

Before this, `make_stakeholder_token(load_id)` was a bare keyed digest. It had
no timestamp, no nonce and no record, so the same string opened the load
forever and the only way to stop one was to rotate the global signing secret,
which killed every other link at the same time. Every test here asserts a
property that design could not have.
"""

from __future__ import annotations

import pytest

from dispatch import notifications, services, tokens
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path):
    set_db_path(tmp_path / "tokens.db")
    yield
    set_db_path(None)


@pytest.fixture()
def load():
    return services.create_load(customer="Token Co", pickup_location="Jacksonville, FL")


class TestIssueAndVerify:
    def test_a_fresh_token_verifies_for_its_own_load(self, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        assert notifications.verify_stakeholder_token(load["load_id"], token)

    def test_two_tokens_for_the_same_load_are_distinguishable(self, load):
        """The nonce is what makes individual revocation possible at all. If
        two tokens for one load were identical there would be nothing to
        revoke one of."""
        first = notifications.make_stakeholder_token(load["load_id"])
        second = notifications.make_stakeholder_token(load["load_id"])
        assert first != second
        assert notifications.verify_stakeholder_token(load["load_id"], first)
        assert notifications.verify_stakeholder_token(load["load_id"], second)

    def test_token_is_scoped_to_one_load(self, load):
        other = services.create_load(customer="Someone Else")
        token = notifications.make_stakeholder_token(load["load_id"])
        assert not notifications.verify_stakeholder_token(other["load_id"], token)

    def test_stakeholder_token_cannot_act_as_a_decision_token(self, load):
        """The purpose claim is signed, so a view link cannot be replayed
        against an action endpoint."""
        view = notifications.make_stakeholder_token(load["load_id"])
        assert not notifications.verify_token(load["load_id"], "acknowledge", view)

    def test_decision_token_cannot_act_as_a_stakeholder_token(self, load):
        decision = notifications.make_token(load["load_id"], "acknowledge")
        assert not notifications.verify_stakeholder_token(load["load_id"], decision)

    def test_decision_token_is_scoped_to_one_action(self, load):
        token = notifications.make_token(load["load_id"], "acknowledge")
        assert notifications.verify_token(load["load_id"], "acknowledge", token)
        assert not notifications.verify_token(load["load_id"], "escalate", token)


class TestFailClosed:
    @pytest.mark.parametrize(
        "bad",
        ["", "garbage", "dt1.only-two-parts", "dt1..", "x" * 64,
         "dt1.bm90LWpzb24.deadbeef"],
    )
    def test_malformed_tokens_are_refused(self, load, bad):
        assert not notifications.verify_stakeholder_token(load["load_id"], bad)

    def test_tampered_signature_is_refused(self, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        version, payload, signature = token.split(".")
        flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
        assert not notifications.verify_stakeholder_token(
            load["load_id"], f"{version}.{payload}.{flipped}"
        )

    def test_tampered_payload_is_refused(self, load):
        """Re-encoding the claims with a different load id must fail on the
        signature, not be silently accepted."""
        import base64, json
        token = notifications.make_stakeholder_token(load["load_id"])
        version, payload, signature = token.split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "==").decode())
        claims["o"] = "LOAD-SOMEONE-ELSE"
        forged = base64.urlsafe_b64encode(
            json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
        ).decode().rstrip("=")
        assert not notifications.verify_stakeholder_token(
            "LOAD-SOMEONE-ELSE", f"{version}.{forged}.{signature}"
        )

    def test_a_correctly_signed_token_with_no_ledger_row_is_refused(self, load):
        """Signed but unknown means it cannot be checked for revocation, so it
        fails closed rather than being trusted on its signature alone."""
        token = notifications.make_stakeholder_token(load["load_id"])
        record = tokens.list_tokens(object_id=load["load_id"])[0]
        from dispatch.db import get_connection
        with get_connection() as conn:
            conn.execute("DELETE FROM operational_tokens WHERE token_id=?", (record["token_id"],))
        assert not notifications.verify_stakeholder_token(load["load_id"], token)


class TestExpiry:
    def test_an_expired_token_is_refused(self, load):
        token = tokens.issue("stakeholder_view", load["load_id"], ttl_hours=-1)
        verdict = tokens.verify("stakeholder_view", load["load_id"], token)
        assert not verdict
        assert verdict.reason == "expired"

    def test_expiry_is_recorded_on_the_token_and_in_the_ledger(self, load):
        notifications.make_stakeholder_token(load["load_id"])
        record = tokens.list_tokens(object_id=load["load_id"])[0]
        assert record["expires_at"] > record["issued_at"]

    def test_stakeholder_links_do_not_outlive_their_default_window(self, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        verdict = tokens.verify("stakeholder_view", load["load_id"], token)
        assert verdict.expires_at


class TestRevocation:
    def test_a_revoked_token_stops_working(self, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        record = tokens.list_tokens(object_id=load["load_id"])[0]

        assert notifications.verify_stakeholder_token(load["load_id"], token)
        assert tokens.revoke(record["token_id"], reason="forwarded in error", actor="mike")
        assert not notifications.verify_stakeholder_token(load["load_id"], token)

    def test_revoking_twice_reports_no_second_revocation(self, load):
        notifications.make_stakeholder_token(load["load_id"])
        record = tokens.list_tokens(object_id=load["load_id"])[0]
        assert tokens.revoke(record["token_id"], actor="mike")
        assert tokens.revoke(record["token_id"], actor="mike") is False

    def test_revoking_a_load_kills_every_live_link_for_it(self, load):
        """The control that did not exist: previously the only way to stop a
        forwarded link was to rotate the global secret and break every other
        link in the business."""
        first = notifications.make_stakeholder_token(load["load_id"])
        second = notifications.make_stakeholder_token(load["load_id"])

        killed = notifications.revoke_stakeholder_access(
            load["load_id"], reason="link left the intended recipient", actor="mike"
        )
        assert killed == 2
        assert not notifications.verify_stakeholder_token(load["load_id"], first)
        assert not notifications.verify_stakeholder_token(load["load_id"], second)

    def test_revoking_one_load_does_not_touch_another(self, load):
        other = services.create_load(customer="Untouched Co")
        mine = notifications.make_stakeholder_token(load["load_id"])
        theirs = notifications.make_stakeholder_token(other["load_id"])

        notifications.revoke_stakeholder_access(load["load_id"], actor="mike")

        assert not notifications.verify_stakeholder_token(load["load_id"], mine)
        assert notifications.verify_stakeholder_token(other["load_id"], theirs)


class TestAudit:
    def test_issue_verify_and_revoke_all_leave_a_trail(self, load):
        token = notifications.make_stakeholder_token(load["load_id"], issued_by="mike")
        notifications.verify_stakeholder_token(load["load_id"], token)
        record = tokens.list_tokens(object_id=load["load_id"])[0]
        tokens.revoke(record["token_id"], reason="done", actor="mike")

        events = [e["event"] for e in tokens.list_audit(object_id=load["load_id"])]
        assert "issued" in events
        assert "verified" in events
        assert "revoked" in events

    def test_a_refusal_records_why(self, load):
        notifications.verify_stakeholder_token(load["load_id"], "dt1.garbage.garbage")
        reasons = [e["reason"] for e in tokens.list_audit(object_id=load["load_id"])]
        assert "malformed_payload" in reasons or "bad_signature" in reasons

    def test_the_actor_who_issued_a_token_is_recorded(self, load):
        notifications.make_stakeholder_token(load["load_id"], issued_by="mike")
        record = tokens.list_tokens(object_id=load["load_id"])[0]
        assert record["issued_by"] == "mike"


class TestLegacyTokens:
    """Old digests must not be permanently valid, and must not be silently
    honoured either. Acceptance is an explicit, expiring, audited decision."""

    def _legacy(self, load_id: str) -> str:
        return notifications._legacy_digest("dispatch-stakeholder", load_id)

    def test_legacy_token_refused_by_default(self, load):
        assert not notifications.verify_stakeholder_token(
            load["load_id"], self._legacy(load["load_id"])
        )

    def test_legacy_token_accepted_inside_an_explicit_grace_window(self, load, monkeypatch):
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "2099-01-01")
        assert notifications.verify_stakeholder_token(
            load["load_id"], self._legacy(load["load_id"])
        )

    def test_legacy_acceptance_is_audited_as_such(self, load, monkeypatch):
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "2099-01-01")
        notifications.verify_stakeholder_token(load["load_id"], self._legacy(load["load_id"]))
        reasons = [e["reason"] for e in tokens.list_audit(object_id=load["load_id"])]
        assert "legacy_grace" in reasons

    def test_grace_window_in_the_past_refuses(self, load, monkeypatch):
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "2000-01-01")
        assert not notifications.verify_stakeholder_token(
            load["load_id"], self._legacy(load["load_id"])
        )

    def test_malformed_grace_window_refuses(self, load, monkeypatch):
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "not-a-date")
        assert not notifications.verify_stakeholder_token(
            load["load_id"], self._legacy(load["load_id"])
        )


class TestTheLiveRouteFailsClosed:
    """The unit tests above prove the engine. These prove the actual HTTP
    surface a broker would hit, because that is what ships."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True
        return app.test_client()

    def test_valid_token_opens_the_load(self, client, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        assert resp.status_code == 200

    def test_revoked_token_is_refused_by_the_route(self, client, load):
        token = notifications.make_stakeholder_token(load["load_id"])
        notifications.revoke_stakeholder_access(load["load_id"], actor="mike")
        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        assert resp.status_code == 403

    def test_expired_token_is_refused_by_the_route(self, client, load):
        token = tokens.issue("stakeholder_view", load["load_id"], ttl_hours=-1)
        resp = client.get(f"/portal/loads/{load['load_id']}?token={token}")
        assert resp.status_code == 403

    def test_revoked_token_cannot_download_evidence(self, client, load, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        evidence = services.attach_evidence(
            load["load_id"], evidence_type="pod",
            file_data=b"pod bytes", original_filename="pod.jpg",
        )
        token = notifications.make_stakeholder_token(load["load_id"])
        assert client.get(
            f"/portal/loads/{load['load_id']}/evidence/{evidence['evidence_id']}?token={token}"
        ).status_code == 200

        notifications.revoke_stakeholder_access(load["load_id"], actor="mike")
        assert client.get(
            f"/portal/loads/{load['load_id']}/evidence/{evidence['evidence_id']}?token={token}"
        ).status_code == 403
