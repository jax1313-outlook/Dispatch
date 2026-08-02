"""Claude agents — the NON-deterministic helpers of the pipeline.

Per the architecture, these sit outside the deterministic rule path:
summarization, routing-decision, and proposal-writer agents. Each has a
deterministic fallback when the Anthropic API key is not configured.
"""
