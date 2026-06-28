from core.utils.logger import log


class MinimalDataSourceClient:
    """
    Minimal stub data source client.
    Replace with:
    - SAM.gov API wrapper
    - vendor website scraper
    - local JSON loader
    """

    def __init__(self):
        log("MinimalDataSourceClient initialized")

    def get_vendor_profile(self, vendor_id: str) -> dict:
        log(f"MinimalDataSourceClient.get_vendor_profile: vendor_id={vendor_id}")

        # Replace this with real data later
        return {
            "vendor_id": vendor_id,
            "name": "Level 1 Transport LLC",
            "sam_status": "active",
            "naics": ["484110", "484121", "484122"],
            "cage": "L1T01",
            "duns": "123456789",
            "contracts_history": [
                {"agency": "VA", "value": 25000, "year": 2024},
                {"agency": "DoD", "value": 18000, "year": 2023},
            ],
            "cyber_posture": {
                "mfa": True,
                "encryption": True,
                "patching": "monthly",
            },
            "contacts": [
                {"name": "Mike", "role": "Owner", "email": "jax1313@outlook.com"}
            ],
        }
