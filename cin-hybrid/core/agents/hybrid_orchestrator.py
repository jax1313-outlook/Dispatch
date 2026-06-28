"""Top-level orchestrator for the CIN-Hybrid system.

The HybridOrchestrator drives end-to-end processing: it takes incoming events and
routes each one to the appropriate engine through a CINRouter.
"""

from __future__ import annotations

from typing import Any, Iterable


class HybridOrchestrator:
    """Coordinates event processing across the CIN-Hybrid engines."""

    def __init__(self, router: Any | None = None, config: dict | None = None) -> None:
        self.router = router
        self.config = config or {}

    def run(self, events: Iterable[Any] | None = None) -> list[Any]:
        """Process a batch of events end-to-end and return per-event results."""
        return [self.route(event) for event in (events or [])]

    def route(self, event: Any) -> Any:
        """Route a single event to the appropriate engine via the router."""
        if self.router is None:
            raise RuntimeError("HybridOrchestrator has no router configured")
        return self.router.dispatch(event)
