"""Dispatch Worker Framework Package.

Provides core base classes, governance models, worker registry, and handoff execution engine.
"""

from .base import (
    BaseWorker,
    HandoffEvent,
    HandoffRunner,
    WorkerConstitution,
    WorkerRegistry,
    HumanCommitmentRequiredError,
    WorkerBoundaryViolationError,
)

__all__ = [
    "BaseWorker",
    "HandoffEvent",
    "HandoffRunner",
    "WorkerConstitution",
    "WorkerRegistry",
    "HumanCommitmentRequiredError",
    "WorkerBoundaryViolationError",
]
