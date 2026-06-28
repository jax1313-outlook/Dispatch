from core.utils.logger import log
from core.intel.cin_scoring import CINScoringModel
from core.intel.rule_modules import RuleModules


class HybridIntelligence:
    """
    Phase 4: Unified intelligence layer.
    - consumes HybridSummary output
    - applies CIN scoring
    - evaluates rule modules
    - prepares structure for CIN routing + GIE alignment
    """

    def __init__(self):
        self.scoring = CINScoringModel()
        self.rules = RuleModules()

    def build(self, hybrid_summary: dict) -> dict:
        """
        Returns unified intelligence product:
        {
            "summary": {...},
            "scoring": {...},
            "rules": {...},
            "intel_version": "phase4-wip"
        }
        """
        log("HybridIntelligence.build: generating intelligence product")

        scoring = self.scoring.score(hybrid_summary)
        rules = self.rules.evaluate(hybrid_summary)

        return {
            "summary": hybrid_summary,
            "scoring": scoring,
            "rules": rules,
            "intel_version": "phase4-wip",
        }
