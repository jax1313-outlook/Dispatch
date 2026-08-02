"""Tests for the intelligence extraction agent (deterministic + Claude code path)."""

from __future__ import annotations

import json

from cin_lite.agents import extractor


def _shape_ok(result: dict) -> bool:
    return (
        isinstance(result.get("strategic_assessment"), str)
        and result["strategic_assessment"]
        and isinstance(result.get("cross_module_findings"), list)
        and isinstance(result.get("competitive_factors"), list)
        and result.get("risk_level") in extractor.RISK_LEVELS
        and result.get("pursuit_readiness") in extractor.READINESS_VALUES
    )


def test_deterministic_shape(mapped_contract, intelligence, flags):
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert _shape_ok(result)


def test_deterministic_includes_set_aside(mapped_contract, intelligence, flags):
    result = extractor.extract(mapped_contract, intelligence, flags)
    findings_text = " ".join(f["finding"] for f in result["cross_module_findings"])
    assert "set-aside" in findings_text.lower() or "Set-aside" in findings_text


def test_deterministic_competitive_factors(mapped_contract, intelligence, flags):
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert isinstance(result["competitive_factors"], list)


def test_clean_contract_not_ready(clean_contract):
    from cin_lite import processing
    intel = processing.process(clean_contract)
    flags = processing.all_flags(intel)
    result = extractor.extract(clean_contract, intel, flags)
    assert _shape_ok(result)
    assert result["pursuit_readiness"] in ("conditional", "not_ready")


def test_claude_success_path(mapped_contract, intelligence, flags, install_anthropic):
    canned = {
        "strategic_assessment": "Strong 8(a) opportunity with moderate cyber burden.",
        "cross_module_findings": [
            {"finding": "Set-aside + NAICS alignment", "modules": ["set_aside_detection", "naics_sin_extraction"], "implication": "Qualifies for pursuit."}
        ],
        "competitive_factors": ["Limited pool due to set-aside"],
        "risk_level": "moderate",
        "pursuit_readiness": "ready",
    }
    install_anthropic(json.dumps(canned))
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert result["strategic_assessment"] == "Strong 8(a) opportunity with moderate cyber burden."
    assert result["risk_level"] == "moderate"


def test_claude_failure_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic(RuntimeError("api down"))
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert _shape_ok(result)


def test_claude_invalid_json_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic("not json")
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert _shape_ok(result)


def test_claude_invalid_risk_level_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    bad = {
        "strategic_assessment": "ok",
        "cross_module_findings": [],
        "competitive_factors": [],
        "risk_level": "INVALID",
        "pursuit_readiness": "ready",
    }
    install_anthropic(json.dumps(bad))
    result = extractor.extract(mapped_contract, intelligence, flags)
    assert result["risk_level"] in extractor.RISK_LEVELS


def test_competitive_factors_from_vendor_and_sub(mapped_contract, intelligence, flags):
    """Verify the extractor picks up vendor limited_competition and subcontracting signals."""
    result = extractor.extract(mapped_contract, intelligence, flags)
    factors_text = " ".join(result["competitive_factors"]).lower()
    assert "sole-source" in factors_text or "limited-competition" in factors_text
    assert "subcontracting" in factors_text


def test_competitive_factors_jv_mp(mapped_contract, intelligence, flags):
    result = extractor.extract(mapped_contract, intelligence, flags)
    factors_text = " ".join(result["competitive_factors"]).lower()
    assert "jv" in factors_text or "mentor" in factors_text
