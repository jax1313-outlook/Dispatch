"""Archive Layer.

Assigns each contract a unique ID, builds a metadata bundle, and persists raw +
processed + intelligence + summary + routing artifacts into the /Archive folder
tree defined by the architecture.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ArchiveIntegrityError(Exception):
    """Raised by load_artifact() when an artifact's content no longer
    matches the hash recorded for it at write time. Fail-closed: the
    caller does not receive the (possibly corrupted or tampered) content."""


def _resolve_archive_root() -> Path:
    explicit = os.environ.get("DISPATCH_ARCHIVE_PATH")
    if explicit:
        return Path(explicit)
    archive_root = os.environ.get("DISPATCH_ARCHIVE_ROOT")
    if archive_root:
        return Path(archive_root) / "CIN"
    return Path(__file__).resolve().parent / "Archive"


ARCHIVE_ROOT = _resolve_archive_root()
_SUBDIRS = ("Raw", "Processed", "Intelligence", "Summaries", "Routing", "Pending", "Outbox")


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


def _write_and_hash(path: Path, content: str) -> Path:
    """Write *content* to *path* and persist a content-hash sidecar next to
    it, so a later load_artifact() can detect if the file was corrupted or
    tampered with after being written."""
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(
        json.dumps({"sha256": digest, "written_at": _utc_now()}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_json(subdir: str, contract_id: str, payload: Any) -> Path:
    path = ARCHIVE_ROOT / subdir / f"{contract_id}.json"
    return _write_and_hash(path, json.dumps(payload, indent=2, ensure_ascii=False))


def store(
    contract: dict, intelligence: dict, summary: str,
    *, enriched: dict | None = None,
) -> dict:
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
    intel_payload = dict(intelligence)
    if enriched:
        intel_payload["_enriched"] = enriched
    _write_json("Intelligence", contract_id, intel_payload)
    _write_and_hash(ARCHIVE_ROOT / "Summaries" / f"{contract_id}.txt", summary)

    return metadata


def store_proposal(proposal: dict, outline: str) -> tuple[Path, Path]:
    """Persist a triggered proposal: structured JSON + human-readable outline."""
    proposals_dir = ARCHIVE_ROOT / "Proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    pid = proposal["proposal_id"]
    json_path = _write_json("Proposals", pid, proposal)
    md_path = proposals_dir / f"{pid}.md"
    _write_and_hash(md_path, outline)
    return json_path, md_path


def _read_verified(path: Path, subdir: str) -> str:
    """Read *path*'s content and, if a .sha256 sidecar exists next to it,
    verify the content still matches the hash recorded at write time.

    No sidecar (artifact predates this feature) -> read through unchanged.
    Sidecar matches -> read through unchanged; this is the normal case.
    Sidecar mismatches -> escalate via record_integrity_exception() and
    raise ArchiveIntegrityError. Fail-closed: the caller never receives
    content that failed verification.
    """
    content = path.read_text(encoding="utf-8")
    sidecar = path.with_name(path.name + ".sha256")
    if not sidecar.exists():
        return content
    recorded = json.loads(sidecar.read_text(encoding="utf-8"))
    expected_hash = recorded.get("sha256")
    actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if actual_hash != expected_hash:
        contract_id = path.stem
        record_integrity_exception(contract_id, subdir, expected_hash, actual_hash)
        raise ArchiveIntegrityError(
            f"content hash mismatch reading {subdir}/{path.name}: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    return content


def list_contracts() -> list[dict]:
    """Return metadata for all archived contracts, most recent first."""
    processed_dir = ARCHIVE_ROOT / "Processed"
    if not processed_dir.exists():
        return []
    results = []
    for path in sorted(processed_dir.glob("*.json"), reverse=True):
        data = json.loads(_read_verified(path, "Processed"))
        results.append(data.get("metadata", {}))
    return results


def load_artifact(subdir: str, contract_id: str) -> dict | str | None:
    """Load a single archived artifact by subdirectory and contract ID.

    Returns parsed JSON for .json files, raw text for .txt files, or None.
    Raises ArchiveIntegrityError (see _read_verified) if a content hash
    was recorded for this artifact at write time and no longer matches.
    """
    json_path = ARCHIVE_ROOT / subdir / f"{contract_id}.json"
    if json_path.exists():
        return json.loads(_read_verified(json_path, subdir))
    txt_path = ARCHIVE_ROOT / subdir / f"{contract_id}.txt"
    if txt_path.exists():
        return _read_verified(txt_path, subdir)
    return None


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


def record_integrity_exception(
    contract_id: str, subdir: str, expected_hash: str | None, actual_hash: str | None
) -> Path:
    """Escalate a content-hash mismatch through the existing ACTIONS/
    HUMAN_REVIEW route (see control.ACTIONS["flag_review"]) -- but as a
    distinctly-named file, NEVER through record_routing() itself, which
    would overwrite the contract's real Routing/{contract_id}.json record
    (possibly the very file that just failed verification). Still picked
    up by pipeline.routing_history(route_filter="HUMAN_REVIEW"), which
    globs every *.json file in Routing/ regardless of name."""
    exception_id = uuid.uuid4().hex[:12]
    payload = {
        "contract_id": contract_id,
        "action": "flag_review",
        "action_label": "Flag for review (auto: archive integrity mismatch)",
        "route": "HUMAN_REVIEW",
        "decided_at": _utc_now(),
        "recommendation": None,
        "followed_recommendation": False,
        "flags": ["archive_integrity_mismatch"],
        "summary": (
            f"Content hash mismatch reading {subdir}/{contract_id}: "
            f"expected {expected_hash}, got {actual_hash!r}"
        ),
        "metadata": {"subdir": subdir, "expected_hash": expected_hash, "actual_hash": actual_hash},
    }
    path = ARCHIVE_ROOT / "Routing" / f"{contract_id}.integrity-exception-{exception_id}.json"
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return path
