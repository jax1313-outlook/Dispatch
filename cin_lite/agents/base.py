"""Abstract base class for pipeline agents — the NON-deterministic helpers.

Every agent sits outside the deterministic rule path and follows the same
lifecycle: initialize (validate config / load resources), execute (do the
work and return a result), shutdown (release resources). Concrete agents
implement these three methods and declare NAME / VERSION / ROLE / ACTION
for traceability and permission enforcement.

Permission check: execute() validates that the agent's ACTION is permitted
by its ROLE before delegating to _execute(). Subclasses implement _execute()
with their core logic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from .roles import permissions_for

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when an agent attempts an action outside its role."""

    def __init__(self, agent_name: str, role: str, action: str) -> None:
        self.agent_name = agent_name
        self.role = role
        self.action = action
        super().__init__(
            f"Agent '{agent_name}' (role={role}) is not permitted to perform '{action}'"
        )


class BaseAgent(ABC):
    """Standard interface for all pipeline agents."""

    NAME: str = ""
    VERSION: str = ""
    ROLE: str = ""
    ACTION: str = ""

    def check_permission(self, action: str) -> bool:
        """Return True if this agent's role permits the given action."""
        return action in permissions_for(self.ROLE)

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Prepare the agent for execution.

        Validate configuration, acquire API clients, and load any resources
        needed before execute() is called.  Raise on invalid config.
        """

    def execute(self, payload: dict[str, Any]) -> Any:
        """Check permissions, then run the agent's core logic.

        Uses the ACTION class attribute by default. A payload may override
        this with an explicit ``action`` key.
        """
        action = payload.get("action", self.ACTION)
        if action and not self.check_permission(action):
            logger.warning("%s denied action '%s' (role=%s)", self.NAME, action, self.ROLE)
            raise PermissionDeniedError(self.NAME, self.ROLE, action)
        return self._execute(payload)

    @abstractmethod
    def _execute(self, payload: dict[str, Any]) -> Any:
        """Subclass implementation of the agent's core logic."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release resources acquired during initialize()."""
