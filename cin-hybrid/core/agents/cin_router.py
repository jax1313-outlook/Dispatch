from core.utils.logger import log
from core.agents.sam_ingestion_engine import SAMIngestionEngine
from core.agents.vendor_network_engine import VendorNetworkEngine
from core.agents.cyber_compliance_engine import CyberComplianceEngine

class CINRouter:
    def __init__(self, data_client):
        self.engines = {
            "sam": SAMIngestionEngine(data_client),
            "vendor": VendorNetworkEngine(data_client),
            "cyber": CyberComplianceEngine(data_client),
        }

    def dispatch(self, engine_name: str, action: str, payload: dict):
        """
        Dispatch a request to the correct engine and action.
        """
        if engine_name not in self.engines:
            raise ValueError(f"Engine '{engine_name}' not registered")

        engine = self.engines[engine_name]

        if not hasattr(engine, action):
            raise ValueError(f"Engine '{engine_name}' has no action '{action}'")

        log(f"Router: dispatching to {engine_name}.{action}")
        method = getattr(engine, action)
        return method(payload)
