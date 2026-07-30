"""Rule-module framework — Processing Layer.

Each rule module is a standalone, DETERMINISTIC logic unit that takes a contract
dict and returns a RuleResult. Results serialize to structured JSON for downstream
use (archive /Intelligence, routing, future modules).

A rule module is any object exposing:
    NAME: str
    VERSION: str
    run(contract: dict) -> RuleResult
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class RuleResult:
    """Structured output of one rule module."""

    module: str
    version: str
    flags: list[str] = field(default_factory=list)
    findings: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    # Optional heuristic score for modules that quantify exposure (e.g. vendor
    # network, cyber burden). None for modules that only emit flags/findings.
    score: int | None = None
    deterministic: bool = True

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
