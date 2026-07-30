"""Tests for all nine deterministic rule modules + the SAM.gov mapping."""

from __future__ import annotations

import re

from cin_lite import acquisition, processing
from cin_lite.rules import ALL_RULES


# --------------------------------------------------------------------------- framework

def test_all_rules_registered():
    names = {m.NAME for m in ALL_RULES}
    assert names == {
        "set_aside_detection",
        "naics_sin_extraction",
        "pricing_anomaly",
        "cyber_compliance_readiness",
        "vendor_network_indicators",
        "past_performance_relevance",
        "subcontractor_dominance",
        "jv_mp_structure",
        "foreign_influence_indicators",
    }


# Modules that emit a human-readable summary (the descriptive/scored ones).
SUMMARY_MODULES = {
    "cyber_compliance_readiness",
    "vendor_network_indicators",
    "past_performance_relevance",
    "subcontractor_dominance",
    "jv_mp_structure",
    "foreign_influence_indicators",
}


def test_rule_result_shape_and_determinism(mapped_contract):
    for module in ALL_RULES:
        first = module.run(mapped_contract).to_json()
        second = module.run(mapped_contract).to_json()
        assert first == second, f"{module.NAME} is not deterministic"
        assert set(first) == {"module", "version", "flags", "findings", "summary", "score", "deterministic"}
        assert first["deterministic"] is True
        assert isinstance(first["summary"], str)
        assert isinstance(first["flags"], list) and first["flags"]
        if module.NAME in SUMMARY_MODULES:
            assert first["summary"], f"{module.NAME} should produce a summary"


# --------------------------------------------------------------------------- per-module (positive)

def test_set_aside(intelligence):
    f = intelligence["set_aside_detection"]
    assert "8(a)" in f["findings"]["set_asides"]
    assert "set_aside_present" in f["flags"]


def test_naics_sin(intelligence):
    f = intelligence["naics_sin_extraction"]["findings"]
    assert f["naics"] == ["541512", "541519"]
    assert "54151S" in f["sins"]


def test_pricing_anomaly(intelligence):
    f = intelligence["pricing_anomaly"]
    assert f["findings"]["estimated_value"] == 5000000
    assert "suspiciously_round" in f["flags"]


def test_cyber_compliance(intelligence):
    f = intelligence["cyber_compliance_readiness"]["findings"]
    assert f["cmmc_level"] == 2
    assert "CMMC" in f["frameworks"] and "NIST SP 800-171" in f["frameworks"]
    assert "cmmc_level_2_or_higher" in intelligence["cyber_compliance_readiness"]["flags"]


def test_vendor_network(intelligence):
    r = intelligence["vendor_network_indicators"]
    assert r["findings"]["network_risk"] == "elevated"
    assert r["score"] >= 6
    assert "limited_competition" in r["flags"]
    assert "vendor_concentration" in r["flags"]


def test_past_performance(intelligence):
    r = intelligence["past_performance_relevance"]
    assert r["findings"]["demand"] == "high"
    assert r["findings"]["requires_past_performance"] is True
    assert 3 in r["findings"]["recency_years"]
    assert "pp_high_demand" in r["flags"]


def test_subcontractor_dominance(intelligence):
    r = intelligence["subcontractor_dominance"]
    assert r["findings"]["subcontract_mentions"] >= 1
    assert r["findings"]["subcontracting_plan_required"] is True
    assert "subcontractor_dominance_signal" in r["flags"]


def test_jv_mp_structure(intelligence):
    f = intelligence["jv_mp_structure"]["findings"]
    assert f["joint_venture"] is True
    assert f["mentor_protege"] is True
    assert f["sba_approved"] is True
    assert "jv_mp_structure" in intelligence["jv_mp_structure"]["flags"]


def test_foreign_influence(intelligence):
    r = intelligence["foreign_influence_indicators"]
    assert "ITAR" in r["findings"]["export_control"]
    assert r["findings"]["us_persons_only"] is True
    assert "export_controlled" in r["flags"]
    assert r["findings"]["sensitivity"] in ("moderate", "elevated")


# --------------------------------------------------------------------------- per-module (negative)

def test_clean_contract_scores_zero(clean_contract):
    intel = processing.process(clean_contract)
    assert "no_vendor_network_signals" in intel["vendor_network_indicators"]["flags"]
    assert "no_past_performance_emphasis" in intel["past_performance_relevance"]["flags"]
    assert "no_subcontractor_dominance" in intel["subcontractor_dominance"]["flags"]
    assert "no_jv_mp_structure" in intel["jv_mp_structure"]["flags"]
    assert "no_foreign_influence_signals" in intel["foreign_influence_indicators"]["flags"]
    for module in ("vendor_network_indicators", "past_performance_relevance",
                   "subcontractor_dominance", "jv_mp_structure", "foreign_influence_indicators"):
        assert intel[module]["score"] == 0


def test_subcontractor_mitigations_zero_out():
    from cin_lite.rules import subcontractor_dominance

    contract = {
        "title": "IT",
        "description": "Subcontracting is permitted but Limitations on Subcontracting (52.219-14) "
        "apply and the prime must self-perform at least 50% of the cost.",
        "notes": "",
    }
    r = subcontractor_dominance.run(contract).to_json()
    assert r["score"] == 0
    assert "limitations_on_subcontracting" in r["flags"]


def test_foreign_influence_elevated():
    from cin_lite.rules import foreign_influence

    contract = {
        "title": "Defense",
        "description": "ITAR-controlled. Mitigate FOCI. Section 889 covered telecommunications "
        "prohibited. U.S. persons only; Secret clearance required.",
        "notes": "",
    }
    r = foreign_influence.run(contract).to_json()
    assert r["findings"]["sensitivity"] == "elevated"
    assert {"export_controlled", "foci_indicator", "section_889", "clearance_required"} <= set(r["flags"])


# --------------------------------------------------------------------------- acquisition mapping

def test_map_opportunity(sam_opportunity):
    c = acquisition._map_opportunity(sam_opportunity, api_key="FAKE", fetch_desc=True)
    assert c["solicitation_number"] == "FA8773-26-R-0007"
    assert c["agency"] == "DEPT OF DEFENSE.DEPT OF THE AIR FORCE.AFMC"
    assert c["naics_text"] == "NAICS 541512, 541519"
    assert c["estimated_value"] == 5000000
    assert c["notes"] == "8(a) Set-Aside (FAR 19.8)"
    assert c["_source_file"] == "sam.gov/TESTNOTICE001"
    assert c["point_of_contact"] == sam_opportunity["pointOfContact"]


def test_acquire_falls_back_to_local_without_key():
    # No CIN_LITE_SAM_API_KEY (scrubbed) -> local sample_data.
    contracts = acquisition.acquire()
    assert isinstance(contracts, list) and contracts
    assert all("title" in c for c in contracts)
