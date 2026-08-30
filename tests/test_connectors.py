"""The connector contract, the eight connectors, the mock, and the refusals.

Operational Readiness Mission Section 6.8 lists the evidence this file has to
produce: interface tests, the mock with tests, simulated labelling visible in a
consuming surface, failure handling (timeout, auth failure, malformed payload),
configuration validation, secret redaction, a test that no connector can claim
LIVE without evidence of a real exchange, audit records for every attempt, and
the Section 6.7 resilience proof.

The structural half of the boundary -- the import-graph scan and the runtime
seal -- lives in tests/test_connector_boundary.py.
"""

from __future__ import annotations

import smtplib
import sqlite3

import pytest

from dispatch import readiness, services
from dispatch.connectors import audit, boundary, registry
from dispatch.connectors.accounting_connector import AccountingConnector
from dispatch.connectors.contract import (
    AuthenticationStatus,
    CapabilityDeclaration,
    ConfigurationStatus,
    Connector,
    ConnectorError,
    ConnectorRefusal,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    ExchangeEvidence,
    HealthStatus,
    NormalizedPayload,
    Provenance,
    TRUTH_WORDS,
    UnlabeledDisplayError,
    assert_labeled_display,
    contains_secret,
    parse_status,
    redact,
    require_payload,
)
from dispatch.connectors.email_transport_connector import EmailTransportConnector
from dispatch.connectors.load_board_connector import LoadBoardConnector
from dispatch.connectors.mock import MockRouteRiskConnector
from dispatch.connectors.outlook_connector import OutlookConnector
from dispatch.connectors.route_risk_connector import (
    AdvisoryRouteRiskEvaluator,
    RouteCondition,
    RouteRiskAssessment,
    RouteRiskEvaluator,
    RouteRiskFinding,
    assessment_to_event_kwargs,
    evaluation_inputs,
    normalize_conditions,
)
from dispatch.db import set_db_path


@pytest.fixture()
def connector_db(tmp_path, monkeypatch):
    """A database of this test's own, so audit rows can be read back."""
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    set_db_path(tmp_path / "connectors.db")
    yield tmp_path
    set_db_path(None)


def _request(operation: str = "fetch_conditions", **params) -> ConnectorRequest:
    return ConnectorRequest(operation, params)


# ── the truth vocabulary ──────────────────────────────────────────────


class TestTruthVocabulary:
    def test_the_eight_words_and_only_those(self):
        assert TRUTH_WORDS == (
            "LIVE", "CONFIGURED", "UNCONFIGURED", "SIMULATED",
            "UNAVAILABLE", "MANUAL", "ABSENT", "UNVERIFIED",
        )

    def test_matches_the_readiness_module_word_for_word(self):
        """The vocabulary is duplicated per THE MIKE RULE; this stops it drifting."""
        assert set(TRUTH_WORDS) == set(readiness.TRUTH_WORDS)

    @pytest.mark.parametrize("word", ["CONNECTED", "VERIFIED", "CURRENT", "ONLINE", "OK", "HEALTHY"])
    def test_words_that_read_like_evidence_are_refused_by_name(self, word):
        with pytest.raises(ValueError, match="not a Dispatch truth word"):
            parse_status(word)

    def test_a_synonym_is_refused_with_the_list(self):
        with pytest.raises(ValueError, match="Synonyms and softer variants"):
            parse_status("degraded")

    def test_parse_status_accepts_the_vocabulary_case_insensitively(self):
        assert parse_status("simulated") is ConnectorStatus.SIMULATED

    def test_no_forbidden_word_is_a_status_member(self):
        members = {s.value for s in ConnectorStatus}
        assert members.isdisjoint({"CONNECTED", "VERIFIED", "CURRENT", "ONLINE"})


# ── the eight ─────────────────────────────────────────────────────────


class TestTheEightConnectors:
    def test_exactly_eight_are_registered(self):
        assert len(registry.CONNECTOR_IDS) == 8

    def test_they_are_the_eight_section_6_4_names(self):
        names = [registry.get(cid).identity().connector_name for cid in registry.CONNECTOR_IDS]
        assert names == [
            "Route Risk Connector",
            "Accounting Connector",
            "Scanner Connector",
            "Outlook Connector",
            "Email Transport Connector",
            "Load Board Connector",
            "Mapping and Routing Connector",
            "Future External Intelligence Connector",
        ]

    def test_every_registered_connector_satisfies_the_protocol(self):
        for connector in registry.all_connectors():
            assert isinstance(connector, Connector)

    def test_every_connector_reports_unconfigured_out_of_the_box(self):
        for row in registry.status_board():
            assert row["connector_status"] == "UNCONFIGURED"

    def test_no_connector_claims_a_provider_it_does_not_have(self):
        for connector in registry.all_connectors():
            assert connector.identity().provider_selected is False

    def test_an_unknown_connector_is_refused_rather_than_returning_none(self):
        with pytest.raises(registry.UnknownConnector, match="not a Dispatch connector"):
            registry.get("quickbooks")

    def test_the_mock_is_not_one_of_the_eight(self):
        assert "mock.route_risk" not in registry.CONNECTOR_IDS
        assert all(c.identity().connector_id != "mock.route_risk" for c in registry.all_connectors())

    def test_the_mock_is_reachable_deliberately(self):
        assert isinstance(registry.mock_connector(), MockRouteRiskConnector)

    def test_a_fresh_instance_is_built_each_time_so_configuration_is_reread(self, monkeypatch):
        before = registry.get("mapping").configuration().status
        monkeypatch.setenv("DISPATCH_MAPPING_API_URL", "https://maps.example.com")
        monkeypatch.setenv("DISPATCH_MAPPING_API_KEY", "k-123456")
        after = registry.get("mapping").configuration().status
        assert before is ConnectorStatus.UNCONFIGURED
        assert after is ConnectorStatus.CONFIGURED


# ── capability declarations ───────────────────────────────────────────


class TestCapabilityDeclaration:
    @pytest.mark.parametrize(
        "claim",
        [
            "apply lifecycle transitions",
            "approve a load for the customer",
            "set pricing for the lane",
            "accept the offer",
            "own scheduling truth",
            "define operational doctrine",
        ],
    )
    def test_authority_a_connector_may_never_hold_cannot_be_declared(self, claim):
        with pytest.raises(ValueError, match="authority a connector may never hold"):
            CapabilityDeclaration(produces=(claim,))

    def test_the_prohibition_is_reported_for_display(self):
        assert "pricing authority" in CapabilityDeclaration().never

    def test_every_registered_connector_declares_the_same_prohibitions(self):
        for connector in registry.all_connectors():
            assert connector.capabilities().never == CapabilityDeclaration().never

    def test_outlook_declares_event_creation_as_human_authorized(self):
        capabilities = OutlookConnector().capabilities()
        assert "request_event_creation" in capabilities.requires_human_authorization

    def test_the_future_intelligence_slot_declares_nothing(self):
        capabilities = registry.get("future_intelligence").capabilities()
        assert capabilities.collects == () and capabilities.produces == ()


# ── configuration validation ──────────────────────────────────────────


class TestConfigurationValidation:
    def test_missing_keys_are_named_so_an_operator_knows_what_to_set(self):
        config = registry.get("route_risk").configuration()
        assert config.status is ConnectorStatus.UNCONFIGURED
        assert set(config.missing_keys) == {
            "DISPATCH_ROUTE_RISK_API_URL", "DISPATCH_ROUTE_RISK_API_KEY",
        }

    def test_partial_configuration_is_still_unconfigured(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_ROUTE_RISK_API_URL", "https://example.test")
        config = registry.get("route_risk").configuration()
        assert config.status is ConnectorStatus.UNCONFIGURED
        assert config.present_keys == ("DISPATCH_ROUTE_RISK_API_URL",)
        assert config.missing_keys == ("DISPATCH_ROUTE_RISK_API_KEY",)

    def test_whitespace_only_configuration_does_not_count_as_present(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SCANNER_API_URL", "   ")
        monkeypatch.setenv("DISPATCH_SCANNER_API_KEY", "   ")
        assert registry.get("scanner").configuration().status is ConnectorStatus.UNCONFIGURED

    def test_full_configuration_reports_configured_not_live(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SCANNER_API_URL", "https://scanner.example.test")
        monkeypatch.setenv("DISPATCH_SCANNER_API_KEY", "scan-key-123456")
        config = registry.get("scanner").configuration()
        assert config.status is ConnectorStatus.CONFIGURED
        assert config.status is not ConnectorStatus.LIVE

    def test_a_connector_with_no_provider_says_so_rather_than_listing_keys(self):
        config = registry.get("future_intelligence").configuration()
        assert config.required_keys == ()
        assert "no provider chosen" in config.detail

    def test_configuration_status_refuses_a_bare_string(self):
        with pytest.raises(ValueError, match="not a Dispatch truth word"):
            ConfigurationStatus("CONFIGURED")


class TestAuthenticationReporting:
    def test_present_credentials_are_unverified_not_configured(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_MAPPING_API_KEY", "map-key-123456")
        auth = registry.get("mapping").authentication()
        assert auth.status is ConnectorStatus.UNVERIFIED
        assert "unproven" in auth.detail

    def test_missing_credentials_are_unconfigured(self):
        assert registry.get("mapping").authentication().status is ConnectorStatus.UNCONFIGURED

    def test_a_relay_without_login_reports_absent_rather_than_unconfigured(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")
        auth = EmailTransportConnector().authentication()
        assert auth.status is ConnectorStatus.ABSENT

    def test_live_authentication_requires_the_timestamp_that_proved_it(self):
        with pytest.raises(ValueError, match="requires the timestamp"):
            AuthenticationStatus(ConnectorStatus.LIVE, method="api_key")

    def test_credential_names_may_not_carry_a_credential(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_MAPPING_API_KEY", "map-key-super-secret")
        with pytest.raises(ValueError, match="never holds them"):
            AuthenticationStatus(
                ConnectorStatus.UNVERIFIED, credential_names=("map-key-super-secret",)
            )


class TestHealthReporting:
    def test_a_connector_never_attempted_is_absent_not_unhealthy(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_MAPPING_API_URL", "https://maps.example.test")
        monkeypatch.setenv("DISPATCH_MAPPING_API_KEY", "map-key-123456")
        assert registry.get("mapping").health().status is ConnectorStatus.ABSENT

    def test_an_unconfigured_connector_reports_unconfigured_health(self):
        assert registry.get("mapping").health().status is ConnectorStatus.UNCONFIGURED

    def test_live_health_requires_a_last_success_timestamp(self):
        with pytest.raises(ValueError, match="last successful communication"):
            HealthStatus(ConnectorStatus.LIVE)


# ── LIVE requires evidence ────────────────────────────────────────────


class TestNoLiveWithoutEvidence:
    def test_live_provenance_without_evidence_is_refused(self):
        with pytest.raises(ValueError, match="must carry ExchangeEvidence"):
            Provenance("mapping", "Some Provider", ConnectorStatus.LIVE)

    def test_evidence_attached_to_simulated_data_is_refused(self):
        evidence = ExchangeEvidence.from_response("https://example.test", b"{}")
        with pytest.raises(ValueError, match="misdescribes it"):
            Provenance("mapping", "Some Provider", ConnectorStatus.SIMULATED, evidence=evidence)

    def test_evidence_needs_a_response_fingerprint(self):
        with pytest.raises(ValueError, match="fingerprint of the response"):
            ExchangeEvidence(endpoint="https://example.test", response_fingerprint="")

    def test_evidence_needs_an_endpoint(self):
        with pytest.raises(ValueError, match="endpoint that answered"):
            ExchangeEvidence(endpoint="", response_fingerprint="abc")

    def test_a_fingerprint_is_a_hash_not_the_response_body(self):
        evidence = ExchangeEvidence.from_response("https://example.test", b'{"secret":"body"}')
        assert "secret" not in evidence.response_fingerprint
        assert len(evidence.response_fingerprint) == 64

    def test_no_registered_connector_emits_live_when_asked(self, connector_db):
        for connector in registry.all_connectors():
            result = boundary.execute(connector, _request("fetch_conditions"))
            assert result.status is not ConnectorStatus.LIVE

    def test_the_mock_cannot_emit_live_on_any_path(self, connector_db):
        for mode, kwargs in [
            ("", {}), ("timeout", {}), ("auth", {}), ("malformed", {}),
            ("timeout", {"succeed_after": 2}),
        ]:
            connector = MockRouteRiskConnector(failure_mode=mode, **kwargs)
            result = boundary.execute(connector, ConnectorRequest("fetch_conditions", max_attempts=2))
            assert result.status is not ConnectorStatus.LIVE

    def test_confidence_is_a_zero_to_one_declaration(self):
        with pytest.raises(ValueError, match="0..1 declaration"):
            Provenance("mapping", "p", ConnectorStatus.SIMULATED, confidence=97.0)


# ── secret redaction ──────────────────────────────────────────────────


class TestSecretRedaction:
    def test_a_configured_secret_value_is_removed_by_value(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_PASSWORD", "hunter2-and-then-some")
        assert "hunter2-and-then-some" not in redact("login failed for hunter2-and-then-some")

    def test_a_secret_shaped_fragment_is_removed_even_if_never_configured(self):
        cleaned = redact("Authorization: Bearer abcdef123456ghijkl")
        assert "abcdef123456ghijkl" not in cleaned
        assert "[REDACTED]" in cleaned

    def test_a_key_value_credential_is_removed(self):
        assert "s3cr3t-value" not in redact("api_key=s3cr3t-value&x=1")

    def test_short_values_are_not_treated_as_secrets(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_USER", "abc")
        assert redact("abc appears in ordinary prose") == "abc appears in ordinary prose"

    def test_contains_secret_detects_a_live_value(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
        assert contains_secret("token sk-ant-not-a-real-key") is True
        assert contains_secret("nothing here") is False
        assert contains_secret("") is False

    def test_an_error_scrubs_its_reason_and_detail_at_construction(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_ACCOUNTING_API_KEY", "acct-key-abcdef")
        error = ConnectorError(
            "auth_failure", "rejected acct-key-abcdef", detail="header acct-key-abcdef"
        )
        assert "acct-key-abcdef" not in error.reason
        assert "acct-key-abcdef" not in error.detail

    def test_health_scrubs_its_last_error(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SCANNER_API_KEY", "scan-key-abcdef")
        health = HealthStatus(ConnectorStatus.UNAVAILABLE, last_error="401 for scan-key-abcdef")
        assert "scan-key-abcdef" not in health.last_error

    def test_no_secret_reaches_the_status_board(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_MAPPING_API_URL", "https://maps.example.test")
        monkeypatch.setenv("DISPATCH_MAPPING_API_KEY", "map-key-abcdef123")
        rendered = str(registry.status_board())
        assert "map-key-abcdef123" not in rendered
        assert "DISPATCH_MAPPING_API_KEY" in rendered  # the NAME is fine, the value is not

    def test_a_failing_relay_leaks_nothing_into_the_result_or_the_audit(
        self, connector_db, monkeypatch
    ):
        """The end-to-end redaction case: SMTP raises with the password in the text."""
        password = "relay-password-abcdef"
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")
        monkeypatch.setenv("DISPATCH_SMTP_USER", "dispatch")
        monkeypatch.setenv("DISPATCH_SMTP_PASSWORD", password)

        def boom(host, port, timeout=None):
            raise OSError(f"535 authentication failed for dispatch/{password}")

        monkeypatch.setattr(smtplib, "SMTP", boom)

        result = boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"]}),
        )
        assert result.status is ConnectorStatus.UNAVAILABLE
        assert password not in str(result.to_dict())
        rows = audit.list_audit("email_transport")
        assert rows and password not in str(rows)


# ── labelling in a consuming surface ──────────────────────────────────


class TestSimulatedLabelling:
    def test_a_payload_carries_its_status_into_every_rendering(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request(load_id="L-1"))
        rendered = result.payload.to_display_dict()
        assert rendered["connector_status"] == "SIMULATED"
        assert rendered["connector_label"].startswith("SIMULATED — ")

    def test_simulated_data_is_not_operational_intelligence(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assert result.payload.is_operational_intelligence is False
        assert result.payload.to_display_dict()["label_required"] is True

    def test_the_mock_labels_itself_in_the_text_a_human_reads(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        for condition in result.payload.data["conditions"]:
            assert "SIMULATED" in condition["summary"]

    def test_a_rendering_that_dropped_the_status_is_refused(self):
        with pytest.raises(UnlabeledDisplayError, match="without its status"):
            assert_labeled_display({"conditions": [], "load_id": "L-1"})

    def test_a_labelled_rendering_passes_and_is_returned(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        rendered = result.payload.to_display_dict()
        assert assert_labeled_display(rendered) is rendered

    def test_a_rendering_labelled_with_a_forbidden_word_is_refused(self):
        with pytest.raises(ValueError, match="not a Dispatch truth word"):
            assert_labeled_display({"connector_status": "CONNECTED"})

    def test_every_status_board_row_shows_a_truth_word(self):
        for row in registry.status_board():
            assert row["connector_status"] in TRUTH_WORDS
            assert row["configuration"]["status"] in TRUTH_WORDS
            assert row["authentication"]["status"] in TRUTH_WORDS
            assert row["health"]["status"] in TRUTH_WORDS

    def test_freshness_is_derived_and_says_so_when_it_cannot_be(self):
        provenance = Provenance("mapping", "p", ConnectorStatus.SIMULATED)
        assert provenance.freshness_seconds is None
        assert provenance.freshness_label == "freshness unknown"

    @pytest.mark.parametrize(
        "source,expected",
        [
            ("2026-08-24T12:00:00Z", "0s old at receipt"),
            ("2026-08-24T11:55:00Z", "5m old at receipt"),
            ("2026-08-24T09:00:00Z", "3.0h old at receipt"),
            ("2026-08-24T12:05:00Z", "source timestamp is in the future"),
        ],
    )
    def test_freshness_is_reported_in_human_units(self, source, expected):
        provenance = Provenance(
            "mapping", "p", ConnectorStatus.SIMULATED,
            source_timestamp=source, received_timestamp="2026-08-24T12:00:00Z",
        )
        assert provenance.freshness_label == expected


# ── the mock ──────────────────────────────────────────────────────────


class TestMockConnector:
    def test_it_reports_simulated_on_every_status_it_has(self):
        connector = MockRouteRiskConnector()
        assert connector.configuration().status is ConnectorStatus.SIMULATED
        assert connector.authentication().status is ConnectorStatus.SIMULATED
        assert connector.health().status is ConnectorStatus.SIMULATED

    def test_it_names_itself_as_having_no_external_system(self):
        assert "no external system" in MockRouteRiskConnector().identity().provider_name

    def test_a_successful_fetch_returns_normalized_conditions(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request(load_id="L-9"))
        assert result.ok
        assert result.payload.kind == "route_risk_conditions"
        assert result.payload.data["condition_count"] == 2
        assert result.payload.data["load_id"] == "L-9"

    def test_health_records_the_attempt_and_the_success(self, connector_db):
        connector = MockRouteRiskConnector()
        boundary.execute(connector, _request())
        health = connector.health()
        assert health.last_attempt_at and health.last_success_at

    def test_an_unknown_failure_mode_is_refused(self):
        with pytest.raises(ValueError, match="not a mock failure mode"):
            MockRouteRiskConnector(failure_mode="explode")

    def test_it_is_not_reachable_through_the_registry(self):
        with pytest.raises(registry.UnknownConnector):
            registry.get("mock.route_risk")


class TestFailureHandling:
    def test_a_timeout_is_retried_and_reported_as_exhausted(self, connector_db):
        result = boundary.execute(
            MockRouteRiskConnector(failure_mode="timeout"),
            ConnectorRequest("fetch_conditions", max_attempts=3),
        )
        assert result.status is ConnectorStatus.UNAVAILABLE
        assert result.error.kind == "timeout"
        assert result.error.retryable is True
        assert result.retry.attempts == 3 and result.retry.exhausted is True
        assert result.retry.next_delay_seconds > 0

    def test_a_recoverable_timeout_succeeds_on_the_second_attempt(self, connector_db):
        result = boundary.execute(
            MockRouteRiskConnector(failure_mode="timeout", succeed_after=2),
            ConnectorRequest("fetch_conditions", max_attempts=3),
        )
        assert result.ok and result.retry.attempts == 2 and result.retry.exhausted is False

    def test_an_auth_failure_is_not_retried(self, connector_db):
        result = boundary.execute(
            MockRouteRiskConnector(failure_mode="auth"),
            ConnectorRequest("fetch_conditions", max_attempts=5),
        )
        assert result.error.kind == "auth_failure"
        assert result.error.retryable is False
        assert result.retry.attempts == 1

    def test_a_malformed_response_fails_rather_than_dropping_the_field(self, connector_db):
        result = boundary.execute(
            MockRouteRiskConnector(failure_mode="malformed"), _request()
        )
        assert result.error.kind == "malformed_payload"
        assert result.payload is None

    def test_a_failure_names_the_connector_and_the_status(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(failure_mode="auth"), _request())
        message = result.refusal_message()
        assert "Mock Route Risk Connector" in message and "UNAVAILABLE" in message

    def test_a_connector_that_raises_is_reported_as_unavailable_not_crashed(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(failure_mode="crash"), _request())
        assert result.status is ConnectorStatus.UNAVAILABLE
        assert result.error.kind == "provider_error"
        assert "RuntimeError" in result.error.reason

    def test_require_payload_raises_the_labelled_refusal(self, connector_db):
        result = boundary.execute(registry.get("scanner"), _request("scan"))
        with pytest.raises(ConnectorRefusal) as caught:
            require_payload(result)
        assert caught.value.status is ConnectorStatus.UNCONFIGURED
        assert "Scanner Connector is UNCONFIGURED" in str(caught.value)

    def test_require_payload_returns_the_payload_when_there_is_one(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assert require_payload(result) is result.payload

    def test_a_result_cannot_be_both_a_success_and_a_failure(self):
        with pytest.raises(ValueError, match="never both and never neither"):
            ConnectorResult(ConnectorStatus.SIMULATED, "x", "op")

    def test_a_result_may_not_disagree_with_its_payload(self):
        payload = NormalizedPayload(
            Provenance("x", "p", ConnectorStatus.SIMULATED), "kind", {}
        )
        with pytest.raises(ValueError, match="disagrees with its payload"):
            ConnectorResult(ConnectorStatus.MANUAL, "x", "op", payload=payload)

    def test_an_error_kind_outside_the_closed_list_is_refused(self):
        with pytest.raises(ValueError, match="not one of the connector error kinds"):
            ConnectorError("gremlins", "something")

    def test_a_request_needs_an_operation_and_at_least_one_attempt(self):
        with pytest.raises(ValueError, match="needs an operation"):
            ConnectorRequest("")
        with pytest.raises(ValueError, match="at least 1"):
            ConnectorRequest("op", max_attempts=0)


# ── the audit trail ───────────────────────────────────────────────────


class TestConnectorAudit:
    def test_a_successful_attempt_is_recorded(self, connector_db):
        boundary.execute(MockRouteRiskConnector(), _request())
        rows = audit.list_audit("mock.route_risk")
        assert len(rows) == 1
        assert rows[0]["outcome"] == "ok" and rows[0]["status"] == "SIMULATED"

    def test_a_refusal_is_recorded_as_refused_not_as_a_failure(self, connector_db):
        boundary.execute(registry.get("mapping"), _request("fetch_distance"))
        rows = audit.list_audit("mapping")
        assert rows[0]["outcome"] == "refused"
        assert rows[0]["status"] == "UNCONFIGURED"
        assert "Mapping and Routing Connector is UNCONFIGURED" in rows[0]["reason"]

    def test_a_failed_attempt_is_recorded_with_its_attempt_count(self, connector_db):
        boundary.execute(
            MockRouteRiskConnector(failure_mode="timeout"),
            ConnectorRequest("fetch_conditions", max_attempts=2),
        )
        rows = audit.list_audit("mock.route_risk")
        assert rows[0]["outcome"] == "failed" and rows[0]["attempts"] == 2

    def test_every_attempt_leaves_a_row_including_the_refusals(self, connector_db):
        for connector in registry.all_connectors():
            boundary.execute(connector, _request("probe"))
        assert len(audit.list_audit(limit=50)) == 8

    def test_the_audit_row_carries_the_evidence_fingerprint_when_there_is_one(
        self, connector_db, monkeypatch
    ):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")
        monkeypatch.setattr(smtplib, "SMTP", _AcceptingSMTP)
        result = boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"]}),
        )
        row = audit.list_audit("email_transport")[0]
        assert row["status"] == "LIVE"
        assert row["evidence_fingerprint"] == result.payload.provenance.evidence.response_fingerprint

    def test_last_success_is_read_from_the_trail_not_from_memory(self, connector_db):
        boundary.execute(MockRouteRiskConnector(failure_mode="auth"), _request())
        assert audit.last_success("mock.route_risk") is None
        boundary.execute(MockRouteRiskConnector(), _request())
        assert audit.last_success("mock.route_risk")["outcome"] == "ok"

    def test_the_last_attempt_status_is_readable(self, connector_db):
        assert audit.status_from_last_attempt("mapping") is None
        boundary.execute(registry.get("mapping"), _request("fetch_distance"))
        assert audit.status_from_last_attempt("mapping") is ConnectorStatus.UNCONFIGURED

    def test_an_audit_write_failure_never_breaks_the_call(self, connector_db, monkeypatch):
        def unusable_database():
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr("dispatch.db.get_connection", lambda: unusable_database())
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assert result.ok is True

    def test_the_audit_row_mirrors_the_result_it_describes(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assert result.audit is not None
        assert result.audit.connector_id == "mock.route_risk"
        assert result.audit.status is result.status

    def test_an_audit_outcome_outside_the_closed_list_is_refused(self):
        from dispatch.connectors.contract import AuditRecord

        with pytest.raises(ValueError, match="not an audit outcome"):
            AuditRecord("x", "op", ConnectorStatus.SIMULATED, "probably_fine")


class _AcceptingSMTP:
    """An SMTP relay that accepts everything, for the LIVE-path tests."""

    def __init__(self, host, port, timeout=None):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        pass


# ── wrapping what already exists ──────────────────────────────────────


class TestEmailTransportWrapsTheExistingTransport:
    def test_no_relay_configured_is_simulated_and_says_nothing_was_delivered(self, connector_db):
        result = boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"],
                                      "fallback_id": "cx-1"}),
        )
        assert result.status is ConnectorStatus.SIMULATED
        assert result.payload.data["delivered"] is False
        assert "No message reached any recipient" in result.payload.data["note"]

    def test_the_fallback_eml_is_the_one_email_delivery_writes(self, connector_db, tmp_archive):
        boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"],
                                      "fallback_id": "cx-2"}),
        )
        assert (tmp_archive / "Outbox" / "cx-2.eml").is_file()

    def test_an_accepted_message_is_live_with_evidence(self, connector_db, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")
        monkeypatch.setattr(smtplib, "SMTP", _AcceptingSMTP)
        result = boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"]}),
        )
        assert result.status is ConnectorStatus.LIVE
        assert result.payload.provenance.evidence.endpoint == "relay.example.test"
        assert result.payload.provenance.evidence.transport == "smtp"

    def test_a_refused_message_is_unavailable_and_retryable(self, connector_db, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")

        def boom(host, port, timeout=None):
            raise OSError("connection refused")

        monkeypatch.setattr(smtplib, "SMTP", boom)
        result = boundary.execute(
            EmailTransportConnector(),
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"]}),
        )
        assert result.status is ConnectorStatus.UNAVAILABLE
        assert result.error.kind == "transport_failure" and result.error.retryable

    def test_an_unrecognised_receipt_is_a_failure_not_a_claimed_delivery(self, connector_db):
        connector = EmailTransportConnector()
        connector._delivery_module = lambda: type(
            "Stub", (), {"send": staticmethod(lambda *a, **k: "who knows what happened")}
        )
        result = connector.fetch(
            ConnectorRequest("send", {"subject": "s", "body": "b", "to": ["a@b.test"]})
        )
        assert result.error.kind == "malformed_payload"
        assert "unknown" in result.error.reason

    def test_a_send_with_no_recipient_is_refused_before_anything_is_attempted(self, connector_db):
        result = EmailTransportConnector().fetch(ConnectorRequest("send", {"subject": "s"}))
        assert result.error.kind == "malformed_payload"

    def test_an_operation_it_does_not_implement_is_refused_rather_than_ignored(self, connector_db):
        result = EmailTransportConnector().fetch(ConnectorRequest("read_inbox"))
        assert result.error.kind == "provider_error"

    def test_the_relay_host_is_named_as_the_provider_when_configured(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_SMTP_HOST", "relay.example.test")
        assert EmailTransportConnector().identity().provider_id == "relay.example.test"

    def test_it_calls_the_existing_transport_rather_than_reimplementing_it(self, connector_db, monkeypatch):
        from cin_lite import email_delivery

        calls = []
        monkeypatch.setattr(
            email_delivery, "send",
            lambda subject, body, to, fallback_id: calls.append((subject, to)) or "not sent (SMTP not configured); written to /x",
        )
        EmailTransportConnector().fetch(
            ConnectorRequest("send", {"subject": "hello", "body": "b", "to": ["a@b.test"]})
        )
        assert calls == [("hello", ["a@b.test"])]


class TestAccountingWrapsTheExistingExport:
    def test_a_local_export_is_manual_not_live_and_not_unconfigured(self, connector_db, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_ACCOUNTING_EXPORT_DIR", str(tmp_path / "export"))
        result = boundary.execute(
            AccountingConnector(),
            ConnectorRequest("export_settlement", {"settlement": {
                "settlement_id": "STL-1", "load_id": "L-1", "invoice_amount": 1200.0,
            }}),
        )
        assert result.status is ConnectorStatus.MANUAL
        assert result.payload.data["posted_to_accounting_system"] is False
        assert (tmp_path / "export" / "STL-1.json").is_file()

    def test_the_manual_label_travels_into_the_rendering(self, connector_db, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_ACCOUNTING_EXPORT_DIR", str(tmp_path / "export"))
        result = AccountingConnector().fetch(
            ConnectorRequest("export_settlement", {"settlement": {"settlement_id": "STL-2"}})
        )
        assert result.payload.to_display_dict()["connector_status"] == "MANUAL"

    def test_an_export_without_a_settlement_id_is_refused(self, connector_db):
        result = AccountingConnector().fetch(
            ConnectorRequest("export_settlement", {"settlement": {}})
        )
        assert result.error.kind == "malformed_payload"

    def test_a_failed_write_is_unavailable_rather_than_silently_lost(self, connector_db, monkeypatch):
        connector = AccountingConnector()
        connector._export_module = lambda: type(
            "Stub", (), {"export_settlement": staticmethod(
                lambda settlement: {"status": "export_failed", "error": "read-only volume"}
            )},
        )
        result = connector.fetch(
            ConnectorRequest("export_settlement", {"settlement": {"settlement_id": "STL-3"}})
        )
        assert result.status is ConnectorStatus.UNAVAILABLE
        assert result.error.kind == "transport_failure"

    def test_any_other_operation_is_unconfigured(self, connector_db):
        result = AccountingConnector().fetch(ConnectorRequest("post_invoice"))
        assert result.status is ConnectorStatus.UNCONFIGURED


class TestLoadBoardRefusesToLaunderSampleData:
    def test_fetch_loads_refuses_rather_than_returning_samples(self, connector_db):
        result = boundary.execute(LoadBoardConnector(), ConnectorRequest("fetch_loads"))
        assert result.status is ConnectorStatus.UNCONFIGURED
        assert "will not present local sample files as market offers" in result.error.reason

    def test_sample_loads_returns_the_same_records_labelled_simulated(self, connector_db):
        result = boundary.execute(LoadBoardConnector(), ConnectorRequest("sample_loads"))
        assert result.status is ConnectorStatus.SIMULATED
        assert "none of them can be booked" in result.payload.data["note"]
        assert result.payload.data["offer_count"] == len(result.payload.data["offers"])

    def test_the_samples_come_from_the_existing_acquisition_layer(self, connector_db, tmp_path, monkeypatch):
        source = tmp_path / "loads"
        source.mkdir()
        (source / "one.json").write_text('{"load_id": "SAMPLE-1", "origin": "Jacksonville, FL"}')
        monkeypatch.setenv("DISPATCH_LOAD_SOURCE", str(source))
        result = LoadBoardConnector().fetch(ConnectorRequest("sample_loads"))
        assert [o["load_id"] for o in result.payload.data["offers"]] == ["SAMPLE-1"]

    def test_an_unknown_operation_is_refused(self, connector_db):
        result = LoadBoardConnector().fetch(ConnectorRequest("book_load"))
        assert result.status is ConnectorStatus.UNCONFIGURED


class TestOutlookStaysTheSchedulingSourceOfTruth:
    def test_reading_the_schedule_refuses_without_inventing_one(self, connector_db):
        result = boundary.execute(OutlookConnector(), ConnectorRequest("read_schedule"))
        assert result.status is ConnectorStatus.UNCONFIGURED
        assert "does not keep one" in result.error.reason

    def test_event_creation_without_a_human_is_refused_before_configuration(self, connector_db):
        result = OutlookConnector().fetch(ConnectorRequest("request_event_creation"))
        assert result.error.kind == "not_authorized"
        assert result.status is ConnectorStatus.ABSENT

    def test_a_system_identity_cannot_authorize_a_calendar_event(self, connector_db):
        result = OutlookConnector().fetch(
            ConnectorRequest("request_event_creation", {"authorized_by": "AUTOMATION"})
        )
        assert result.error.kind == "not_authorized"
        assert "system identity" in result.error.reason

    def test_an_asserted_authorization_without_a_reference_is_refused(self, connector_db):
        result = OutlookConnector().fetch(
            ConnectorRequest("request_event_creation", {"authorized_by": "mike"})
        )
        assert result.error.kind == "not_authorized"
        assert "never manufactures an approval attribution" in result.error.reason

    def test_a_fully_authorized_request_still_creates_nothing(self, connector_db):
        result = OutlookConnector().fetch(
            ConnectorRequest("request_event_creation", {
                "authorized_by": "mike", "authorization_reference": "APPROVAL-123",
            })
        )
        assert result.status is ConnectorStatus.UNCONFIGURED
        assert "Nothing has been scheduled anywhere" in result.error.reason

    def test_an_unknown_operation_lists_the_ones_that_exist(self, connector_db):
        result = OutlookConnector().fetch(ConnectorRequest("write_calendar"))
        assert "read_schedule" in result.error.reason

    def test_it_declares_no_capability_to_hold_scheduling_truth(self):
        declared = " ".join(OutlookConnector().capabilities().produces).lower()
        assert "read-only" in declared
        assert "scheduling truth" in OutlookConnector().capabilities().never


# ── the Route Risk evaluation layer ───────────────────────────────────


class TestRouteRiskEvaluationLayer:
    def test_the_reference_evaluator_satisfies_the_interface(self):
        assert isinstance(AdvisoryRouteRiskEvaluator(), RouteRiskEvaluator)

    def test_an_assessment_carries_the_status_of_the_data_it_judged(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request(load_id="L-2"))
        assessment = AdvisoryRouteRiskEvaluator().evaluate(result.payload)
        assert assessment.status is ConnectorStatus.SIMULATED
        assert assessment.to_display_dict()["connector_status"] == "SIMULATED"

    def test_a_structural_condition_raises_the_consequence_level(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assessment = AdvisoryRouteRiskEvaluator().evaluate(result.payload)
        by_kind = {f.condition_kind: f for f in assessment.findings}
        assert by_kind["weather"].consequence_level == 3          # "warning"
        assert by_kind["road_restrictions"].consequence_level == 3  # "advisory" + structural

    def test_an_empty_collection_produces_a_zero_assessment_not_a_guess(self):
        payload = NormalizedPayload(
            Provenance("route_risk", "p", ConnectorStatus.SIMULATED),
            "route_risk_conditions",
            normalize_conditions(()),
        )
        assessment = AdvisoryRouteRiskEvaluator().evaluate(payload)
        assert assessment.consequence_level == 0
        assert assessment.findings == ()
        assert assessment.stakeholder_communication_input == ""

    def test_an_assessment_is_advisory_and_cannot_be_made_otherwise(self):
        with pytest.raises(ValueError, match="advisory"):
            RouteRiskAssessment(status=ConnectorStatus.SIMULATED, advisory=False)

    def test_an_assessment_has_no_field_that_could_accept_or_cancel_a_load(self):
        fields = set(RouteRiskAssessment(status=ConnectorStatus.SIMULATED).to_display_dict())
        assert not fields & {"accept", "cancel", "new_status", "load_update", "booked"}

    def test_a_consequence_level_outside_zero_to_five_is_refused(self):
        with pytest.raises(ValueError, match="outside 0-5"):
            RouteRiskFinding("weather", "", "", 9, "too much")

    def test_a_condition_class_outside_section_6_5_is_refused(self):
        with pytest.raises(ValueError, match="not a Route Risk condition class"):
            RouteCondition(kind="astrology", summary="mercury retrograde")

    def test_a_condition_needs_a_human_readable_summary(self):
        with pytest.raises(ValueError, match="summary a human can read"):
            RouteCondition(kind="weather", summary="")

    def test_the_event_translation_carries_the_status_into_the_stored_text(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request())
        assessment = AdvisoryRouteRiskEvaluator().evaluate(result.payload)
        kwargs = assessment_to_event_kwargs(
            assessment, load_id="L-3", source_label="Mock Route Risk Connector"
        )
        assert kwargs["condition_summary"].startswith("[SIMULATED]")
        assert kwargs["source_label"].endswith("[SIMULATED]")
        assert kwargs["consequence_level"] == 3

    def test_the_event_translation_of_an_empty_assessment_says_so(self):
        assessment = RouteRiskAssessment(status=ConnectorStatus.SIMULATED)
        kwargs = assessment_to_event_kwargs(assessment, load_id="L-4", source_label="mock")
        assert "No route conditions reported" in kwargs["condition_summary"]

    def test_evaluation_inputs_is_the_single_accessor_for_the_payload_body(self, connector_db):
        result = boundary.execute(MockRouteRiskConnector(), _request(load_id="L-5"))
        assert evaluation_inputs(result.payload)["load_id"] == "L-5"

    def test_the_route_risk_connector_refuses_rather_than_reporting_a_clear_road(self, connector_db):
        result = boundary.execute(registry.get("route_risk"), _request())
        assert result.status is ConnectorStatus.UNCONFIGURED
        assert result.payload is None
        assert "Internal and manual Route Risk events" in result.error.reason


# ── Section 6.7: resilience ───────────────────────────────────────────


class TestCoreOperationSurvivesEveryConnectorBeingUnconfigured:
    """Section 6.7's proof: the local operating path completes regardless."""

    def test_create_assign_milestone_evidence_deliver_with_nothing_connected(self, connector_db):
        board = registry.status_board()
        assert {row["connector_status"] for row in board} == {"UNCONFIGURED"}

        load = services.create_load(
            customer="Level 1 Transport",
            pickup_location="Jacksonville, FL",
            delivery_location="Atlanta, GA",
        )
        driver = services.create_driver(name="A Driver", phone="904-555-0100")
        services.assign_driver(load["load_id"], driver["driver_id"])

        for event in [
            "dispatched", "en_route_pickup", "arrived_pickup", "loaded",
            "departed_pickup", "arrived_delivery", "delivered",
        ]:
            milestone = services.add_milestone(load["load_id"], event_type=event)
            assert "status_transition_refused" not in milestone

        evidence = services.attach_evidence(
            load["load_id"],
            evidence_type="pod",
            description="Signed delivery receipt",
            file_data=b"%PDF-1.4 signed",
            original_filename="pod.pdf",
            uploaded_by="a-driver",
        )

        final = services.get_load(load["load_id"])
        assert final["status"] == "delivered"
        assert services.list_evidence(load["load_id"])[0]["evidence_id"] == evidence["evidence_id"]
        assert services.get_visibility(load["load_id"])["current_status"] == "delivered"

        # And the connectors are still exactly as honest afterwards.
        assert {row["connector_status"] for row in registry.status_board()} == {"UNCONFIGURED"}

    def test_a_function_that_needs_a_connector_refuses_loudly(self, connector_db):
        """Not a silent degradation: the refusal names the connector and the status."""
        result = boundary.execute(registry.get("mapping"), ConnectorRequest("fetch_distance"))
        with pytest.raises(ConnectorRefusal) as caught:
            require_payload(result)
        message = str(caught.value)
        assert "Mapping and Routing Connector" in message
        assert "UNCONFIGURED" in message
        assert "DISPATCH_MAPPING_API_URL" in message

    def test_an_unavailable_connector_does_not_stop_a_load_being_delivered(self, connector_db):
        load = services.create_load(customer="Level 1 Transport")
        failure = boundary.execute(
            MockRouteRiskConnector(failure_mode="timeout"),
            ConnectorRequest("fetch_conditions", max_attempts=2),
        )
        assert failure.status is ConnectorStatus.UNAVAILABLE

        services.add_milestone(load["load_id"], event_type="dispatched")
        services.add_milestone(load["load_id"], event_type="en_route_pickup")
        assert services.get_load(load["load_id"])["status"] == "en_route_pickup"
