from core.utils.logger import log


class RuleModules:
    """
    Phase 4: domain rule engines (WIP).
    - SAM rules
    - vendor network rules
    - cyber rules
    - pricing rules
    - influence rules

    Each method returns a simple dict for now:
    {
        "flags": [...],
        "notes": [...],
    }
    """

    def evaluate(self, hybrid_summary: dict) -> dict:
        """
        Entry point for rule evaluation.

        Returns:
        {
            "sam": {...},
            "vendor_network": {...},
            "cyber": {...},
            "pricing": {...},
            "influence": {...},
        }
        """
        log("RuleModules.evaluate: evaluating rules across domains")

        return {
            "sam": self._rules_sam(hybrid_summary.get("sam", {})),
            "vendor_network": self._rules_vendor(hybrid_summary.get("vendor_network", {})),
            "cyber": self._rules_cyber(hybrid_summary.get("cyber", {})),
            "pricing": self._rules_pricing(hybrid_summary),
            "influence": self._rules_influence(hybrid_summary),
        }

    def _rules_sam(self, sam: dict) -> dict:
        flags = []
        notes = []

        status = sam.get("status")
        if status is None:
            flags.append("sam_missing")
            notes.append("SAM data missing or not yet collected.")
        elif status == "WIP":
            flags.append("sam_incomplete")
            notes.append("SAM data is in-progress; registration or entity details may be incomplete.")

        return {"flags": flags, "notes": notes}

    def _rules_vendor(self, vendor: dict) -> dict:
        flags = []
        notes = []

        relationships = vendor.get("relationships", [])
        if not relationships:
            flags.append("vendor_isolated")
            notes.append("No vendor network relationships detected; potential isolation or missing network data.")

        return {"flags": flags, "notes": notes}

    def _rules_cyber(self, cyber: dict) -> dict:
        flags = []
        notes = []

        score = cyber.get("score")
        if isinstance(score, (int, float)):
            if score < 50:
                flags.append("cyber_low_score")
                notes.append(f"Cyber score {score} is below threshold; potential cyber risk.")
        else:
            flags.append("cyber_unknown")
            notes.append("Cyber posture unknown; no numeric score available.")

        return {"flags": flags, "notes": notes}

    def _rules_pricing(self, summary: dict) -> dict:
        # Phase 4 WIP: placeholder until pricing anomalies are wired
        flags = []
        notes = ["Pricing anomaly rules not yet implemented (Phase 4 WIP)."]
        return {"flags": flags, "notes": notes}

    def _rules_influence(self, summary: dict) -> dict:
        # Phase 4 WIP: placeholder until foreign influence signals are wired
        flags = []
        notes = ["Influence / foreign ownership rules not yet implemented (Phase 4 WIP)."]
        return {"flags": flags, "notes": notes}
