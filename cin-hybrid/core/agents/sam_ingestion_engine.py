from core.utils.logger import log

class SAMIngestionEngine:
    def __init__(self, client):
        """
        client: a simple HTTP client or SDK wrapper that exposes .get(url, params=None)
        """
        self.client = client

    def fetch_opportunities(self, payload: dict):
        """
        payload: {
            "filters": {...},
            "limit": 100
        }
        """
        base_url = payload.get("base_url")
        if not base_url:
            raise ValueError("base_url is required")

        filters = payload.get("filters", {})
        limit = payload.get("limit", 100)

        log(f"SAMIngestionEngine: fetching opportunities from {base_url} with limit={limit}")
        response = self.client.get(base_url, params={**filters, "limit": limit})
        return response

    def fetch_opportunity_detail(self, payload: dict):
        """
        payload: {
            "detail_url": "...",
            "id": "..."
        }
        """
        detail_url = payload.get("detail_url")
        if not detail_url:
            raise ValueError("detail_url is required")

        opp_id = payload.get("id")
        log(f"SAMIngestionEngine: fetching detail for id={opp_id} from {detail_url}")
        response = self.client.get(detail_url, params={"id": opp_id} if opp_id else None)
        return response
