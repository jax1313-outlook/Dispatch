"""Tests for the Archive Layer."""

from __future__ import annotations

import json
import re

import pytest

from cin_lite import archive, processing
from cin_lite.pipeline import routing_history


def test_make_id_format_and_determinism(mapped_contract):
    a = archive.make_id(mapped_contract)
    b = archive.make_id(mapped_contract)
    assert a == b  # deterministic for the same contract
    assert re.fullmatch(r"CIN-\d{8}-[0-9A-F]{8}", a)


def test_make_id_differs_by_contract(mapped_contract, clean_contract):
    assert archive.make_id(mapped_contract) != archive.make_id(clean_contract)


def test_ensure_tree_creates_subdirs(tmp_archive):
    archive.ensure_tree()
    for sub in ("Raw", "Processed", "Intelligence", "Summaries", "Routing", "Pending", "Outbox"):
        assert (tmp_archive / sub).is_dir()


def test_store_writes_all_artifacts(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "the summary")
    cid = metadata["contract_id"]
    assert (tmp_archive / "Raw" / f"{cid}.json").exists()
    assert (tmp_archive / "Processed" / f"{cid}.json").exists()
    assert (tmp_archive / "Intelligence" / f"{cid}.json").exists()
    assert (tmp_archive / "Summaries" / f"{cid}.txt").read_text(encoding="utf-8") == "the summary"

    saved_intel = json.loads((tmp_archive / "Intelligence" / f"{cid}.json").read_text(encoding="utf-8"))
    assert "vendor_network_indicators" in saved_intel
    assert metadata["flag_count"] == sum(len(r["flags"]) for r in intelligence.values())


def test_record_routing_followed_true(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    decision = {"action": "approve_proposal", "priority": "high", "recipient": "proposal-team"}
    path = archive.record_routing(metadata["contract_id"], "approve_proposal",
                                  "PROPOSAL_QUEUE", metadata, decision)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["action"] == "approve_proposal"
    assert payload["followed_recommendation"] is True
    assert payload["recommendation"]["action"] == "approve_proposal"


def test_record_routing_followed_false(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    decision = {"action": "approve_proposal", "priority": "high", "recipient": "proposal-team"}
    path = archive.record_routing(metadata["contract_id"], "reject", "REJECTED", metadata, decision)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["followed_recommendation"] is False


def test_store_metadata_includes_value_and_deadline(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    assert "estimated_value" in metadata
    assert "response_date" in metadata


def test_record_routing_includes_label_flags_summary(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    decision = {"action": "reject", "priority": "low", "recipient": "none"}
    path = archive.record_routing(
        metadata["contract_id"], "reject", "REJECTED", metadata, decision,
        action_label="Reject", flags=["flag_a", "flag_b"], summary="The summary",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["action_label"] == "Reject"
    assert payload["flags"] == ["flag_a", "flag_b"]
    assert payload["summary"] == "The summary"


def test_store_proposal(tmp_archive):
    proposal = {"proposal_id": "PROP-TEST-1", "title": "X"}
    json_path, md_path = archive.store_proposal(proposal, "# Outline\n- a")
    assert json_path.exists() and md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["proposal_id"] == "PROP-TEST-1"
    assert md_path.read_text(encoding="utf-8") == "# Outline\n- a"


def test_store_persists_enriched_intelligence(tmp_archive, mapped_contract, intelligence):
    enriched = {"risk_level": "moderate", "pursuit_readiness": "ready",
                "strategic_assessment": "Good opportunity."}
    metadata = archive.store(mapped_contract, intelligence, "s", enriched=enriched)
    cid = metadata["contract_id"]
    saved = json.loads((tmp_archive / "Intelligence" / f"{cid}.json").read_text(encoding="utf-8"))
    assert saved["_enriched"]["risk_level"] == "moderate"
    assert saved["_enriched"]["strategic_assessment"] == "Good opportunity."


def test_store_without_enriched_has_no_key(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    saved = json.loads((tmp_archive / "Intelligence" / f"{cid}.json").read_text(encoding="utf-8"))
    assert "_enriched" not in saved


def test_list_contracts_empty(tmp_archive):
    assert archive.list_contracts() == []


def test_list_contracts_returns_metadata(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    contracts = archive.list_contracts()
    assert len(contracts) == 1
    assert contracts[0]["contract_id"] == metadata["contract_id"]
    assert contracts[0]["title"] == mapped_contract["title"]


def test_load_artifact_json(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    raw = archive.load_artifact("Raw", cid)
    assert raw["title"] == mapped_contract["title"]


def test_load_artifact_summary_txt(tmp_archive, mapped_contract, intelligence):
    archive.store(mapped_contract, intelligence, "the summary")
    cid = archive.make_id(mapped_contract)
    summary = archive.load_artifact("Summaries", cid)
    assert summary == "the summary"


def test_load_artifact_missing(tmp_archive):
    assert archive.load_artifact("Raw", "CIN-NOPE") is None


def test_writes_isolated_to_tmp(tmp_archive, mapped_contract, intelligence):
    archive.store(mapped_contract, intelligence, "s")
    assert str(tmp_archive).startswith(str(tmp_archive.parent))
    assert archive.ARCHIVE_ROOT == tmp_archive


# ── Content-hash verification (Phase 3) ─────────────────────────────


def test_store_writes_sha256_sidecars(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "the summary")
    cid = metadata["contract_id"]
    for subdir, ext in [("Raw", "json"), ("Processed", "json"), ("Intelligence", "json")]:
        sidecar = tmp_archive / subdir / f"{cid}.{ext}.sha256"
        assert sidecar.exists()
        recorded = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "sha256" in recorded and "written_at" in recorded
    summary_sidecar = tmp_archive / "Summaries" / f"{cid}.txt.sha256"
    assert summary_sidecar.exists()


def test_record_routing_writes_sidecar(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    decision = {"action": "approve_proposal", "priority": "high", "recipient": "team"}
    archive.record_routing(metadata["contract_id"], "approve_proposal", "PROPOSAL_QUEUE", metadata, decision)
    sidecar = tmp_archive / "Routing" / f"{metadata['contract_id']}.json.sha256"
    assert sidecar.exists()


def test_store_proposal_writes_sidecars(tmp_archive):
    proposal = {"proposal_id": "PROP-TEST-2", "title": "X"}
    json_path, md_path = archive.store_proposal(proposal, "# Outline\n- a")
    assert json_path.with_name(json_path.name + ".sha256").exists()
    assert md_path.with_name(md_path.name + ".sha256").exists()


def test_load_artifact_no_sidecar_reads_unchanged(tmp_archive, mapped_contract, intelligence):
    """Artifacts written before this feature (no sidecar) must still load
    exactly as before -- no retroactive enforcement."""
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    (tmp_archive / "Raw" / f"{cid}.json.sha256").unlink()
    raw = archive.load_artifact("Raw", cid)
    assert raw["title"] == mapped_contract["title"]


def test_load_artifact_matching_hash_reads_unchanged(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    raw = archive.load_artifact("Raw", cid)
    assert raw["title"] == mapped_contract["title"]


def test_load_artifact_corrupted_raises_and_escalates(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    raw_path = tmp_archive / "Raw" / f"{cid}.json"
    raw_path.write_text(json.dumps({"title": "TAMPERED"}), encoding="utf-8")

    with pytest.raises(archive.ArchiveIntegrityError):
        archive.load_artifact("Raw", cid)

    exception_files = list((tmp_archive / "Routing").glob(f"{cid}.integrity-exception-*.json"))
    assert len(exception_files) == 1
    payload = json.loads(exception_files[0].read_text(encoding="utf-8"))
    assert payload["route"] == "HUMAN_REVIEW"
    assert payload["flags"] == ["archive_integrity_mismatch"]
    assert payload["metadata"]["subdir"] == "Raw"


def test_integrity_exception_surfaces_in_human_review_queue(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    summary_path = tmp_archive / "Summaries" / f"{cid}.txt"
    summary_path.write_text("tampered summary", encoding="utf-8")

    with pytest.raises(archive.ArchiveIntegrityError):
        archive.load_artifact("Summaries", cid)

    queue = routing_history(route_filter="HUMAN_REVIEW")
    assert any(r["contract_id"] == cid and "archive_integrity_mismatch" in r["flags"] for r in queue)


def test_integrity_exception_does_not_overwrite_routing_record(tmp_archive, mapped_contract, intelligence):
    """The exact hazard this phase's design avoids: escalating a mismatch
    found in the Routing artifact itself must never overwrite the
    contract's real routing decision via record_routing()'s single
    per-contract file."""
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    decision = {"action": "approve_proposal", "priority": "high", "recipient": "team"}
    archive.record_routing(cid, "approve_proposal", "PROPOSAL_QUEUE", metadata, decision)

    routing_path = tmp_archive / "Routing" / f"{cid}.json"
    original_bytes = routing_path.read_bytes()
    routing_path.write_text(json.dumps({"tampered": True}), encoding="utf-8")

    with pytest.raises(archive.ArchiveIntegrityError):
        archive.load_artifact("Routing", cid)

    # The tampered file itself is left as found (this phase does not "heal"
    # or delete evidence); the escalation is a *separate* file.
    assert routing_path.read_bytes() != original_bytes  # still shows the tampering, untouched by us
    exception_files = list((tmp_archive / "Routing").glob(f"{cid}.integrity-exception-*.json"))
    assert len(exception_files) == 1


def test_list_contracts_verifies_processed_records(tmp_archive, mapped_contract, intelligence):
    metadata = archive.store(mapped_contract, intelligence, "s")
    cid = metadata["contract_id"]
    processed_path = tmp_archive / "Processed" / f"{cid}.json"
    processed_path.write_text(json.dumps({"tampered": True}), encoding="utf-8")

    with pytest.raises(archive.ArchiveIntegrityError):
        archive.list_contracts()
