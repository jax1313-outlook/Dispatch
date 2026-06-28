from core.intel.intelligence_api import get_intelligence
from core.intel.intelligence_owner import IntelligenceOwner


class HybridOps:
    def __init__(self, data_client):
        self.data_client = data_client

        # Phase-4 → Phase-3 wiring point
        self.intelligence_orchestrator = None

    def attach_intelligence_orchestrator(self, orchestrator: IntelligenceOwner):
        """
        Attach the Phase-3 IntelligenceOwner (HybridOrchestrator).
        """
        self.intelligence_orchestrator = orchestrator

    def get_vendor_intelligence(self, vendor_id: str) -> dict:
        """
        Retrieve unified CIN intelligence for a vendor via the orchestrator.
        """
        if not self.intelligence_orchestrator:
            raise RuntimeError("HybridOps: intelligence orchestrator not attached")

        return get_intelligence(self.intelligence_orchestrator, vendor_id)
