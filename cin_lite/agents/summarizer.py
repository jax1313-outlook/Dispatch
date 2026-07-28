"""Summarization agent — Claude-backed.

Replaces the deterministic placeholder summary with a Claude-generated summary of
the contract plus the rule-module intelligence. This is a NON-deterministic helper
and sits OUTSIDE the deterministic rule path (the rules in cin_lite/rules/ stay
deterministic per the architecture).

Single Messages API call via the official `anthropic` SDK. Falls back to a
deterministic summary when the SDK isn't installed, no API key is configured, or
the call fails — so the Phase-1 pipeline still runs end-to-end offline.

Configuration (environment):
    ANTHROPIC_API_KEY   required to use Claude (else deterministic fallback)
    CIN_LITE_MODEL      optional model override (default: claude-opus-4-8)
"""

from __future__ import annotations

import json
import os
from typing import Any

from loguru import logger

from .base import BaseAgent

MODEL = os.environ.get("CIN_LITE_MODEL", "claude-opus-4-8")
MAX_TOKENS = 400

_SYSTEM = (
    "You are the summarization agent in a government-contract intelligence "
    "pipeline. You are given one contract and the JSON output of deterministic "
    "rule modules that have already analyzed it. Write a concise 2-3 sentence "
    "summary for a human reviewer who is deciding whether to pursue the contract. "
    "Lead with the most decision-relevant facts: set-aside type, NAICS/SIN codes, "
    "pricing flags, and cyber-compliance burden. Be factual and do not invent "
    "details beyond the provided data. Output only the summary, no preamble."
)

_CONTRACT_FIELDS = (
    "title",
    "agency",
    "solicitation_number",
    "estimated_value",
    "response_date",
    "description",
)


def _deterministic_summary(contract: dict, flags: list[str]) -> str:
    """Offline stand-in used when Claude is unavailable."""
    return (
        f"{contract.get('title')} ({contract.get('agency')}) — "
        f"est. {contract.get('estimated_value')}, due {contract.get('response_date')}. "
        f"{len(flags)} flag(s): {', '.join(flags) if flags else 'none'}."
    )


class SummarizerAgent(BaseAgent):
    """Claude-backed summarization with deterministic fallback."""

    NAME = "summarizer"
    VERSION = "1.0.0"
    ROLE = "processing"
    ACTION = "summarize"

    def initialize(self, config: dict[str, Any]) -> None:
        self._model = config.get("model", MODEL)
        self._max_tokens = config.get("max_tokens", MAX_TOKENS)
        self._client = None

        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.info("{agent} initialized (deterministic mode — no API key)", agent=self.NAME)
            return

        try:
            import anthropic
            self._client = anthropic.Anthropic()
            logger.info("{agent} initialized (Claude mode, model={model})",
                        agent=self.NAME, model=self._model)
        except ImportError:
            logger.warning("{agent}: anthropic SDK not installed; using deterministic fallback",
                           agent=self.NAME)

    def _execute(self, payload: dict[str, Any]) -> str:
        contract = payload["contract"]
        intelligence = payload["intelligence"]
        flags = payload["flags"]

        logger.debug("{agent} executing for contract {solicitation}",
                     agent=self.NAME, solicitation=contract.get("solicitation_number"))

        if self._client is None:
            logger.debug("{agent} using deterministic summary", agent=self.NAME)
            return _deterministic_summary(contract, flags)

        msg_payload = {
            "contract": {k: contract.get(k) for k in _CONTRACT_FIELDS},
            "intelligence": intelligence,
            "flags": flags,
        }

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": "Summarize this contract for the reviewer.\n\n"
                        + json.dumps(msg_payload, indent=2),
                    }
                ],
            )
            text = "".join(b.text for b in response.content if b.type == "text").strip()
            return text or _deterministic_summary(contract, flags)
        except Exception as exc:
            logger.error("{agent} failed ({exc}); using deterministic fallback",
                        agent=self.NAME, exc=exc)
            return _deterministic_summary(contract, flags)

    def shutdown(self) -> None:
        self._client = None
        logger.info("{agent} shut down", agent=self.NAME)


def summarize(contract: dict, intelligence: dict, flags: list[str]) -> str:
    """Return a human-readable summary, Claude-generated when possible."""
    agent = SummarizerAgent()
    agent.initialize({})
    try:
        return agent.execute({
            "contract": contract,
            "intelligence": intelligence,
            "flags": flags,
        })
    finally:
        agent.shutdown()
