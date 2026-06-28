from core.utils.logger import log
from core.agents.cin_router import CINRouter


class HybridResult:
    def __init__(self, sam, vendor_network, cyber):
        self.sam = sam
        self.vendor_network = vendor_network
        self.cyber = cyber

    def to_dict(self):
        return {
            "sam": self.sam,
            "vendor_network": self.vendor_network,
            "cyber": self.cyber,
        }


class HybridLifecycle:
    def __init__(self, data_client):
        # Phase 3: Hybrid uses the Phase 2 CINRouter
        self.router = CINRouter(data_client)

    def run(self, vendor_id: str) -> HybridResult:
        """
        Phase 3 lifecycle:
        - calls each engine explicitly through dispatch()
        - merges results into HybridResult
        """
        log(f"HybridLifecycle: run vendor_id={vendor_id}")

        sam = self.router.dispatch("sam", "ingest", {"vendor_id": vendor_id})
        vendor_network = self.router.dispatch("vendor", "analyze", {"vendor_id": vendor_id})
        cyber = self.router.dispatch("cyber", "check", {"vendor_id": vendor_id})

        return HybridResult(
            sam=sam,
            vendor_network=vendor_network,
            cyber=cyber,
        )
