"""Joe Worker Package Proxy forwarding to canonical dispatch.workers.joe."""

from dispatch.workers.joe.worker import JoeWorker

__all__ = ["JoeWorker"]
