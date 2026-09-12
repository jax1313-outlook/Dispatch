"""Joe Worker Package.

Voice capture, driver communication, dictation parsing, and Opportunity Card creation worker.
"""

from dispatch_operations.workers.joe.worker import JoeWorker

__all__ = ["JoeWorker"]
