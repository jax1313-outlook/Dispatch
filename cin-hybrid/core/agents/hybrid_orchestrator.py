from core.agents.cin_router import CINRouter
from core.utils.logger import log
from core.utils.config_loader import load_config

class HybridOrchestrator:
    def __init__(self, config_path="config.yaml"):
        self.config = load_config(config_path)
        self.router = CINRouter()

    def register_engines(self, engines: dict):
        """
        engines: {"gov": GovEngine(), "tell": TellEngine(), ...}
        """
        for name, engine in engines.items():
            self.router.register_engine(name, engine)
            log(f"Registered engine: {name}")

    def run(self, task: dict):
        """
        task: {"engine": "gov", "action": "analyze", "payload": {...}}
        """
        engine = task.get("engine")
        action = task.get("action")
        payload = task.get("payload", {})

        log(f"Routing task → engine={engine}, action={action}")
        return self.router.dispatch(engine, action, payload)

    def route(self, engine: str, action: str, payload: dict):
        """
        Direct routing without full task dict.
        """
        log(f"Direct route → engine={engine}, action={action}")
        return self.router.dispatch(engine, action, payload)
