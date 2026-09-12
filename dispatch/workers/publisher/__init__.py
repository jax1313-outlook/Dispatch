"""Publisher Worker Package.

Commitment package lifecycle, rate confirmation production, and Outlook email draft generation worker.
"""

from dispatch.workers.publisher.worker import PublisherWorker

__all__ = ["PublisherWorker"]
