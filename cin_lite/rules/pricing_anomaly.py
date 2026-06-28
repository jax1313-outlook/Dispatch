"""Pricing anomaly rule module.

Deterministic checks on the contract's estimated value: missing value, suspiciously
round numbers, and out-of-band magnitudes. Thresholds are explicit constants so the
logic stays auditable.
"""

from __future__ import annotations

from .base import RuleResult

NAME = "pricing_anomaly"
VERSION = "1.0.0"

# Explicit, auditable thresholds.
_LOW_BAND = 25_000          # below this is unusually small for a tracked contract
_HIGH_BAND = 100_000_000    # above this warrants human attention


def run(contract: dict) -> RuleResult:
    value = contract.get("estimated_value")
    flags: list[str] = []
    findings: dict = {"estimated_value": value}

    if value is None or not isinstance(value, (int, float)):
        flags.append("value_missing")
        return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings)

    if value < _LOW_BAND:
        flags.append("value_below_band")
    if value > _HIGH_BAND:
        flags.append("value_above_band")

    # "Suspiciously round": exact multiple of 1,000,000 is a common placeholder.
    if value >= 1_000_000 and value % 1_000_000 == 0:
        flags.append("suspiciously_round")

    findings["below_band"] = value < _LOW_BAND
    findings["above_band"] = value > _HIGH_BAND

    if not flags:
        flags.append("pricing_nominal")

    return RuleResult(module=NAME, version=VERSION, flags=flags, findings=findings)
