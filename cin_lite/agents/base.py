"""Abstract base class for pipeline agents — the NON-deterministic helpers.

Every agent sits outside the deterministic rule path and follows the same
lifecycle: initialize (validate config / load resources), execute (do the
work and return a result), shutdown (release resources). Concrete agents
implement these three methods and declare NAME / VERSION for traceability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Standard interface for all pipeline agents."""

    NAME: str = ""
    VERSION: str = ""

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Prepare the agent for execution.

        Validate configuration, acquire API clients, and load any resources
        needed before execute() is called.  Raise on invalid config.
        """

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> Any:
        """Run the agent's core logic and return a result.

        The shape of *payload* and the return value are agent-specific.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources acquired during initialize()."""
