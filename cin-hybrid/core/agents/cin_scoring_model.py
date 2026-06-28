from core.utils.logger import log


class CINScoringModel:
    """
    Phase 4: CIN scoring across domains.
    - weighted scorecard model
    - per-domain sub-scores
    - unified CIN score (0–100)
    """

    def __init__(self):
        # Phase 4: initial weights (WIP, tunable)
        self.weights = {
            "sam": 0.25,
            "vendor_network": 0.25,
            "cyber": 0.25,
            "pricing": 0.15,
            "influence": 0.10,
        }

    def score(self, hybrid_summary: dict) -> dict:
        """
        Accepts HybridSummary.build() output and returns:
        {
            "cin_score": float,
            "domains": {
                "sam": float,
                "vendor_network": float,
                "cyber": float,
                "pricing": float,
                "influence": float,
            }
        }
        """
        log("CINScoringModel.score: scoring hybrid summary")

        domains = {
            "sam": self._score_sam(hybrid_summary.get("sam", {})),
            "vendor_network": self._score_vendor(hybrid_summary.get("vendor_network", {})),
            "cyber": self._score_cyber(hybrid_summary.get("cyber", {})),
            "pricing": self._score_pricing(hybrid_summary),
            "influence": self._score_influence(hybrid_summary),
        }

        cin_score = 0.0
        for domain, value in domains.items():
            weight = self.weights.get(domain, 0.0)
            cin_score += weight * value

        return {
            "cin_score": round(cin_score, 2),
            "domains": domains,
        }

    def _score_sam(self, sam: dict) -> float:
        status = sam.get("status")
        if status == "OK":
            return 85.0
        if status == "WIP":
            return 50.0
        if status is None:
            return 40.0
        return 60.0

    def _score_vendor(self, vendor: dict) -> float:
        status = vendor.get("status")
        relationships = vendor.get("relationships", [])
        if status == "WIP":
            return 50.0
        if not relationships:
            return 45.0
        return 70.0

    def _score_cyber(self, cyber: dict) -> float:
        status = cyber.get("status")
        score = cyber.get("score")
        if isinstance(score, (int, float)):
            return float(score)
        if status == "OK":
            return 80.0
        if status == "WIP":
            return 50.0
        return 40.0

    def _score_pricing(self, summary: dict) -> float:
        # Phase 4 WIP: placeholder until pricing anomalies are wired
        return 50.0

    def _score_influence(self, summary: dict) -> float:
        # Phase 4 WIP: placeholder until foreign influence signals are wired
        return 50.0
