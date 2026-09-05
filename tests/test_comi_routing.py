"""Tests for Workstream 1: COMI Routing Foundation."""

from __future__ import annotations

import pytest
from dispatch import services as dispatch_svc
from dispatch import comi_routing


def test_evaluate_comi_routing_route_risk_minor():
    res = dispatch_svc.evaluate_comi_routing(
        load_id="LOAD-101",
        trigger_type="route_risk_event",
        consequence_level=1,
    )
    assert res["load_id"] == "LOAD-101"
    assert res["trigger_type"] == "route_risk_event"
    assert res["consequence_level"] == 1
    assert "operations" in res["recipient_roles"]
    assert "driver" in res["recipient_roles"]
    assert res["driver_alert_required"] is True
    assert res["publisher_required"] is False
    assert res["stakeholder_update_required"] is False


def test_evaluate_comi_routing_route_risk_significant():
    res = dispatch_svc.evaluate_comi_routing(
        load_id="LOAD-102",
        trigger_type="route_risk_event",
        consequence_level=3,
    )
    assert res["consequence_level"] == 3
    assert "broker" in res["recipient_roles"]
    assert "customer" in res["recipient_roles"]
    assert res["publisher_required"] is True
    assert res["stakeholder_update_required"] is True
    assert res["recommended_channel"] == "publisher_draft"


def test_sanitize_payload_for_role_internal_role():
    payload = {
        "load_id": "LOAD-101",
        "internal_note": "Confidential driver notes",
        "profit": 450.00,
        "margin_pct": 22.5,
        "customer": "Acme Corp",
    }
    sanitized = comi_routing.sanitize_payload_for_role(payload, role="operations")
    assert sanitized["internal_note"] == "Confidential driver notes"
    assert sanitized["profit"] == 450.00
    assert sanitized["customer"] == "Acme Corp"


def test_sanitize_payload_for_role_external_roles():
    payload = {
        "load_id": "LOAD-101",
        "internal_note": "Confidential driver notes",
        "profit": 450.00,
        "margin_pct": 22.5,
        "recovery_word": "secret",
        "customer": "Acme Corp",
        "details": {
            "internal_score": 95,
            "pickup_location": "Atlanta, GA",
        },
    }

    for ext_role in ("broker", "customer", "driver", "shipper"):
        sanitized = comi_routing.sanitize_payload_for_role(payload, role=ext_role)
        assert "internal_note" not in sanitized
        assert "profit" not in sanitized
        assert "margin_pct" not in sanitized
        assert "recovery_word" not in sanitized
        assert sanitized["customer"] == "Acme Corp"
        assert "internal_score" not in sanitized["details"]
        assert sanitized["details"]["pickup_location"] == "Atlanta, GA"
