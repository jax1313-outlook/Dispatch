from core.utils.logger import log


class HybridSummary:
    """
    Phase 3: Minimal summary aggregator.
    - normalizes raw engine outputs
    - merges into unified summary dict
    - prepares structure for Phase 4 scoring and CIN routing
    """

    def __init__(self):
        pass

    def build(self, hybrid_result: dict) -> dict:
        """
        Accepts HybridResult.to_dict() output and produces a unified summary.
        """
        log("HybridSummary.build: aggregating hybrid result")

        sam = hybrid_result.get("sam", {})
        vendor = hybrid_result.get("vendor_network", {})
        cyber = hybrid_result.get("cyber", {})

        summary = {
            "vendor_id": sam.get("vendor_id") or vendor.get("vendor_id") or cyber.get("vendor_id"),

            "sam": {
                "status": sam.get("sam_status"),
                "opportunities": sam.get("opportunities", []),
            },

            "vendor_network": {
                "status": vendor.get("network_status"),
                "relationships": vendor.get("relationships", []),
            },

            "cyber": {
                "status": cyber.get("cyber_status"),
                "score": cyber.get("score"),
            },

            # Phase 3 WIP: placeholder for Phase 4 scoring + CIN routing
            "overall_assessment": "WIP",
        }

        return summary
