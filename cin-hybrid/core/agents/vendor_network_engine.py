from core.utils.logger import log

class VendorNetworkEngine:
    def __init__(self, data_client):
        """
        data_client: simple client exposing .get(table, filters=None)
        Used to retrieve vendor relationship data.
        """
        self.data_client = data_client

    def fetch_relationships(self, payload: dict):
        """
        payload: {
            "vendor_id": "...",
            "table": "vendor_relationships"
        }
        """
        vendor_id = payload.get("vendor_id")
        table = payload.get("table")

        if not vendor_id:
            raise ValueError("vendor_id is required")
        if not table:
            raise ValueError("table is required")

        log(f"VendorNetworkEngine: fetching relationships for vendor_id={vendor_id}")
        return self.data_client.get(table, filters={"vendor_id": vendor_id})

    def analyze_network(self, payload: dict):
        """
        payload: {
            "records": [...],
        }
        """
        records = payload.get("records", [])
        log(f"VendorNetworkEngine: analyzing {len(records)} relationship records")

        summary = {
            "dominant_vendor": None,
            "subcontractor_count": 0,
            "jv_partners": [],
            "flags": []
        }

        for r in records:
            vendor = r.get("vendor")
            role = r.get("role")

            if role == "prime":
                summary["dominant_vendor"] = vendor

            if role == "sub":
                summary["subcontractor_count"] += 1

            if role == "jv":
                summary["jv_partners"].append(vendor)

            if r.get("flag"):
                summary["flags"].append(r["flag"])

        return summary
