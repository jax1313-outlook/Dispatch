from core.utils.logger import log
from core.agents.hybrid_lifecycle import HybridLifecycle

class HybridOrchestrator:
    """
    Orchestrates Phase-3 intelligence engines and now optionally
    reports operational lifecycle state from HybridLifecycleController.
    """

    def __init__(self, data_client, lifecycle_controller=None):
        self.data_client = data_client
        self.lifecycle = HybridLifecycle(data_client)

        # NEW: optional operational lifecycle controller
        self.lifecycle_controller = lifecycle_controller

        log("HybridOrchestrator initialized")

    def run(self, vendor_id: str) -> dict:
        """
        Runs the Phase-3 engine pipeline and returns a unified dict.
        Optionally includes operational lifecycle state.
        """

        log(f"HybridOrchestrator running for vendor {vendor_id}")

        # Phase-3 engine runner (unchanged)
        raw_result = self.lifecycle.run(vendor_id).to_dict()

        # NEW: include operational lifecycle state if available
        if self.lifecycle_controller:
            raw_result["ops_lifecycle_state"] = self.lifecycle_controller.state

        return raw_result
