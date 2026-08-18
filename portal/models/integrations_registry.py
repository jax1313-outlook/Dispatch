"""System Keys — generic integrations credential registry.

Deployment decision register item D4: "a generic System Keys Card integrations registry
inside the Driver Portal, covering Accounting, ELD, Scanner, Printer, DAT, TruckSmart, and
Other -- each holding an API Key, Credentials, Token, and Configuration." Reasoning given:
"Dispatch should manage integrations, not hard-code vendors."

This module is the storage/container only. It does not read from, or get read by, any live
integration -- dispatch/accounting_export.py, cin_lite/acquisition.py's DISPATCH_SAM_API_KEY,
dispatch/acquisition.py's DISPATCH_LOAD_API_KEY, cin_lite's SMTP/ANTHROPIC_API_KEY env vars,
etc. all keep reading from os.environ as they do today. Wiring any of those to read from this
registry instead is future work, not part of this change.

SECURITY NOTE -- plaintext storage: this follows the same local-file-backed-JSON pattern every
other model in portal/models/ already uses (see get_data_dir(), _load()/_save() below), for
consistency with the established codebase convention. Unlike the non-sensitive data those other
models hold, this module stores api_key / credentials / token values -- and unlike every other
place in this codebase that touches a secret (DISPATCH_SMTP_PASSWORD, ANTHROPIC_API_KEY,
DISPATCH_SAM_API_KEY, DISPATCH_EMAIL_SECRET, PORTAL_SECRET_KEY -- all os.environ.get() only,
never written to disk by this app), values saved here ARE written to disk in plaintext JSON,
with no encryption or secrets-manager layer. This is a real limitation, accepted here only
because it matches this app's documented single-admin/local-only deployment model (CLAUDE.md:
"Must remain lightweight... locally controllable... no external DB in Phase 1"). Building actual
encryption-at-rest or a secrets manager would be an architecture change outside this task's
scope and was deliberately not invented. Treat this file's JSON store as sensitive: it belongs
under the same access control as the rest of PORTAL_DATA_DIR, and should not be committed,
synced to shared storage, or exposed by any read-only file browser.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from portal.models import get_data_dir

# The seven integration types specified by D4. Fixed set -- this is a generic container, not a
# per-vendor model, so callers must pick one of these rather than inventing new types.
INTEGRATION_TYPES = [
    "Accounting",
    "ELD",
    "Scanner",
    "Printer",
    "DAT",
    "TruckSmart",
    "Other",
]

# The only editable fields on an entry, per D4: API Key, Credentials, Token, Configuration.
ENTRY_FIELDS = ["api_key", "credentials", "token", "configuration"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _registry_path() -> Path:
    d = get_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "integrations_registry.json"


def _load() -> dict:
    path = _registry_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(data: dict) -> None:
    path = _registry_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _default_entry(integration_type: str) -> dict:
    """An unsaved, empty template for a type that has never been upserted -- lets callers
    (list_entries(), get_entry()) always present all seven types, even before any of them
    have a stored record."""
    return {
        "integration_type": integration_type,
        "api_key": None,
        "credentials": None,
        "token": None,
        "configuration": None,
        "created_at": None,
        "updated_at": None,
    }


def _check_type(integration_type: str) -> None:
    if integration_type not in INTEGRATION_TYPES:
        raise ValueError(
            f"Invalid integration_type: {integration_type!r} "
            f"(must be one of {INTEGRATION_TYPES})"
        )


def list_entries() -> list[dict]:
    """Return all seven integration types in D4's fixed order. Types with no stored record
    yet come back as empty templates (created_at/updated_at None) rather than being omitted,
    so the Settings UI can always render a full System Keys card."""
    data = _load()
    return [data.get(t, _default_entry(t)) for t in INTEGRATION_TYPES]


def get_entry(integration_type: str) -> dict:
    """Return the stored entry for one type, or an empty template if it has never been
    upserted. Raises ValueError for an unknown integration_type."""
    _check_type(integration_type)
    data = _load()
    return data.get(integration_type, _default_entry(integration_type))


def upsert_entry(
    integration_type: str,
    api_key: str | None = None,
    credentials: str | dict | None = None,
    token: str | None = None,
    configuration: str | dict | None = None,
) -> dict:
    """Create or update the entry for one integration type. Idempotent by integration_type --
    calling this again for the same type updates the existing record rather than creating a
    second one. Only fields explicitly passed (non-None) are changed, matching
    library.update_record()'s convention -- pass a field to change it, omit it to leave it as
    is. To blank out a value entirely, pass an empty string; to wipe every field at once, use
    clear_entry() instead."""
    _check_type(integration_type)
    data = _load()
    now = _utc_now()

    entry = data.get(integration_type)
    if entry is None:
        entry = _default_entry(integration_type)
        entry["created_at"] = now

    if api_key is not None:
        entry["api_key"] = api_key
    if credentials is not None:
        entry["credentials"] = credentials
    if token is not None:
        entry["token"] = token
    if configuration is not None:
        entry["configuration"] = configuration
    entry["updated_at"] = now

    data[integration_type] = entry
    _save(data)
    return entry


def clear_entry(integration_type: str) -> dict:
    """Reset all four credential fields for a type back to None, keeping the row (and its
    created_at) rather than deleting it -- lets a reviewer wipe stored secrets without losing
    the fact that this integration type was once configured. A no-op-but-valid call on a type
    that was never upserted returns a fresh empty template (nothing is persisted in that case,
    matching get_entry()'s pre-upsert behavior)."""
    _check_type(integration_type)
    data = _load()
    entry = data.get(integration_type)
    if entry is None:
        return _default_entry(integration_type)

    for field in ENTRY_FIELDS:
        entry[field] = None
    entry["updated_at"] = _utc_now()
    data[integration_type] = entry
    _save(data)
    return entry
