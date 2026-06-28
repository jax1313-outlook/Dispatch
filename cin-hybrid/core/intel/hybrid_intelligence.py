from core.utils.logger import log
from core.intel.cin_scoring import CINScoringModel


class HybridIntelligence:
    """
    Phase 4: Unified intelligence layer.
    - consumes HybridSummary output
    - applies CIN scoring
    - prepares structure for rule modules + CIN routing + GIE alignment
    """

    def __init__(self):
        self.scoring = CINScoringModel()

    def build(self, hybrid_summary: dict) -> dict:
        """
        Returns unified intelligence product:
        {
            "summary": {...},
            "scoring": {...},
            "intel_version": "phase4-wip"
        }
        """
        log("HybridIntelligence.build: generating intelligence product")

        scoring = self.scoring.score(hybrid_summary)

        return {
            "summary": hybrid_summary,
            "scoring": scoring,
            "intel_version": "phase4-wip",
        }
