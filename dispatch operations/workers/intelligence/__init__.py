"""Intelligence Worker Package Proxy forwarding to canonical dispatch.workers.intelligence."""

from dispatch.workers.intelligence.worker import IntelligenceWorker

__all__ = ["IntelligenceWorker"]
