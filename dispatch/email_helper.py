"""Email Helper: the review-package step between Publisher and Submit in Dispatch.

Local Dispatch copy, duplicated to enforce standalone ownership under THE MIKE RULE.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

RESERVED_SYSTEM_IDENTITIES = {"SYSTEM", "CRON", "BACKGROUND_JOB", "DISPATCH_DAEMON"}

STATUSES = ["DRAFT", "REVIEWED", "SUBMITTED"]

_SIGNATURE = "\n\nThank you,\n\nMike Zachary\nLevel 1 Transport Inc."

_EDITABLE_FIELDS = {
    "broker_email", "broker_subject", "broker_body",
    "customer_email", "customer_subject", "customer_body",
}


class EmailHelperSubmitError(ValueError):
    """Raised when a package is submitted without a valid external submitted_by identity."""


def _get_data_dir() -> Path:
    portal_dir = os.environ.get("PORTAL_DATA_DIR")
    if portal_dir:
        return Path(portal_dir)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Current Workspace" / "PortalData"
    env_dir = os.environ.get("DISPATCH_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parent.parent / "portal" / "data"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _packages_path() -> Path:
    d = _get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "email_packages.json"


def _load() -> list[dict]:
    path = _packages_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    path = _packages_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_package(load_id: str) -> dict | None:
    for package in _load():
        if package["load_id"] == load_id:
            return package
    return None


def list_packages() -> list[dict]:
    return _load()


def _format_when(value: str | None) -> str:
    if not value:
        return "TBD"
    return value[:16].replace("T", " ")


def _closeout_summary_lines(closeout_data: dict | None) -> list[str]:
    if not closeout_data:
        return []

    load = closeout_data.get("load") or {}
    rate = closeout_data.get("rate_confirmation")
    settlement = closeout_data.get("settlement")
    pods = closeout_data.get("pods") or []

    lines = [
        f"Pickup: {load.get('pickup_location') or '?'} "
        f"({_format_when(load.get('pickup_datetime'))})",
        f"Delivery: {load.get('delivery_location') or '?'} "
        f"({_format_when(load.get('delivery_datetime'))})",
    ]

    if rate:
        rate_line = (
            f"Rate: ${rate['rate_amount']:.2f} ({rate['rate_type'].replace('_', ' ')})"
        )
        if rate.get("distance_miles"):
            rate_line += f", {rate['distance_miles']} mi"
        lines.append(rate_line)
    else:
        lines.append("Rate: not yet confirmed")

    if settlement:
        lines.append(
            f"Invoice #: {settlement['invoice_number']} "
            f"(${settlement['invoice_amount']:.2f}, {settlement['payment_status']})"
        )
    else:
        lines.append("Invoice: not yet generated")

    if pods:
        pod = pods[0]
        lines.append(
            f"POD: {pod['status']} (recipient: {pod.get('recipient') or '—'})"
        )
    else:
        lines.append("POD: not yet generated")

    return lines


def _draft_broker_email(
    load: dict, broker_contact: dict | None, closeout_data: dict | None = None
) -> tuple[str, str, str]:
    to = broker_contact["email"] if broker_contact and broker_contact.get("email") else ""
    greeting_name = broker_contact.get("contact_name") if broker_contact else ""
    greeting = f"Hello {greeting_name}," if greeting_name else "Hello,"
    lane = f"{load.get('pickup_location') or '?'} to {load.get('delivery_location') or '?'}"
    subject = f"Load {load['load_id'][:12]} Completed — {lane}"

    summary_lines = _closeout_summary_lines(closeout_data)
    if summary_lines:
        summary = "\n".join(summary_lines)
        opening = (
            f"Load {load['load_id'][:12]} ({lane}) has been completed. Summary below; "
            "full rate confirmation, proof of delivery, and invoice documents are "
            "available on request.\n\n"
            f"{summary}"
        )
    else:
        opening = (
            f"Load {load['load_id'][:12]} ({lane}) has been completed. Rate confirmation, "
            "proof of delivery, and invoice are available and can be provided on request."
        )
    body = f"{greeting}\n\n{opening}{_SIGNATURE}"
    return to, subject, body


def _draft_customer_email(load: dict, closeout_data: dict | None = None) -> tuple[str, str, str]:
    to = ""
    lane = f"{load.get('pickup_location') or '?'} to {load.get('delivery_location') or '?'}"
    subject = f"Delivery Confirmation — {load.get('customer') or 'Your Shipment'}"

    summary_lines = _closeout_summary_lines(closeout_data)
    if summary_lines:
        summary = "\n".join(summary_lines)
        opening = (
            f"Your shipment ({lane}) has been delivered and completed. Summary below; "
            "a copy of the proof of delivery is available on request.\n\n"
            f"{summary}"
        )
    else:
        opening = (
            f"Your shipment ({lane}) has been delivered and completed. "
            "A copy of the proof of delivery is available on request."
        )
    body = f"Hello,\n\n{opening}{_SIGNATURE}"
    return to, subject, body


def create_draft(
    load_id: str,
    load: dict,
    broker_contact: dict | None = None,
    pod_id: str | None = None,
    invoice_number: str | None = None,
    closeout_data: dict | None = None,
) -> dict:
    existing = get_package(load_id)
    if existing:
        return existing

    broker_to, broker_subject, broker_body = _draft_broker_email(
        load, broker_contact, closeout_data
    )
    customer_to, customer_subject, customer_body = _draft_customer_email(load, closeout_data)

    packages = _load()
    now = _utc_now()
    package = {
        "id": f"EH-{len(packages) + 1:04d}",
        "load_id": load_id,
        "status": "DRAFT",
        "broker_email": broker_to,
        "broker_subject": broker_subject,
        "broker_body": broker_body,
        "customer_email": customer_to,
        "customer_subject": customer_subject,
        "customer_body": customer_body,
        "pod_id": pod_id,
        "invoice_number": invoice_number,
        "send_results": [],
        "reviewed_by": None,
        "created_at": now,
        "updated_at": now,
        "submitted_at": None,
    }
    packages.append(package)
    _save(packages)
    return package


def update_draft(load_id: str, **fields) -> dict:
    packages = _load()
    for package in packages:
        if package["load_id"] == load_id:
            if package["status"] == "SUBMITTED":
                raise ValueError(f"Email package for {load_id} already submitted; cannot edit")
            for key, value in fields.items():
                if key in _EDITABLE_FIELDS:
                    package[key] = value
            package["status"] = "REVIEWED"
            package["updated_at"] = _utc_now()
            _save(packages)
            return package
    raise KeyError(f"Email package not found for load: {load_id}")


def submit_package(load_id: str, submitted_by: str | None) -> dict:
    if not submitted_by or submitted_by.strip().upper() in RESERVED_SYSTEM_IDENTITIES:
        raise EmailHelperSubmitError(
            "Email package cannot be submitted without a real, external, non-system "
            "submitted_by identity (mirrors Publisher's own approval gate)."
        )

    package = get_package(load_id)
    if not package:
        raise KeyError(f"Email package not found for load: {load_id}")
    if package["status"] == "SUBMITTED":
        return package

    recipients = [
        (package["broker_email"], package["broker_subject"], package["broker_body"]),
        (package["customer_email"], package["customer_subject"], package["customer_body"]),
    ]
    if not any(to for to, _, _ in recipients):
        raise ValueError(
            "Email package has no recipient addresses -- fill in at least one email "
            "before submitting"
        )

    from dispatch import email_delivery

    results = []
    for to, subject, body in recipients:
        if not to:
            continue
        outcome = email_delivery.send(subject, body, [to], f"completion-{load_id}-{to}")
        results.append({"to": to, "result": outcome})

    packages = _load()
    for stored in packages:
        if stored["load_id"] == load_id:
            now = _utc_now()
            stored["send_results"] = results
            stored["reviewed_by"] = submitted_by
            stored["status"] = "SUBMITTED"
            stored["submitted_at"] = now
            stored["updated_at"] = now
            _save(packages)
            return stored
    raise KeyError(f"Email package not found for load: {load_id}")
