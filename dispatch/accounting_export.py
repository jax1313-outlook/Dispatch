"""Accounting handoff boundary.

Confirmed during the deployment-hardening audit: no accounting/QuickBooks
integration exists anywhere in this codebase. dispatch/services.py itself
says so (see compute_ifta_payment_recommendation()'s docstring), and the
live /settings page tells the user the same thing ("QuickBooks Online --
Planned"). This module is the boundary for that gap -- and only the
boundary.

Following the acquisition-layer pattern already used elsewhere in this
codebase (dispatch/acquisition.py's DISPATCH_LOAD_API_URL + local-file
fallback): if DISPATCH_ACCOUNTING_API_URL isn't configured, export writes
a structured JSON file locally instead of calling out anywhere, and never
raises. There is no live integration here, on purpose -- per this
mission's governance rule 9, a real QuickBooks (or other) integration is
future work requiring its own vendor choice and auth flow, not something
to fake.

Deliberately NOT decided here (see the deployment decision register):
    - what triggers an export (per-invoice? per-payment? a batch job?)
    - which vendor / API shape (QuickBooks Online vs Desktop vs a plain
      CSV a bookkeeper imports by hand)
    - authentication for a live integration

This only defines what a settlement export record looks like, using
fields that already exist on the real Settlement model (dispatch/models.py)
-- nothing invented.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


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


def _export_dir() -> Path:
    explicit = os.environ.get("DISPATCH_ACCOUNTING_EXPORT_DIR")
    if explicit:
        return Path(explicit)
    return _get_data_dir() / "AccountingExport"


def export_settlement(settlement: dict) -> dict:
    """Export one settlement record. Returns a receipt dict describing
    where the export went. Never raises -- a settlement that already
    completed its real DB write must not fail visibly because of this.

    If DISPATCH_ACCOUNTING_API_URL is set, this still only writes locally
    today -- no live call is made. That's the point: this boundary exists
    so a real integration can be dropped in later behind this same
    function signature, without touching any caller.
    """
    record = {
        "settlement_id": settlement.get("settlement_id", ""),
        "load_id": settlement.get("load_id", ""),
        "invoice_number": settlement.get("invoice_number", ""),
        "invoice_amount": settlement.get("invoice_amount", 0.0),
        "invoice_date": settlement.get("invoice_date", ""),
        "due_date": settlement.get("due_date", ""),
        "payment_status": settlement.get("payment_status", ""),
        "payment_amount": settlement.get("payment_amount", 0.0),
        "payment_date": settlement.get("payment_date", ""),
        "payment_method": settlement.get("payment_method", ""),
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    export_dir = _export_dir()
    try:
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"{record['settlement_id'] or 'unknown'}.json"
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return {"status": "written_locally", "path": str(path), "record": record}
    except OSError as exc:
        return {"status": "export_failed", "error": str(exc), "record": record}
