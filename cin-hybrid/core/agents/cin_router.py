"""Engine registry and dispatch for the CIN-Hybrid system.

Engines register themselves by name; the router dispatches each event to the
engine named on the event. Each engine is expected to expose `handle(event)`.
"""

from __future__ import annotations

from typing import Any


class CINRouter:
    """Routes events to registered engines by name."""

    def __init__(self) -> None:
        self._engines: dict[str, Any] = {}

    def register_engine(self, name: str, engine: Any) -> None:
        """Register an engine under `name` (overwrites any existing entry)."""
        self._engines[name] = engine

    def dispatch(self, event: Any) -> Any:
        """Dispatch `event` to its target engine's `handle` method.

        The target engine name is read from `event["engine"]` (dict) or
        `event.engine` (object).
        """
        if isinstance(event, dict):
            name = event.get("engine")
        else:
            name = getattr(event, "engine", None)

        engine = self._engines.get(name)
        if engine is None:
            raise KeyError(f"No engine registered for {name!r}")
        return engine.handle(event)
