"""Integration and end-to-end tests for the full CIN-Lite pipeline.

Verifies that all layers compose correctly: acquisition -> processing ->
agent summarization/routing -> control rendering -> archive + email delivery.
Also tests the dispatch subsystem integration and cross-module data flow.
"""

from __future__ import annotations

import json

from cin_lite import acquisition, processing, archive, control, email_delivery
from cin_lite.agents.summarizer import SummarizerAgent
from cin_lite.agents.router import RouterAgent
from cin_lite.agents.manager import AgentManager
from cin_lite.workflows import proposal


class TestEndToEndPipeline:
    """Full pipeline: acquire -> process -> summarize -> route -> control -> archive."""

    def test_full_pipeline_local_data(self, tmp_archive):
        contracts = acquisition.acquire()
        assert contracts

        with AgentManager() as mgr:
            mgr.register(SummarizerAgent())
            mgr.register(RouterAgent())
            mgr.initialize_all({})

            for contract in contracts:
                intelligence = processing.process(contract)
                flags = processing.all_flags(intelligence)

                summary = mgr.execute("summarizer", {
                    "contract": contract,
                    "intelligence": intelligence,
                    "flags": flags,
                })
                assert isinstance(summary, str) and summary

                decision = mgr.execute("router", {
                    "contract": contract,
                    "intelligence": intelligence,
                    "summary": summary,
                    "flags": flags,
                })
                assert decision["action"] in control.ACTIONS
                assert decision["priority"]
                assert decision["reason"]

                email = control.render_email(contract, intelligence, summary, flags, decision)
                assert contract.get("title", "") in email or "None" in email

                metadata = archive.store(contract, intelligence, summary)
                assert metadata["contract_id"].startswith("CIN-")

                action = decision["action"]
                label, route = control.resolve(action)
                routing_path = archive.record_routing(
                    metadata["contract_id"], action, route, metadata, decision
                )
                assert routing_path.exists()

                email_status = email_delivery.deliver_decision(
                    contract, metadata["contract_id"], summary, decision,
                    action, route, flags,
                )
                assert isinstance(email_status, str)

    def test_pipeline_with_proposal_trigger(self, tmp_archive, mapped_contract, intelligence, flags):
        with AgentManager() as mgr:
            mgr.register(SummarizerAgent())
            mgr.register(RouterAgent())
            mgr.initialize_all({})

            summary = mgr.execute("summarizer", {
                "contract": mapped_contract,
                "intelligence": intelligence,
                "flags": flags,
            })
            decision = mgr.execute("router", {
                "contract": mapped_contract,
                "intelligence": intelligence,
                "summary": summary,
                "flags": flags,
            })

            metadata = archive.store(mapped_contract, intelligence, summary)
            action = decision["action"]

            if proposal.is_triggered(action):
                label, route = control.resolve(action)
                result = proposal.trigger(
                    mapped_contract, metadata["contract_id"],
                    intelligence, decision, summary, flags,
                )
                assert result["proposal_id"].startswith("PROP-")
                assert result["json_path"].exists()
                assert result["outline_path"].exists()


class TestCrossModuleDataFlow:
    """Verify that data flows correctly between modules."""

    def test_sam_mapping_feeds_all_rules(self, sam_opportunity):
        contract = acquisition._map_opportunity(sam_opportunity, api_key="FAKE", fetch_desc=True)
        intelligence = processing.process(contract)

        assert len(intelligence) == 9
        for name, result in intelligence.items():
            assert "flags" in result, f"{name} missing flags"
            assert "findings" in result, f"{name} missing findings"

    def test_flags_propagate_to_routing(self, mapped_contract, intelligence, flags):
        decision = RouterAgent()
        decision.initialize({})
        result = decision.execute({
            "contract": mapped_contract,
            "intelligence": intelligence,
            "summary": "test",
            "flags": flags,
        })
        decision.shutdown()

        assert result["action"] in control.ACTIONS
        if "value_below_band" in flags or "value_above_band" in flags:
            assert result["action"] == "flag_review"

    def test_control_email_reflects_all_scored_modules(self, mapped_contract, intelligence, flags):
        decision = {"action": "approve_proposal", "priority": "high",
                    "recipient": "proposal-team", "reason": "fit", "notes": "n"}
        email = control.render_email(mapped_contract, intelligence, "summary", flags, decision)

        for scored in ("vendor_network_indicators", "past_performance_relevance",
                       "subcontractor_dominance", "jv_mp_structure",
                       "foreign_influence_indicators"):
            assert scored in email

    def test_archive_stores_complete_bundle(self, tmp_archive, mapped_contract, intelligence):
        summary = "integration test summary"
        metadata = archive.store(mapped_contract, intelligence, summary)

        raw_path = archive.ARCHIVE_ROOT / "Raw"
        processed_path = archive.ARCHIVE_ROOT / "Processed"
        intel_path = archive.ARCHIVE_ROOT / "Intelligence"
        summary_path = archive.ARCHIVE_ROOT / "Summaries"

        assert raw_path.exists()
        assert processed_path.exists()
        assert intel_path.exists()
        assert summary_path.exists()

        cid = metadata["contract_id"]
        intel_file = intel_path / f"{cid}.json"
        saved_intel = json.loads(intel_file.read_text(encoding="utf-8"))
        assert set(saved_intel) == set(intelligence)


class TestDispatchIntegration:
    """Verify the dispatch subsystem works end-to-end."""

    def test_dispatch_router_end_to_end(self):
        from cin_lite.dispatch.dispatch_router import dispatch_load

        load = {
            "rate": 2500,
            "miles": 800,
            "weight": 35000,
            "equipment": "dry_van",
        }
        decision = dispatch_load(load)
        assert decision.action in ("accept", "reject", "flag_review")
        assert decision.priority in ("low", "medium", "high")
        assert isinstance(decision.score, int)
        assert isinstance(decision.to_json(), dict)

    def test_dispatch_invalid_load(self):
        from cin_lite.dispatch.dispatch_router import dispatch_load

        load = {"rate": -5, "miles": 0, "weight": 0}
        decision = dispatch_load(load)
        assert decision.action == "reject"


class TestEdgeCases:
    """Edge cases that cross module boundaries."""

    def test_empty_contract_survives_pipeline(self):
        contract = {}
        intelligence = processing.process(contract)
        flags = processing.all_flags(intelligence)
        assert isinstance(flags, list)
        assert len(intelligence) == 9

    def test_minimal_contract_survives_pipeline(self, tmp_archive):
        contract = {"title": "Minimal"}
        intelligence = processing.process(contract)
        flags = processing.all_flags(intelligence)
        summary = SummarizerAgent()
        summary.initialize({})
        result = summary.execute({
            "contract": contract,
            "intelligence": intelligence,
            "flags": flags,
        })
        summary.shutdown()
        assert isinstance(result, str)

        metadata = archive.store(contract, intelligence, result)
        assert metadata["contract_id"].startswith("CIN-")

    def test_contract_with_all_none_fields(self):
        contract = {
            "title": None,
            "agency": None,
            "solicitation_number": None,
            "naics_text": None,
            "description": None,
            "estimated_value": None,
            "response_date": None,
            "notes": None,
        }
        intelligence = processing.process(contract)
        flags = processing.all_flags(intelligence)
        assert "value_missing" in flags
