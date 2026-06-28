from core.utils.logger import log
from core.agents.hybrid_lifecycle import HybridLifecycle
from core.agents.hybrid_summary import HybridSummary
from core.intel.hybrid_intelligence import HybridIntelligence


class HybridOrchestrator:
    """
    Phase 4: Orchestrator with intelligence layer.
    - lifecycle (Phase 3)
    - summary (Phase 3)
    - intelligence (Phase 4)
    """

    def __init__(self, data_client):
        self.lifecycle = HybridLifecycle(data_client)
        self.summary = HybridSummary()
        self.intel = HybridIntelligence()

    def run(self, vendor_id: str) -> dict:
        log(f"HybridOrchestrator: run vendor_id={vendor_id}")

        # Phase 3: lifecycle → raw result dict
        raw_result = self.lifecycle.run(vendor_id).to_dict()

        # Phase 3: summary
        summary = self.summary.build(raw_result)

        # Phase 4: intelligence
        intelligence = self.intel.build(summary)

        return intelligence
