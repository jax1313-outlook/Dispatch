"""Portal helpers — data loading and card processing.

Reads from pipeline layers without modifying them.
"""

from __future__ import annotations

import json
from pathlib import Path

from cin_lite import acquisition, processing
from cin_lite.agents import summarizer, router


DISPATCH_SAMPLE_DIR = Path(__file__).resolve().parent / "sample_dispatch_data"

SCORE_HIGH_THRESHOLD = 90

INQUIRY_TEMPLATE_SUBJECT = "Load Inquiry - Level 1 Transport"

INQUIRY_TEMPLATE_BODY = """\
Hello,

We reviewed your posted load and believe it may fit our operating area and equipment profile.

Please contact us when available to discuss load details, timing, and rate.

Thank you,

Mike Zachary
Level 1 Transport Inc.

---
Important:
This is not acceptance.
This is not commitment.
This is not negotiation.
This is a non-binding early inquiry."""


def load_and_process_sam() -> list[dict]:
    """Acquire SAM contracts and process through the pipeline."""
    contracts = acquisition.acquire()
    results = []
    for contract in contracts:
        intel = processing.process(contract)
        flags = processing.all_flags(intel)
        summary = summarizer.summarize(contract, intel, flags)
        decision = router.decide(contract, intel, summary, flags)
        results.append({
            "contract": contract,
            "intelligence": intel,
            "flags": flags,
            "summary": summary,
            "decision": decision,
        })
    return results


def load_dispatch_data() -> list[dict]:
    """Load dispatch/load data from sample files."""
    loads: list[dict] = []
    if DISPATCH_SAMPLE_DIR.exists():
        for path in sorted(DISPATCH_SAMPLE_DIR.glob("*.json")):
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            data.setdefault("_source_file", path.name)
            loads.append(data)
    return loads


def card_visual(score: int | None, decision: dict | None = None) -> dict:
    """Determine card visual header based on score or routing decision."""
    if score is not None:
        if score >= SCORE_HIGH_THRESHOLD:
            return {"icon": "✅", "label": "HIGH VALUE MATCH", "css": "card-high"}
        return {"icon": "\U0001f7e5", "label": "", "css": "card-investigate"}

    if decision:
        action = decision.get("action", "")
        priority = decision.get("priority", "")
        if action == "approve_proposal":
            return {"icon": "✅", "label": f"PURSUE CANDIDATE | {priority}", "css": "card-high"}
        if action == "flag_review":
            return {"icon": "\U0001f7e5", "label": "FLAG FOR REVIEW", "css": "card-investigate"}
        if action == "deeper_analysis":
            return {"icon": "⚠️", "label": "DEEPER ANALYSIS", "css": "card-analysis"}
        if action == "reject":
            return {"icon": "❌", "label": "REJECT", "css": "card-reject"}

    return {"icon": "", "label": "", "css": "card-default"}


def format_score(score: int | None) -> str:
    if score is None:
        return "Unknown"
    return str(score)
