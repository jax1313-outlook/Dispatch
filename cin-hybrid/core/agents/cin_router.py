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

    def dispatch(self, engine: str, action: str, payload: dict | None = None) -> Any:
        """Dispatch an action to a registered engine.

        Looks up the engine by name and calls its `handle(action, payload)`.
        """
        target = self._engines.get(engine)
        if target is None:
            raise KeyError(f"No engine registered for {engine!r}")
        return target.handle(action, payload or {})
