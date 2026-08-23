"""Tests for the email-driven control system: HTML emails, tokens, pending
decisions, and the portal decision endpoint."""

from __future__ import annotations

import json

import pytest

from cin_lite import control, email_delivery, pending, archive


# --------------------------------------------------------------------------- tokens

class TestTokens:
    def test_tokens_carry_their_own_expiry_and_both_verify(self):
        """Was `test_make_token_deterministic`, which asserted t1 == t2 and a
        64-char SHA-256 hex digest. Determinism was a property of the old
        design, not a requirement -- and it was inseparable from the defect:
        a token with nothing in it but contract and action has nothing to
        expire on, so every link ever mailed stayed valid forever. The
        replacement asserts the property that actually matters."""
        t1 = email_delivery.make_token("CIN-001", "approve_archive")
        t2 = email_delivery.make_token("CIN-001", "approve_archive")
        assert email_delivery.verify_token("CIN-001", "approve_archive", t1)
        assert email_delivery.verify_token("CIN-001", "approve_archive", t2)
        assert t1.startswith("ce1.")

    def test_expired_token_is_refused(self):
        token = email_delivery.make_token("CIN-001", "approve_archive", ttl_hours=-1)
        assert email_delivery.verify_token("CIN-001", "approve_archive", token) is False

    def test_legacy_digest_is_refused_without_an_explicit_grace_window(self):
        """A pre-expiry link must not be permanently valid just because it was
        issued before expiry existed."""
        import hashlib, hmac, os
        legacy = hmac.new(
            os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret").encode(),
            b"CIN-001:approve_archive", hashlib.sha256,
        ).hexdigest()
        assert email_delivery.verify_token("CIN-001", "approve_archive", legacy) is False

    def test_legacy_digest_accepted_only_inside_the_grace_window(self, monkeypatch):
        import hashlib, hmac, os
        legacy = hmac.new(
            os.environ.get("DISPATCH_EMAIL_SECRET", "dispatch-dev-secret").encode(),
            b"CIN-001:approve_archive", hashlib.sha256,
        ).hexdigest()
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "2099-01-01")
        assert email_delivery.verify_token("CIN-001", "approve_archive", legacy) is True
        monkeypatch.setenv("DISPATCH_LEGACY_TOKENS_UNTIL", "2000-01-01")
        assert email_delivery.verify_token("CIN-001", "approve_archive", legacy) is False

    def test_verify_token_valid(self):
        token = email_delivery.make_token("CIN-002", "reject")
        assert email_delivery.verify_token("CIN-002", "reject", token) is True

    def test_verify_token_wrong_action(self):
        token = email_delivery.make_token("CIN-002", "reject")
        assert email_delivery.verify_token("CIN-002", "approve_archive", token) is False

    def test_verify_token_wrong_contract(self):
        token = email_delivery.make_token("CIN-002", "reject")
        assert email_delivery.verify_token("CIN-999", "reject", token) is False

    def test_verify_token_tampered(self):
        assert email_delivery.verify_token("CIN-002", "reject", "bad" * 16) is False

    def test_custom_secret(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "my-secret")
        t1 = email_delivery.make_token("CIN-003", "reject")
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "other-secret")
        t2 = email_delivery.make_token("CIN-003", "reject")
        assert t1 != t2


# --------------------------------------------------------------------------- HTML email

class TestHTMLEmail:
    def test_render_html_contains_all_actions(self, mapped_contract, intelligence, flags):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary text", flags,
            contract_id="CIN-TEST-01",
        )
        for key, (label, _) in control.ACTIONS.items():
            assert label in html
            assert key in html

    def test_render_html_has_action_links(self, mapped_contract, intelligence, flags):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", flags,
            contract_id="CIN-TEST-02",
            action_url_base="http://localhost:8080/api/decision",
        )
        for key in control.ACTIONS:
            assert f"/api/decision/CIN-TEST-02/{key}" in html

    def test_render_html_with_tokens(self, mapped_contract, intelligence, flags):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", flags,
            contract_id="CIN-TEST-03",
            token_fn=email_delivery.make_token,
        )
        for key in control.ACTIONS:
            token = email_delivery.make_token("CIN-TEST-03", key)
            assert f"token={token}" in html

    def test_render_html_shows_recommendation(self, mapped_contract, intelligence, flags):
        decision = {
            "action": "approve_proposal", "priority": "high",
            "recipient": "proposal-team", "reason": "good fit", "notes": "",
        }
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", flags, decision,
            contract_id="CIN-TEST-04",
        )
        assert "RECOMMENDED" in html
        assert "Routing Agent Recommendation" in html
        assert "approve_proposal" in html

    def test_render_html_shows_contract_info(self, mapped_contract, intelligence, flags):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", flags,
            contract_id="CIN-TEST-05",
        )
        assert mapped_contract["title"] in html
        assert "CIN-TEST-05" in html

    def test_render_html_shows_flags(self, mapped_contract, intelligence, flags):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", flags,
            contract_id="CIN-TEST-06",
        )
        for flag in flags[:3]:
            assert flag in html

    def test_render_html_no_flags(self, mapped_contract, intelligence):
        html = control.render_html_email(
            mapped_contract, intelligence, "Summary", [],
            contract_id="CIN-TEST-07",
        )
        assert "<em>none</em>" in html


# --------------------------------------------------------------------------- pending decisions

class TestPending:
    def test_store_and_load(self, tmp_archive):
        pending.store(
            "CIN-P-001", {"title": "Test"}, {"mod": {}}, "summary",
            {"action": "reject"}, ["flag1"],
        )
        record = pending.load("CIN-P-001")
        assert record is not None
        assert record["contract_id"] == "CIN-P-001"
        assert record["contract"]["title"] == "Test"
        assert record["summary"] == "summary"
        assert record["flags"] == ["flag1"]

    def test_load_missing_returns_none(self, tmp_archive):
        assert pending.load("NONEXISTENT") is None

    def test_complete_removes_file(self, tmp_archive):
        pending.store("CIN-P-002", {}, {}, "", {}, [])
        assert pending.load("CIN-P-002") is not None
        pending.complete("CIN-P-002")
        assert pending.load("CIN-P-002") is None

    def test_complete_missing_is_safe(self, tmp_archive):
        pending.complete("NONEXISTENT")

    def test_list_pending(self, tmp_archive):
        pending.store("CIN-P-003", {"title": "A"}, {}, "", {}, [])
        pending.store("CIN-P-004", {"title": "B"}, {}, "", {}, [])
        items = pending.list_pending()
        assert len(items) == 2
        ids = {item["contract_id"] for item in items}
        assert ids == {"CIN-P-003", "CIN-P-004"}

    def test_list_pending_empty(self, tmp_archive):
        assert pending.list_pending() == []


# --------------------------------------------------------------------------- checkpoint delivery

class TestCheckpointDelivery:
    def test_deliver_checkpoint_offline(self, tmp_archive, mapped_contract):
        status = email_delivery.deliver_checkpoint(
            mapped_contract, "CIN-CHK-001", "plain text", "<html>rich</html>",
        )
        assert "written to" in status
        eml_path = tmp_archive / "Outbox" / "CIN-CHK-001-checkpoint.eml"
        assert eml_path.exists()
        eml = eml_path.read_text(encoding="utf-8")
        assert "Decision Required" in eml
        assert "plain text" in eml
        assert "<html>rich</html>" in eml


# --------------------------------------------------------------------------- decision confirmation email

class TestDecisionEmail:
    @staticmethod
    def _read_eml(path):
        """Read .eml and return decoded full text (handles MIME base64 parts)."""
        from email import policy
        from email.parser import BytesParser
        raw = path.read_bytes()
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        parts = []
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ("text/plain", "text/html"):
                parts.append(part.get_content())
        return "\n".join(parts)

    def test_deliver_decision_has_html(self, tmp_archive, mapped_contract):
        decision = {"action": "approve_archive", "priority": "medium",
                    "recipient": "none", "reason": "fits", "notes": ""}
        status = email_delivery.deliver_decision(
            mapped_contract, "CIN-DEC-HTML", "Summary text",
            decision, "approve_archive", "ARCHIVE", ["flag_a"],
        )
        assert "written to" in status
        eml_path = tmp_archive / "Outbox" / "CIN-DEC-HTML.eml"
        content = self._read_eml(eml_path)
        assert "Decision Recorded" in content
        assert "Approve for archive" in content
        assert "ARCHIVE" in content
        assert "CIN-DEC-HTML" in content

    def test_decision_html_shows_followed(self, tmp_archive, mapped_contract):
        decision = {"action": "reject", "priority": "low",
                    "recipient": "none", "reason": "no fit", "notes": ""}
        email_delivery.deliver_decision(
            mapped_contract, "CIN-DEC-FOL", "Sum",
            decision, "reject", "REJECTED", [],
        )
        content = self._read_eml(tmp_archive / "Outbox" / "CIN-DEC-FOL.eml")
        assert "Followed recommendation" in content

    def test_decision_html_shows_overrode(self, tmp_archive, mapped_contract):
        decision = {"action": "approve_archive", "priority": "medium",
                    "recipient": "none", "reason": "fits", "notes": ""}
        email_delivery.deliver_decision(
            mapped_contract, "CIN-DEC-OVR", "Sum",
            decision, "reject", "REJECTED", [],
        )
        content = self._read_eml(tmp_archive / "Outbox" / "CIN-DEC-OVR.eml")
        assert "Overrode recommendation" in content

    def test_decision_html_shows_flags(self, tmp_archive, mapped_contract):
        decision = {"action": "reject", "priority": "low",
                    "recipient": "none", "reason": "n", "notes": ""}
        email_delivery.deliver_decision(
            mapped_contract, "CIN-DEC-FLG", "Sum",
            decision, "reject", "REJECTED", ["cyber_flag", "vendor_flag"],
        )
        content = self._read_eml(tmp_archive / "Outbox" / "CIN-DEC-FLG.eml")
        assert "cyber_flag" in content
        assert "vendor_flag" in content


# --------------------------------------------------------------------------- portal decision endpoint

class TestDecisionEndpoint:
    @pytest.fixture
    def app(self, tmp_archive, monkeypatch):
        monkeypatch.setattr(pending, "_PENDING_DIR", tmp_archive / "Pending")
        from portal.app import create_app
        app = create_app({"TESTING": True})
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def _seed_pending(self, tmp_archive, contract_id="CIN-DEC-001"):
        pending.store(
            contract_id,
            {"title": "Test Contract", "agency": "DOD",
             "solicitation_number": "SOL-001", "estimated_value": 1000000},
            {"set_aside_detection": {
                "module": "set_aside_detection", "version": "1.0",
                "flags": [], "findings": {}, "summary": "No set-asides",
                "score": None, "deterministic": True,
            }},
            "Test summary",
            {"action": "approve_archive", "priority": "medium",
             "recipient": "none", "reason": "r", "notes": "n"},
            ["test_flag"],
        )

    def test_valid_decision(self, client, tmp_archive):
        self._seed_pending(tmp_archive)
        token = email_delivery.make_token("CIN-DEC-001", "approve_archive")
        resp = client.get(f"/api/decision/CIN-DEC-001/approve_archive?token={token}")
        assert resp.status_code == 200
        assert b"Decision Recorded" in resp.data
        assert b"Approve for archive" in resp.data
        assert pending.load("CIN-DEC-001") is None

    def test_invalid_action(self, client, tmp_archive):
        self._seed_pending(tmp_archive)
        token = email_delivery.make_token("CIN-DEC-001", "bogus")
        resp = client.get(f"/api/decision/CIN-DEC-001/bogus?token={token}")
        assert resp.status_code == 400
        assert b"Unknown action" in resp.data

    def test_invalid_token(self, client, tmp_archive):
        self._seed_pending(tmp_archive)
        resp = client.get("/api/decision/CIN-DEC-001/approve_archive?token=bad")
        assert resp.status_code == 403
        assert b"Invalid or expired token" in resp.data

    def test_missing_pending(self, client, tmp_archive):
        token = email_delivery.make_token("CIN-MISSING", "reject")
        resp = client.get(f"/api/decision/CIN-MISSING/reject?token={token}")
        assert resp.status_code == 404
        assert b"already processed" in resp.data

    def test_decision_creates_archive_artifacts(self, client, tmp_archive):
        self._seed_pending(tmp_archive)
        token = email_delivery.make_token("CIN-DEC-001", "reject")
        client.get(f"/api/decision/CIN-DEC-001/reject?token={token}")

        routing_files = list((tmp_archive / "Routing").glob("*.json"))
        assert len(routing_files) == 1
        routing = json.loads(routing_files[0].read_text())
        assert routing["action"] == "reject"
        assert routing["route"] == "REJECTED"

    def test_approve_proposal_triggers_workflow(self, client, tmp_archive):
        self._seed_pending(tmp_archive, "CIN-DEC-002")
        token = email_delivery.make_token("CIN-DEC-002", "approve_proposal")
        resp = client.get(f"/api/decision/CIN-DEC-002/approve_proposal?token={token}")
        assert resp.status_code == 200
        assert b"Proposal Triggered" in resp.data

    def test_double_click_returns_404(self, client, tmp_archive):
        self._seed_pending(tmp_archive, "CIN-DEC-003")
        token = email_delivery.make_token("CIN-DEC-003", "approve_archive")
        resp1 = client.get(f"/api/decision/CIN-DEC-003/approve_archive?token={token}")
        assert resp1.status_code == 200
        resp2 = client.get(f"/api/decision/CIN-DEC-003/approve_archive?token={token}")
        assert resp2.status_code == 404
