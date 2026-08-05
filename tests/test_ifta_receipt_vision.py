"""Tests for Phase 6b: vision-assisted fuel-receipt pre-fill. Follows
Dispatch's own established Claude-agent pattern (cin_lite/agents/
extractor.py) and its existing fake-anthropic test fixture, not a port
of Hold's separate ClaudeVisionExtractor test setup. Per
DISPATCH_IFTA_PHASE6B_RECEIPT_VISION_PREFILL_LAUNCH_PACKAGE_v1."""

from __future__ import annotations

import io
import json

import pytest

from cin_lite.agents import receipt_vision
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


_GOOD_RESULT = json.dumps({
    "vendor_name": "Pilot Travel Center",
    "vendor_address": "123 Main St, Amarillo, TX 79101",
    "purchase_date": "2025-01-16",
    "gallons": 52.3,
    "amount": 184.15,
    "extraction_confidence": 0.91,
})


class TestExtractFuelReceipt:
    def test_no_api_key_returns_unavailable(self):
        result = receipt_vision.extract_fuel_receipt(b"fake image bytes", "receipt.jpg")
        assert result == {"available": False, "reason": "no API key configured"}

    def test_unsupported_extension_returns_unavailable(self, install_anthropic):
        install_anthropic(_GOOD_RESULT)
        result = receipt_vision.extract_fuel_receipt(b"fake bytes", "receipt.pdf")
        assert result["available"] is False
        assert "unsupported image type" in result["reason"]

    def test_successful_extraction(self, install_anthropic):
        install_anthropic(_GOOD_RESULT)
        result = receipt_vision.extract_fuel_receipt(b"fake image bytes", "receipt.jpg")
        assert result["available"] is True
        assert result["vendor_name"] == "Pilot Travel Center"
        assert result["gallons"] == 52.3
        assert result["extraction_confidence"] == 0.91

    def test_api_failure_degrades_to_unavailable(self, install_anthropic):
        install_anthropic(RuntimeError("network unreachable"))
        result = receipt_vision.extract_fuel_receipt(b"fake image bytes", "receipt.jpg")
        assert result["available"] is False
        assert "network unreachable" in result["reason"]

    def test_malformed_json_response_degrades_to_unavailable(self, install_anthropic):
        install_anthropic("not valid json {{{")
        result = receipt_vision.extract_fuel_receipt(b"fake image bytes", "receipt.jpg")
        assert result["available"] is False

    def test_invalid_shape_response_degrades_to_unavailable(self, install_anthropic):
        install_anthropic(json.dumps({"vendor_name": "X"}))  # missing required keys
        result = receipt_vision.extract_fuel_receipt(b"fake image bytes", "receipt.jpg")
        assert result["available"] is False
        assert result["reason"] == "invalid extraction result"

    def test_never_raises(self, install_anthropic):
        """No matter what goes wrong, this returns a dict -- never an
        exception the caller has to catch."""
        install_anthropic(Exception("anything"))
        result = receipt_vision.extract_fuel_receipt(b"x", "receipt.jpg")
        assert isinstance(result, dict)
        assert result["available"] is False


class TestDeriveJurisdiction:
    def test_finds_state_code_token(self):
        assert receipt_vision.derive_jurisdiction("123 Main St, Amarillo, TX 79101") == "TX"

    def test_no_match_returns_none(self):
        assert receipt_vision.derive_jurisdiction("123 Main St, Nowhereville, ZZ 00000") is None

    def test_none_input_returns_none(self):
        assert receipt_vision.derive_jurisdiction(None) is None

    def test_empty_string_returns_none(self):
        assert receipt_vision.derive_jurisdiction("") is None

    def test_substring_is_not_a_false_positive(self):
        """'CAMP' contains 'CA' but is not the token 'CA' -- must not match."""
        assert receipt_vision.derive_jurisdiction("CAMP Road, Somewhereton") is None

    def test_canadian_province_code_matches(self):
        assert receipt_vision.derive_jurisdiction("456 King St, Toronto, ON M5V 1A1") == "ON"


class TestExtractReceiptRoute:
    def test_no_file_400(self, client):
        resp = client.post("/api/dispatch/ifta/fuel-purchases/extract-receipt", data={})
        assert resp.status_code == 400

    def test_no_api_key_returns_200_unavailable(self, client):
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases/extract-receipt",
            data={"file": (io.BytesIO(b"fake image"), "receipt.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["available"] is False

    def test_successful_extraction_includes_derived_jurisdiction(self, client, install_anthropic):
        install_anthropic(_GOOD_RESULT)
        resp = client.post(
            "/api/dispatch/ifta/fuel-purchases/extract-receipt",
            data={"file": (io.BytesIO(b"fake image"), "receipt.jpg")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["available"] is True
        assert data["jurisdiction"] == "TX"

    def test_extract_creates_no_fuel_purchase(self, client, install_anthropic):
        """This is a pre-fill lookup only -- confirmed by checking nothing
        was persisted after calling it."""
        install_anthropic(_GOOD_RESULT)
        client.post(
            "/api/dispatch/ifta/fuel-purchases/extract-receipt",
            data={"file": (io.BytesIO(b"fake image"), "receipt.jpg")},
            content_type="multipart/form-data",
        )
        listing = client.get(
            "/api/dispatch/ifta/fuel-purchases?date_from=2020-01-01&date_to=2030-01-01"
        ).get_json()
        assert listing == []


class TestFullPrefillThenSaveFlow:
    """Mirrors the UI's actual sequence: scan -> dispatcher reviews ->
    create purchase -> attach the same scanned image as its receipt --
    proving the two existing, independently-tested endpoints (extract,
    then Phase 5's attach-evidence) compose correctly end to end."""

    def test_scan_then_create_then_attach(self, client, install_anthropic):
        install_anthropic(_GOOD_RESULT)
        scan = client.post(
            "/api/dispatch/ifta/fuel-purchases/extract-receipt",
            data={"file": (io.BytesIO(b"fake image"), "receipt.jpg")},
            content_type="multipart/form-data",
        ).get_json()
        assert scan["available"] is True

        created = client.post(
            "/api/dispatch/ifta/fuel-purchases",
            json={
                "jurisdiction": scan["jurisdiction"],
                "gallons": scan["gallons"],
                "amount": scan["amount"],
                "date": scan["purchase_date"],
                "vendor": scan["vendor_name"],
            },
        ).get_json()
        assert created["jurisdiction"] == "TX"

        attach = client.post(
            f"/api/dispatch/ifta/fuel-purchases/{created['purchase_id']}/evidence",
            data={"file": (io.BytesIO(b"fake image"), "receipt.jpg")},
            content_type="multipart/form-data",
        )
        assert attach.status_code == 201
        assert attach.get_json()["evidence"]["purchase_id"] == created["purchase_id"]
