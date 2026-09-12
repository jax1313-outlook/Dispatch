"""Publisher Worker Package Proxy forwarding to canonical dispatch.workers.publisher."""

from dispatch.workers.publisher.worker import PublisherWorker

__all__ = ["PublisherWorker"]
