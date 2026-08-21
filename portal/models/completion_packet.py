"""Completion Packet: the End Load closeout bundle.

Not a new source of truth -- every field in a packet's `closeout_data` is assembled by
dispatch.services.build_completion_packet() from data that already exists (rate confirmation,
POD, settlement/invoice, evidence, broker contact). This module only persists the resulting
snapshot so it can be reviewed later, the same way portal/models/publisher.py persists action
cards derived from Sandbox/Library data.

One packet per load. Creating a packet for a load that already has one is idempotent -- it
returns the existing packet rather than overwriting it, so re-clicking "End Load" from the cab
is always safe.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir, atomic_write_json

STATUSES = ["ASSEMBLED", "ROUTED", "CLUSTERED", "ARCHIVED"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _packets_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "completion_packets.json"


def _load() -> list[dict]:
    path = _packets_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    path = _packets_path()
    atomic_write_json(path, data)


def get_packet(load_id: str) -> dict | None:
    for packet in _load():
        if packet["load_id"] == load_id:
            return packet
    return None


def list_packets() -> list[dict]:
    return _load()


def create_packet(
    load_id: str,
    closeout_data: dict,
    available: list[str] | None = None,
    missing: list[str] | None = None,
) -> dict:
    existing = get_packet(load_id)
    if existing:
        return existing

    packets = _load()
    now = _utc_now()
    packet = {
        "id": f"CP-{len(packets) + 1:04d}",
        "load_id": load_id,
        "status": "ASSEMBLED",
        "closeout_data": closeout_data,
        "available": available or [],
        "missing": missing or [],
        "publisher_action_id": None,
        "email_cluster": None,
        "retention_archive_id": None,
        "created_at": now,
        "updated_at": now,
    }
    packets.append(packet)
    _save(packets)
    return packet


def mark_routed(load_id: str, publisher_action_id: str) -> dict:
    packets = _load()
    for packet in packets:
        if packet["load_id"] == load_id:
            packet["status"] = "ROUTED"
            packet["publisher_action_id"] = publisher_action_id
            packet["updated_at"] = _utc_now()
            _save(packets)
            return packet
    raise KeyError(f"Completion packet not found for load: {load_id}")


def create_email_cluster(load_id: str, email_package: dict) -> dict:
    """D10: 'Email Sent -> Render Email to Business Document -> Attach Related Files ->
    Create Email Cluster -> Store With Completion Package.' Renders each sent email in a
    SUBMITTED email_helper package into a document record, attaches references to the
    packet's own already-assembled evidence/POD/invoice, and stores the resulting cluster
    on this load's Completion Packet. Idempotent -- an existing cluster is returned
    unchanged rather than re-rendered.
    """
    packets = _load()
    for packet in packets:
        if packet["load_id"] != load_id:
            continue
        if packet.get("email_cluster"):
            return packet

        send_results = {r["to"]: r["result"] for r in email_package.get("send_results", [])}
        documents = []
        for prefix, doc_type in (("broker", "broker_email"), ("customer", "customer_email")):
            to = email_package.get(f"{prefix}_email")
            if not to:
                continue
            documents.append({
                "type": doc_type,
                "to": to,
                "subject": email_package.get(f"{prefix}_subject"),
                "body": email_package.get(f"{prefix}_body"),
                "send_result": send_results.get(to),
            })

        closeout = packet.get("closeout_data") or {}
        cluster = {
            "email_package_id": email_package["id"],
            "documents": documents,
            "attached_files": {
                "evidence_ids": [e["evidence_id"] for e in closeout.get("evidence") or []],
                "pod_id": (closeout["pods"][0]["pod_id"] if closeout.get("pods") else None),
                "invoice_number": (
                    closeout["settlement"]["invoice_number"] if closeout.get("settlement") else None
                ),
            },
            "created_at": _utc_now(),
        }
        packet["email_cluster"] = cluster
        packet["status"] = "CLUSTERED"
        packet["updated_at"] = _utc_now()
        _save(packets)
        return packet
    raise KeyError(f"Completion packet not found for load: {load_id}")


def mark_archived(load_id: str, retention_archive_id: str) -> dict:
    """D10's terminal step: 'Archive Takes Custody.' Records that the (existing,
    human-triggered) Archive Load action has taken custody of this packet's Email
    Cluster -- does not itself trigger archiving. Idempotent.
    """
    packets = _load()
    for packet in packets:
        if packet["load_id"] == load_id:
            if packet["status"] == "ARCHIVED":
                return packet
            packet["status"] = "ARCHIVED"
            packet["retention_archive_id"] = retention_archive_id
            packet["updated_at"] = _utc_now()
            _save(packets)
            return packet
    raise KeyError(f"Completion packet not found for load: {load_id}")
