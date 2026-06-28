from core.utils.logger import log
from core.agents.hybrid_lifecycle import HybridLifecycle
from core.agents.hybrid_summary import HybridSummary


class HybridOrchestrator:
    """
    Phase 3: Minimal orchestrator for Hybrid.
    - constructs HybridLifecycle
    - constructs HybridSummary
    - exposes run(vendor_id)
    - returns unified summary dict
    """

    def __init__(self, data_client):
        self.lifecycle = HybridLifecycle(data_client)
        self.summary = HybridSummary()

    def run(self, vendor_id: str) -> dict:
        log(f"HybridOrchestrator: run vendor_id={vendor_id}")

        # Phase 3: run lifecycle → raw result dict
        raw_result = self.lifecycle.run(vendor_id).to_dict()

        # Phase 3: build unified summary
        unified = self.summary.build(raw_result)

        return unified
