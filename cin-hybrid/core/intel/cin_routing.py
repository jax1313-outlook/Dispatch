from core.utils.logger import log


class CINRouting:
    """
    Phase 4: CIN routing (WIP).
    - decides which intelligence paths to activate
    - uses scoring + rules to set high-level CIN signals

    For now, returns a simple dict:
    {
        "risk_level": "low|medium|high",
        "paths": [...],
        "notes": [...],
    }
    """

    def route(self, scoring: dict, rules: dict) -> dict:
        """
        scoring: HybridIntelligence.scoring
        rules: HybridIntelligence.rules

        Returns routing decision dict.
        """
        log("CINRouting.route: computing routing decision")

        cin_score = scoring.get("cin_score", 0.0)
        risk_level = self._risk_from_score(cin_score)

        paths = []
        notes = []

        # Example path activations based on rules + score
        sam_flags = rules.get("sam", {}).get("flags", [])
        vendor_flags = rules.get("vendor_network", {}).get("flags", [])
        cyber_flags = rules.get("cyber", {}).get("flags", [])
        pricing_flags = rules.get("pricing", {}).get("flags", [])
        influence_flags = rules.get("influence", {}).get("flags", [])

        if "sam_missing" in sam_flags or "sam_incomplete" in sam_flags:
            paths.append("sam_review")
            notes.append("SAM data missing or incomplete; route to SAM review.")

        if "vendor_isolated" in vendor_flags:
            paths.append("vendor_network_analysis")
            notes.append("Vendor appears isolated; route to network analysis.")

        if "cyber_low_score" in cyber_flags or "cyber_unknown" in cyber_flags:
            paths.append("cyber_risk_assessment")
            notes.append("Cyber posture weak or unknown; route to cyber risk assessment.")

        if pricing_flags:
            paths.append("pricing_anomaly_review")
            notes.append("Pricing flags present; route to pricing anomaly review (WIP).")

        if influence_flags:
            paths.append("influence_review")
            notes.append("Influence / foreign ownership flags present; route to influence review (WIP).")

        return {
            "risk_level": risk_level,
            "paths": paths,
            "notes": notes,
        }

    def _risk_from_score(self, cin_score: float) -> str:
        if cin_score >= 75:
            return "low"
        if cin_score >= 50:
            return "medium"
        return "high"
