"""Processing Layer.

Runs every registered rule module over a contract and aggregates their structured
JSON output. Rules are deterministic and independent of each other.
"""

from __future__ import annotations

from typing import Any

from .rules import ALL_RULES


def process(contract: dict) -> dict[str, Any]:
    """Apply all rule modules; return {module_name: rule_json}."""
    intelligence: dict[str, Any] = {}
    for rule in ALL_RULES:
        result = rule.run(contract)
        intelligence[result.module] = result.to_json()
    return intelligence


def all_flags(intelligence: dict[str, Any]) -> list[str]:
    """Flatten every flag raised across all modules (for quick triage)."""
    flags: list[str] = []
    for result in intelligence.values():
        flags.extend(result.get("flags", []))
    return flags
