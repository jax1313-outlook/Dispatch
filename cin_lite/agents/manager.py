"""Agent manager — lifecycle coordinator for BaseAgent instances.

Provides a single point of control for registering, initializing, executing,
and shutting down pipeline agents through the common BaseAgent interface.
Supports context-manager usage to guarantee shutdown on exit.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseAgent

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages a set of agents through the BaseAgent lifecycle."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if not agent.NAME:
            raise ValueError(f"{type(agent).__name__} has no NAME set")
        self._agents[agent.NAME] = agent
        logger.info("registered agent %s (v%s)", agent.NAME, agent.VERSION)

    def get(self, name: str) -> BaseAgent:
        return self._agents[name]

    @property
    def agents(self) -> dict[str, BaseAgent]:
        return dict(self._agents)

    def initialize_all(self, config: dict[str, Any]) -> None:
        logger.info("initializing %d agent(s)", len(self._agents))
        for agent in self._agents.values():
            agent.initialize(config)

    def execute(self, name: str, payload: dict[str, Any]) -> Any:
        return self._agents[name].execute(payload)

    def shutdown_all(self) -> None:
        logger.info("shutting down %d agent(s)", len(self._agents))
        errors: list[tuple[str, Exception]] = []
        for name, agent in self._agents.items():
            try:
                agent.shutdown()
            except Exception as exc:
                logger.error("shutdown failed for %s: %s", name, exc)
                errors.append((name, exc))
        if errors:
            names = ", ".join(n for n, _ in errors)
            raise RuntimeError(f"Shutdown failed for: {names}") from errors[0][1]

    def __enter__(self) -> AgentManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown_all()
