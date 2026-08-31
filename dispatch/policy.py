"""The Policy Profile — every business judgement Dispatch makes, in one file.

The engine knows *how* to evaluate. It does not know what Level 1 Transport
considers a good load: that belongs to the person who owns the truck, and it
changes with the season, the fuel price and the debt position. A business rule
welded into code is a rule the operator must ask a programmer to change.

Before this module, `dispatch/scoring.py` held nine such rules as module
constants. They are now values in a validated, versioned file.

Doctrine: `docs/DISPATCH_CONFIGURABLE_BUSINESS_POLICY_DOCTRINE.md` and
`docs/DISPATCH_POLICY_PROFILE_SPEC.md`.

What this module deliberately does not do
-----------------------------------------
It cannot grant authority. There is no `auto_accept`, no `auto_decline`, no
`auto_send`, and no threshold above which a human is skipped. The profile tunes
evaluation; it does not touch the authority model. A setting that could grant
authority would make human final authority a setting, and a setting can be
changed by accident.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Where the operator's profile lives. Override with ``DISPATCH_POLICY_PROFILE``.
DEFAULT_PROFILE_PATH = _REPO_ROOT / "config" / "policy_profile.json"

#: The shipped defaults, read when the operator has no profile of their own.
SHIPPED_PROFILE_PATH = _REPO_ROOT / "config" / "policy_profile.default.json"


# The values `dispatch/scoring.py` carried as module constants until this module
# existed. They are reproduced here exactly, so that a Dispatch with no profile
# file scores precisely what it scored before -- the move is a move, not a
# behaviour change. Correcting them is separate, later, and visible.
DEFAULTS: dict = {
    "profile_version": "0.0.0-shipped-defaults",
    "profile_name": "Shipped defaults (not the operator's)",
    "identity": {
        "home_base": "Jacksonville, FL",
    },
    "money": {
        "fuel_cost_per_mile": 0.62,
        "rate_per_mile": {
            "floor": 2.50,
            "good": 4.00,
            "excellent": 5.50,
        },
    },
    "capability": {
        "operating_radius_miles": 500,
        "hours_available_default": 11.0,
        "drive_speed_mph": 50,
        "weight_limit_lbs": 45000,
    },
}


class PolicyProfileError(ValueError):
    """The profile could not be trusted, so none of it was applied."""


@dataclass(frozen=True)
class RatePerMile:
    floor: float
    good: float
    excellent: float


@dataclass(frozen=True)
class PolicyProfile:
    """One operator's business judgement, validated whole.

    `is_default` is True when nothing of the operator's own was loaded. It
    exists so an interface can say which values are theirs and which they have
    merely inherited -- a default presented as a decision is a small lie that
    compounds.
    """

    profile_version: str
    profile_name: str
    home_base: str
    fuel_cost_per_mile: float
    rate_per_mile: RatePerMile
    operating_radius_miles: float
    hours_available_default: float
    drive_speed_mph: float
    weight_limit_lbs: float
    source_path: str = ""
    is_default: bool = True
    warnings: tuple[str, ...] = field(default_factory=tuple)


# Keys the profile may carry. Anything else is a typo, and a typo that is
# silently ignored leaves the operator believing one set of rules is in force
# while another is running.
_ALLOWED = {
    "profile_version": None,
    "profile_name": None,
    "effective_from": None,
    "identity": {"home_base"},
    "money": {"fuel_cost_per_mile", "rate_per_mile"},
    "capability": {
        "operating_radius_miles",
        "hours_available_default",
        "drive_speed_mph",
        "weight_limit_lbs",
    },
}
_RATE_KEYS = {"floor", "good", "excellent"}


def _reject_unknown(raw: dict) -> list[str]:
    problems: list[str] = []
    for key, value in raw.items():
        if key.startswith("_"):
            continue  # a comment key, by convention
        if key not in _ALLOWED:
            problems.append(f"unknown top-level key {key!r}")
            continue
        allowed_children = _ALLOWED[key]
        if allowed_children is None:
            continue
        if not isinstance(value, dict):
            problems.append(f"{key!r} must be an object")
            continue
        for child in value:
            if child.startswith("_"):
                continue
            if child not in allowed_children:
                problems.append(f"unknown key {key}.{child!r}")
    rate = (raw.get("money") or {}).get("rate_per_mile")
    if rate is not None:
        if not isinstance(rate, dict):
            problems.append("money.rate_per_mile must be an object")
        else:
            for child in rate:
                if not child.startswith("_") and child not in _RATE_KEYS:
                    problems.append(f"unknown key money.rate_per_mile.{child!r}")
    return problems


def _number(raw: dict, section: str, key: str, problems: list[str],
            *, positive: bool = True) -> float | None:
    value = (raw.get(section) or {}).get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        problems.append(f"{section}.{key} must be a number, got {type(value).__name__}")
        return None
    if positive and value <= 0:
        problems.append(f"{section}.{key} must be greater than zero, got {value}")
        return None
    return float(value)


def _merge(raw: dict) -> dict:
    """Overlay the operator's values on the shipped defaults, section by section."""
    merged = json.loads(json.dumps(DEFAULTS))  # deep copy, no aliasing
    for section in ("identity", "money", "capability"):
        supplied = raw.get(section)
        if not isinstance(supplied, dict):
            continue
        for key, value in supplied.items():
            if key == "rate_per_mile" and isinstance(value, dict):
                merged["money"]["rate_per_mile"].update(value)
            else:
                merged[section][key] = value
    for key in ("profile_version", "profile_name"):
        if raw.get(key) is not None:
            merged[key] = raw[key]
    return merged


def profile_from_dict(raw: dict, *, source_path: str = "", is_default: bool = False) -> PolicyProfile:
    """Validate a profile whole, or refuse it whole.

    Raises `PolicyProfileError` listing every problem found, rather than the
    first. A half-applied profile is the worst possible state: the operator
    believes one set of rules is in force while another is running.
    """
    if not isinstance(raw, dict):
        raise PolicyProfileError("profile must be a JSON object")

    problems = _reject_unknown(raw)
    merged = _merge(raw)

    home_base = (merged.get("identity") or {}).get("home_base")
    if not isinstance(home_base, str) or not home_base.strip():
        problems.append("identity.home_base must be a non-empty string")

    fuel = _number(merged, "money", "fuel_cost_per_mile", problems)
    radius = _number(merged, "capability", "operating_radius_miles", problems)
    hours = _number(merged, "capability", "hours_available_default", problems)
    speed = _number(merged, "capability", "drive_speed_mph", problems)
    weight = _number(merged, "capability", "weight_limit_lbs", problems)

    rate_raw = (merged.get("money") or {}).get("rate_per_mile") or {}
    floor = _number({"r": rate_raw}, "r", "floor", problems)
    good = _number({"r": rate_raw}, "r", "good", problems)
    excellent = _number({"r": rate_raw}, "r", "excellent", problems)
    if None not in (floor, good, excellent) and not (floor <= good <= excellent):
        problems.append(
            "money.rate_per_mile must satisfy floor <= good <= excellent, got "
            f"{floor} / {good} / {excellent}"
        )

    version = merged.get("profile_version")
    if not isinstance(version, str) or not version.strip():
        problems.append("profile_version must be a non-empty string")

    if problems:
        raise PolicyProfileError(
            "Policy profile rejected; no part of it was applied:\n  - "
            + "\n  - ".join(problems)
        )

    return PolicyProfile(
        profile_version=version,
        profile_name=str(merged.get("profile_name") or ""),
        home_base=home_base,
        fuel_cost_per_mile=fuel,
        rate_per_mile=RatePerMile(floor=floor, good=good, excellent=excellent),
        operating_radius_miles=radius,
        hours_available_default=hours,
        drive_speed_mph=speed,
        weight_limit_lbs=weight,
        source_path=source_path,
        is_default=is_default,
    )


def default_profile() -> PolicyProfile:
    """The shipped defaults, honestly labelled as defaults."""
    return profile_from_dict({}, source_path="", is_default=True)


def load_profile(path: str | Path | None = None) -> PolicyProfile:
    """Load and validate a profile from disk.

    A missing file is not an error -- a fresh install works, on defaults that
    say they are defaults. A malformed file *is* an error, and it is raised
    rather than absorbed: see `active_profile` for the running-system behaviour.
    """
    if path is None:
        env = os.environ.get("DISPATCH_POLICY_PROFILE")
        path = Path(env) if env else DEFAULT_PROFILE_PATH
    path = Path(path)

    if not path.exists():
        return default_profile()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyProfileError(f"Policy profile at {path} could not be read: {exc}") from exc

    return profile_from_dict(raw, source_path=str(path), is_default=False)


_active: PolicyProfile | None = None
_last_known_good: PolicyProfile | None = None


def active_profile() -> PolicyProfile:
    """The profile in force, loaded once and cached.

    If the file on disk is malformed, this returns the **last known-good**
    profile -- or the shipped defaults if there has never been one -- and
    records why on `warnings`. Dispatch keeps running and says what happened; it
    does not stop, and it never partially applies the bad file.
    """
    global _active, _last_known_good
    if _active is not None:
        return _active
    try:
        _active = load_profile()
        _last_known_good = _active
    except PolicyProfileError as exc:
        fallback = _last_known_good or default_profile()
        _active = PolicyProfile(
            **{
                **{k: getattr(fallback, k) for k in (
                    "profile_version", "profile_name", "home_base",
                    "fuel_cost_per_mile", "rate_per_mile", "operating_radius_miles",
                    "hours_available_default", "drive_speed_mph", "weight_limit_lbs",
                    "source_path", "is_default",
                )},
                "warnings": (str(exc),),
            }
        )
    return _active


def set_active_profile(profile: PolicyProfile | None) -> None:
    """Install a profile, or clear the cache so the next read re-loads.

    Used by tests and by an operator reloading after an edit.
    """
    global _active
    _active = profile
