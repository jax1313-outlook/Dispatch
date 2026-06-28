from core.utils.logger import log
from core.intel.cin_scoring import CINScoringModel
from core.intel.rule_modules import RuleModules
from core.intel.cin_routing import CINRouting


class HybridIntelligence:
    """
    Phase 4: Unified intelligence layer.
    - consumes HybridSummary output
    - applies CIN scoring
    - evaluates rule modules
    - computes CIN routing decisions
    - prepares structure for GIE alignment (future)
    """

    def __init__(self):
        self.scoring = CINScoringModel()
        self.rules = RuleModules()
        self.routing = CINRouting()

    def build(self, hybrid_summary: dict) -> dict:
        """
        Returns unified intelligence product:
        {
            "summary": {...},
            "scoring": {...},
            "rules": {...},
            "routing": {...},
            "intel_version": "phase4-wip"
        }
        """
        log("HybridIntelligence.build: generating intelligence product")

        scoring = self.scoring.score(hybrid_summary)
        rules = self.rules.evaluate(hybrid_summary)
        routing = self.routing.route(scoring, rules)

        return {
            "summary": hybrid_summary,
            "scoring": scoring,
            "rules": rules,
            "routing": routing,
            "intel_version": "phase4-wip",
        }
