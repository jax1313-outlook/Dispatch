"""Claude agents — the NON-deterministic helpers of the pipeline.

Per the architecture (section 7.1), these sit outside the deterministic rule
path: intelligence extraction, summarization, routing-decision, and
proposal-writer agents. Each has a deterministic fallback when the Anthropic
API key is not configured.
"""
