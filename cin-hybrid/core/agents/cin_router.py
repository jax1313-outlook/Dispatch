from core.utils.logger import log
from core.agents.sam_ingestion_engine import SAMIngestionEngine
from core.agents.vendor_network_engine import VendorNetworkEngine
from core.agents.cyber_compliance_engine import CyberComplianceEngine


class CINRouter:
    """
    Phase 3: Minimal action-mapped router.
    - validates engine names
    - validates action names
    - dispatches to engine.action(payload)
    """

    def __init__(self, data_client):
        self.engines = {
            "sam": SAMIngestionEngine(data_client),
            "vendor": VendorNetworkEngine(data_client),
            "cyber": CyberComplianceEngine(data_client),
        }

        # Phase 3 action map (minimal)
        self.action_map = {
            "ingest": "sam",
            "analyze": "vendor",
            "check": "cyber",
        }

    def dispatch(self, engine_name: str, action: str, payload: dict):
        log(f"CINRouter.dispatch: engine={engine_name}, action={action}")

        # Validate engine
        if engine_name not in self.engines:
            raise ValueError(f"Unknown engine '{engine_name}'")

        engine = self.engines[engine_name]

        # Validate action
        if not hasattr(engine, action):
            raise ValueError(f"Engine '{engine_name}' has no action '{action}'")

        method = getattr(engine, action)
        return method(payload)
