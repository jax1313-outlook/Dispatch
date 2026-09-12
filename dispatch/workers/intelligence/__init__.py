"""Intelligence Worker Package.

Pre-commit dynamic capacity analysis, load scoring, and calendar recommendation worker.
"""

from dispatch_operations.workers.intelligence.worker import IntelligenceWorker

__all__ = ["IntelligenceWorker"]
