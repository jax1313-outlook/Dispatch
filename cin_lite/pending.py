"""Pending decisions — staging area for email-driven control flow.

When the pipeline processes a contract, it stores the full context (contract,
intelligence, summary, routing recommendation, flags) as a pending decision.
When the reviewer clicks an action button in the HTML email, the portal loads
the pending record and completes the archival.
"""

from __future__ import annotations

import json
from pathlib import Path

from cin_lite import archive

_PENDING_DIR = archive.ARCHIVE_ROOT / "Pending"


def _path(contract_id: str) -> Path:
    return _PENDING_DIR / f"{contract_id}.json"


def store(
    contract_id: str,
    contract: dict,
    intelligence: dict,
    summary: str,
    decision: dict,
    flags: list[str],
    *,
    enriched: dict | None = None,
) -> Path:
    """Persist all context needed to complete a decision later."""
    _PENDING_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_id": contract_id,
        "contract": contract,
        "intelligence": intelligence,
        "summary": summary,
        "decision": decision,
        "flags": flags,
    }
    if enriched is not None:
        payload["enriched"] = enriched
    path = _path(contract_id)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def load(contract_id: str) -> dict | None:
    """Load a pending decision, or None if not found."""
    path = _path(contract_id)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def complete(contract_id: str) -> None:
    """Remove a pending decision after it has been acted on."""
    path = _path(contract_id)
    if path.exists():
        path.unlink()


def list_pending() -> list[dict]:
    """Return all pending decisions (for dashboard display)."""
    if not _PENDING_DIR.exists():
        return []
    results = []
    for path in sorted(_PENDING_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            results.append(json.load(fh))
    return results
