"""Dispatch Worker Framework Package.

Provides core base classes, governance models, worker registry, and handoff execution engine.
"""

from dispatch.workers.worker_framework.base import (
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
