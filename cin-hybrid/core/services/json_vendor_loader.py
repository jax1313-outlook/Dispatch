from core.utils.logger import log
import json
import os

class JSONVendorLoader:
    """
    Minimal JSON vendor loader.
    HybridOps expects: load_vendor(vendor_id)
    """

    def __init__(self, base_path="vendors"):
        self.base_path = base_path
        log(f"JSONVendorLoader initialized (base_path={self.base_path})")

    def load_vendor(self, vendor_id: str) -> dict:
        """
        HybridOps entrypoint.
        Loads vendor JSON profile from disk.
        """
        vendor_path = os.path.join(self.base_path, f"{vendor_id}.json")

        if not os.path.exists(vendor_path):
            raise FileNotFoundError(f"Vendor file not found: {vendor_path}")

        with open(vendor_path, "r") as f:
            vendor = json.load(f)

        log(f"Vendor loaded: {vendor_id}")
        return vendor
