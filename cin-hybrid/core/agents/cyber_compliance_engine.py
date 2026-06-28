from core.utils.logger import log

class CyberComplianceEngine:
    def __init__(self, data_client):
        """
        data_client: simple client exposing .get(table, filters=None)
        Used to retrieve cyber posture records.
        """
        self.data_client = data_client

    def fetch_posture(self, payload: dict):
        """
        payload: {
            "vendor_id": "...",
            "table": "cyber_posture"
        }
        """
        vendor_id = payload.get("vendor_id")
        table = payload.get("table")

        if not vendor_id:
            raise ValueError("vendor_id is required")
        if not table:
            raise ValueError("table is required")

        log(f"CyberComplianceEngine: fetching cyber posture for vendor_id={vendor_id}")
        return self.data_client.get(table, filters={"vendor_id": vendor_id})

    def score_posture(self, payload: dict):
        """
        payload: {
            "records": [...],
        }
        """
        records = payload.get("records", [])
        log(f"CyberComplianceEngine: scoring posture from {len(records)} records")

        score = {
            "tier": "none",
            "flags": [],
            "summary": {}
        }

        for r in records:
            level = r.get("level")
            flag = r.get("flag")

            if level in ("low", "moderate", "high"):
                score["tier"] = level

            if flag:
                score["flags"].append(flag)

        score["summary"] = {
            "record_count": len(records),
            "tier": score["tier"],
            "flags": score["flags"]
        }

        return score
