import json
import os
from core.utils.logger import log


class JSONVendorLoader:
    """
    Loads vendor profiles from local JSON files.
    Replace later with:
    - SAM.gov API client
    - database-backed vendor profiles
    - web scrapers
    """

    def __init__(self, base_path: str = "vendor_profiles"):
        self.base_path = base_path
        log(f"JSONVendorLoader initialized (base_path={self.base_path})")

    def get_vendor_profile(self, vendor_id: str) -> dict:
        """
        Loads vendor profile JSON by vendor_id.
        Example file: vendor_profiles/L1T-001.json
        """
        log(f"JSONVendorLoader.get_vendor_profile: vendor_id={vendor_id}")

        filename = f"{vendor_id}.json"
        filepath = os.path.join(self.base_path, filename)

        if not os.path.exists(filepath):
            log(f"Vendor profile not found: {filepath}")
            raise FileNotFoundError(f"Vendor profile JSON not found: {filepath}")

        with open(filepath, "r") as f:
            data = json.load(f)

        log(f"Vendor profile loaded: {filepath}")
        return data
