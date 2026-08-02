"""Archive Layer.

Assigns each contract a unique ID, builds a metadata bundle, and persists raw +
processed + intelligence + summary + routing artifacts into the /Archive folder
tree defined by the architecture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARCHIVE_ROOT = Path(__file__).resolve().parent / "Archive"
_SUBDIRS = ("Raw", "Processed", "Intelligence", "Summaries", "Routing")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_tree() -> None:
    for sub in _SUBDIRS:
        (ARCHIVE_ROOT / sub).mkdir(parents=True, exist_ok=True)


def make_id(contract: dict) -> str:
    """Deterministic, human-readable unique ID: CIN-YYYYMMDD-<8 hex>."""
    seed = str(contract.get("solicitation_number") or contract.get("title") or repr(contract))
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8].upper()
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"CIN-{day}-{digest}"


def _write_json(subdir: str, contract_id: str, payload: Any) -> Path:
    path = ARCHIVE_ROOT / subdir / f"{contract_id}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path


def store(contract: dict, intelligence: dict, summary: str) -> dict:
    """Persist raw/processed/intelligence/summary; return the metadata bundle."""
    ensure_tree()
    contract_id = make_id(contract)

    metadata = {
        "contract_id": contract_id,
        "source": contract.get("_source_file", "unknown"),
        "title": contract.get("title"),
        "solicitation_number": contract.get("solicitation_number"),
        "agency": contract.get("agency"),
        "estimated_value": contract.get("estimated_value"),
        "response_date": contract.get("response_date"),
        "acquired_at": contract.get("_acquired_at"),
        "processed_at": _utc_now(),
        "flag_count": sum(len(r.get("flags", [])) for r in intelligence.values()),
    }

    _write_json("Raw", contract_id, contract)
    _write_json("Processed", contract_id, {"metadata": metadata, "contract": contract})
    _write_json("Intelligence", contract_id, intelligence)
    (ARCHIVE_ROOT / "Summaries" / f"{contract_id}.txt").write_text(summary, encoding="utf-8")

    return metadata


def store_proposal(proposal: dict, outline: str) -> tuple[Path, Path]:
    """Persist a triggered proposal: structured JSON + human-readable outline."""
    proposals_dir = ARCHIVE_ROOT / "Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    pid = proposal["proposal_id"]
    json_path = _write_json("Proposals", pid, proposal)
    md_path = proposals_dir / f"{pid}.md"
    md_path.write_text(outline, encoding="utf-8")
    return json_path, md_path


def record_routing(
    contract_id: str,
    action: str,
    route: str,
    metadata: dict,
    recommendation: dict | None = None,
    *,
    action_label: str = "",
    flags: list[str] | None = None,
    summary: str = "",
) -> Path:
    """Persist the human decision, resulting route, and the agent recommendation."""
    payload = {
        "contract_id": contract_id,
        "action": action,
        "action_label": action_label,
        "route": route,
        "decided_at": _utc_now(),
        "recommendation": recommendation,
        "followed_recommendation": bool(recommendation and recommendation.get("action") == action),
        "flags": flags or [],
        "summary": summary,
        "metadata": metadata,
    }
    return _write_json("Routing", contract_id, payload)
