"""Core Base Classes for Dispatch Bounded Operational Workers.

Enforces Worker Constitutions, Reserved System Identity Guards, Human Commitment Gates,
and Deterministic Handoff Sequences.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class WorkerBoundaryViolationError(PermissionError):
    """Raised when a worker attempts an operation outside its Constitutional authority."""


class HumanCommitmentRequiredError(PermissionError):
    """Raised when an automated worker attempts to commit a load or send communications without human approval."""


RESERVED_SYSTEM_IDENTITIES = {
    "PUBLISHER",
    "SYSTEM",
    "AUTOMATION",
    "INTELLIGENCE",
    "LIBRARY",
    "JOE",
}


@dataclass
class WorkerConstitution:
    worker_id: str
    name: str
    purpose: str
    capabilities: List[str]
    boundaries: Dict[str, Any]
    inputs: List[str]
    outputs: List[str]
    relationships: List[str]
    handoffs: List[str]
    stop_conditions: List[str]
    escalation_conditions: List[str]


@dataclass
class HandoffEvent:
    event_id: str
    source_worker: str
    target_worker: str
    trigger: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    record_updated: str
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            payload = f"{self.event_id}:{self.source_worker}:{self.target_worker}:{self.timestamp}"
            self.checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BaseWorker:
    """Base operational worker bound by a fixed Constitution."""

    def __init__(self, constitution: WorkerConstitution, config: Optional[Dict[str, Any]] = None):
        self.constitution = constitution
        self.config = config or {}
        self.state = "INITIALIZED"

    def verify_authority(self, requested_action: str, actor_id: Optional[str] = None) -> None:
        """Enforce that non-human workers cannot commit or perform human-only actions."""
        action_upper = requested_action.upper()
        if "COMMIT" in action_upper or "APPROVE" in action_upper or "SEND_EMAIL" in action_upper:
            if actor_id is None or actor_id.strip().upper() in RESERVED_SYSTEM_IDENTITIES:
                raise HumanCommitmentRequiredError(
                    f"Worker {self.constitution.worker_id} cannot perform human action {requested_action!r}. "
                    f"Only Mike Zachary (human authority) is permitted to commit or authorize."
                )

    def execute_handoff(
        self,
        target_worker_id: str,
        trigger: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        record_updated: str,
    ) -> HandoffEvent:
        event_id = f"HO-{self.constitution.worker_id}-{int(datetime.datetime.now().timestamp())}"
        event = HandoffEvent(
            event_id=event_id,
            source_worker=self.constitution.worker_id,
            target_worker=target_worker_id,
            trigger=trigger,
            input_data=input_data,
            output_data=output_data,
            record_updated=record_updated,
        )
        self.state = "HANDOFF_COMPLETED"
        return event


class WorkerRegistry:
    """Registry managing active workers and their configurations."""

    def __init__(self):
        self._workers: Dict[str, BaseWorker] = {}

    def register(self, worker: BaseWorker) -> None:
        self._workers[worker.constitution.worker_id.upper()] = worker

    def get(self, worker_id: str) -> Optional[BaseWorker]:
        return self._workers.get(worker_id.upper())

    def list_workers(self) -> List[str]:
        return list(self._workers.keys())


class HandoffRunner:
    """Orchestrates deterministic handoff transitions between bounded workers."""

    def __init__(self, registry: WorkerRegistry):
        self.registry = registry
        self.history: List[HandoffEvent] = []

    def dispatch_handoff(
        self,
        source_worker_id: str,
        target_worker_id: str,
        trigger: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        record_updated: str,
    ) -> HandoffEvent:
        source_worker = self.registry.get(source_worker_id)
        if source_worker is None:
            raise ValueError(f"Source worker {source_worker_id!r} not registered.")

        event = source_worker.execute_handoff(
            target_worker_id=target_worker_id,
            trigger=trigger,
            input_data=input_data,
            output_data=output_data,
            record_updated=record_updated,
        )
        self.history.append(event)
        return event
