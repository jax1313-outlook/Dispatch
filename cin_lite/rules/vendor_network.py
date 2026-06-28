"""Vendor network indicators rule module.

Deterministic detection plus a heuristic score for vendor-ecosystem signals:
limited-competition language (incumbent / sole-source / brand-name), teaming /
JV / subcontracting structure, corporate affiliation language, point-of-contact
email-domain anomalies, and award-concentration. Weights are explicit constants
so the score is auditable; the same input always yields the same output.

Reads the usual text fields plus optional structured fields when present:
    point_of_contact : list of {"email": ...}   (e.g. from SAM.gov)
    poc_emails       : list of email strings
    award            : {"awardee": {"name": ...}, "amount": ..., "number": ...}
"""

from __future__ import annotations

from .base import RuleResult

NAME = "vendor_network_indicators"
VERSION = "1.0.0"

# label -> case-insensitive substrings that indicate the category.
_CATEGORIES: dict[str, list[str]] = {
    "limited_competition": [
        "sole source", "sole-source", "single source", "only one responsible source",
        "brand name", "brand-name", "incumbent", "follow-on", "follow on",
    ],
    "teaming": [
        "joint venture", "teaming agreement", "teaming", "mentor-protege",
        "mentor-protégé", "mentor protege", "subcontractor", "subcontracting",
        "prime contractor",
    ],
    "affiliation": [
        "affiliate", "parent company", "subsidiary", "holding company",
        "commonly owned", "under common control",
    ],
}

# Personal / free email providers — unusual for a federal vendor POC.
_FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "proton.me", "protonmail.com", "gmx.com", "icloud.com",
}

# Explicit, auditable weights.
_WEIGHTS = {
    "limited_competition": 3,
    "teaming": 1,
    "affiliation": 2,
    "personal_poc_domain": 2,
    "shared_poc_domain": 1,
    "award_concentration": 2,
}


def _text(contract: dict) -> str:
    parts = [str(contract.get(k, "")) for k in ("title", "description", "naics_text", "notes")]
    return " ".join(parts).lower()


def _poc_domains(contract: dict) -> list[str]:
    emails: list[str] = []
    for poc in contract.get("point_of_contact") or []:
        if isinstance(poc, dict) and poc.get("email"):
            emails.append(str(poc["email"]))
    for addr in contract.get("poc_emails") or []:
        emails.append(str(addr))
    return [e.split("@", 1)[1].lower() for e in emails if "@" in e]


def run(contract: dict) -> RuleResult:
    text = _text(contract)

    indicators: dict[str, list[str]] = {}
    for label, needles in _CATEGORIES.items():
        hits = [n for n in needles if n in text]
        if hits:
            indicators[label] = hits

    domains = _poc_domains(contract)
    personal_domains = sorted({d for d in domains if d in _FREE_EMAIL_DOMAINS})
    shared_domain = len(domains) >= 2 and len(set(domains)) == 1

    award = contract.get("award") if isinstance(contract.get("award"), dict) else None
    awardee = None
    if award:
        a = award.get("awardee")
        awardee = a.get("name") if isinstance(a, dict) else a

    # --- score (explicit, auditable) ---
    score = 0
    signals: list[str] = []

    if "limited_competition" in indicators:
        score += _WEIGHTS["limited_competition"]
        signals.append("limited-competition language (" + ", ".join(indicators["limited_competition"]) + ")")
    if "teaming" in indicators:
        score += _WEIGHTS["teaming"]
        signals.append("teaming/subcontracting structure referenced")
    if "affiliation" in indicators:
        score += _WEIGHTS["affiliation"]
        signals.append("corporate affiliation language")
    if personal_domains:
        score += _WEIGHTS["personal_poc_domain"]
        signals.append("POC uses personal email domain (" + ", ".join(personal_domains) + ")")
    if shared_domain:
        score += _WEIGHTS["shared_poc_domain"]
        signals.append(f"multiple POCs share one domain ({domains[0]})")
    if award and "limited_competition" in indicators:
        score += _WEIGHTS["award_concentration"]
        signals.append("award concentrated with limited competition")

    if score == 0:
        risk = "none"
    elif score <= 2:
        risk = "low"
    elif score <= 5:
        risk = "moderate"
    else:
        risk = "elevated"

    flags: list[str] = []
    if score == 0:
        flags.append("no_vendor_network_signals")
    else:
        flags.append("vendor_network_signals")
    if "limited_competition" in indicators:
        flags.append("limited_competition")
    if "teaming" in indicators:
        flags.append("teaming_structure")
    if risk == "elevated":
        flags.append("vendor_concentration")

    summary = (
        f"{risk.capitalize()} vendor-network exposure: " + "; ".join(signals) + "."
        if signals
        else "No vendor-network signals detected."
    )

    findings = {
        "network_score": score,
        "network_risk": risk,
        "indicators": indicators,
        "signals": signals,
        "poc_domains": domains,
        "awardee": awardee,
    }

    return RuleResult(
        module=NAME,
        version=VERSION,
        flags=flags,
        findings=findings,
        summary=summary,
        score=score,
    )
