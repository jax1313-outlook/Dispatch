"""Claude agents — the NON-deterministic helpers of the pipeline.

Per the architecture, these sit outside the deterministic rule path:
intelligence-extraction, summarization, and routing-decision agents. Phase 1
implements the summarization agent; the others are future expansion.
"""
