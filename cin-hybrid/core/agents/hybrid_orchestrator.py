from core.intel.intelligence_owner import IntelligenceOwner
from core.agents.hybrid_lifecycle import HybridLifecycle
from core.agents.hybrid_summary import HybridSummary
from core.intel.hybrid_intelligence import HybridIntelligence
from core.utils.logger import log


class HybridOrchestrator(IntelligenceOwner):
    """
    Sole owner of CIN-Hybrid intelligence.
    No other class may produce unified intelligence output.
    """

    def __init__(self, data_client, lifecycle_controller=None):
        self.data_client = data_client
        self.lifecycle = HybridLifecycle(data_client)
        self.lifecycle_controller = lifecycle_controller

        # Hard-wire ownership
        self._intelligence_owner = True

        log("HybridOrchestrator initialized as IntelligenceOwner")

    def run_intelligence(self, vendor_id: str) -> dict:
        """
        Full intelligence pipeline:
        - run engines
        - build summary
        - build intelligence
        - attach optional ops lifecycle state
        """

        if not self._intelligence_owner:
            raise RuntimeError("Intelligence ownership violation")

        log(f"HybridOrchestrator (IntelligenceOwner) running for vendor {vendor_id}")

        raw_result = self.lifecycle.run(vendor_id).to_dict()
        summary = HybridSummary().build(raw_result)
        intelligence_dict = HybridIntelligence().build(summary)

        if self.lifecycle_controller:
            intelligence_dict["ops_lifecycle_state"] = self.lifecycle_controller.state

        return intelligence_dict

    # Alias for compatibility
    def run(self, vendor_id: str) -> dict:
        return self.run_intelligence(vendor_id)
