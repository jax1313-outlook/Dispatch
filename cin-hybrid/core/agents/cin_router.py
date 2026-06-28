from core.utils.logger import log

class CINRouter:
    def __init__(self):
        self.engines = {}

    def register_engine(self, name: str, engine):
        """
        Register an engine under a name.
        Example: router.register_engine("gov", GovEngine())
        """
        self.engines[name] = engine
        log(f"Router: registered engine '{name}'")

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
