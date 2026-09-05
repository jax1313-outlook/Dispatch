"""Fuel-receipt vision extraction -- Claude-backed, mirroring this
codebase's own established agent pattern (cin_lite/agents/extractor.py),
not a port of Hold's separate ClaudeVisionExtractor class.

Extracts one receipt image's structured fields to pre-fill the Add Fuel
Purchase form on /ifta. Never creates a fuel purchase or evidence record
itself -- the dispatcher always reviews the pre-filled form and clicks
Save explicitly. No API key configured, the anthropic package missing,
an unsupported image type, or any call/parse failure all degrade the
same way: "unavailable, fill the form manually" -- never a hard error,
never a fabricated guess. Per
DISPATCH_IFTA_PHASE6B_RECEIPT_VISION_PREFILL_LAUNCH_PACKAGE_v1.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

MODEL = os.environ.get("DISPATCH_MODEL", "claude-opus-4-8")
MAX_TOKENS = 500

_SYSTEM = (
    "You are extracting structured fields from a fuel receipt image for "
    "a trucking IFTA fuel-purchase form. Produce a JSON object with "
    "exactly these keys:\n"
    "  vendor_name -- string or null\n"
    "  vendor_address -- string or null (the full address as printed)\n"
    "  purchase_date -- \"YYYY-MM-DD\" or null\n"
    "  gallons -- number or null\n"
    "  amount -- number or null (total amount charged, in dollars)\n"
    "  extraction_confidence -- 0.0-1.0, your actual certainty for this "
    "receipt as a whole, not a blanket high score\n"
    "If you cannot read a field, use null rather than guessing."
)

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": ["string", "null"]},
        "vendor_address": {"type": ["string", "null"]},
        "purchase_date": {"type": ["string", "null"]},
        "gallons": {"type": ["number", "null"]},
        "amount": {"type": ["number", "null"]},
        "extraction_confidence": {"type": "number"},
    },
    "required": [
        "vendor_name", "vendor_address", "purchase_date",
        "gallons", "amount", "extraction_confidence",
    ],
    "additionalProperties": False,
}

_MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp",
}


def _valid(result: object) -> bool:
    return (
        isinstance(result, dict)
        and "vendor_name" in result
        and "vendor_address" in result
        and "purchase_date" in result
        and "gallons" in result
        and "amount" in result
        and isinstance(result.get("extraction_confidence"), (int, float))
    )


def extract_fuel_receipt(image_bytes: bytes, filename: str) -> dict[str, Any]:
    """Returns {"available": True, ...extracted fields} on success, or
    {"available": False, "reason": ...} otherwise. Never raises -- the
    caller's job is "pre-fill the form or don't"."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"available": False, "reason": "no API key configured"}

    try:
        import anthropic
    except ImportError:
        print("dispatch: `anthropic` not installed; receipt scan unavailable.", file=sys.stderr)
        return {"available": False, "reason": "anthropic package not installed"}

    ext = Path(filename).suffix.lower()
    media_type = _MEDIA_TYPES.get(ext)
    if not media_type:
        return {"available": False, "reason": f"unsupported image type: {ext or '(none)'}"}

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=_SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": "Extract this fuel receipt's fields."},
                    ],
                }
            ],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        result = json.loads(text)
        if _valid(result):
            return {"available": True, **result}
        print("dispatch: receipt scan returned an invalid result; scan unavailable.", file=sys.stderr)
        return {"available": False, "reason": "invalid extraction result"}
    except Exception as exc:  # noqa: BLE001 -- any network/API/parse failure degrades identically
        print(f"dispatch: receipt scan failed ({exc}); scan unavailable.", file=sys.stderr)
        return {"available": False, "reason": str(exc)}


def derive_jurisdiction(vendor_address: str | None) -> str | None:
    """Deterministic pattern match only: a 2-letter state/province code
    from Dispatch's own IFTA_JURISDICTIONS list, found as its own token
    in the address text. No inference beyond that -- returns None rather
    than guessing when no such token is present.

    Small port of Hold's src/dispatch/receipt/address.py::
    derive_jurisdiction(), adapted from "raise, then quarantine" (Hold
    has a quarantine folder to send an undetermined document to) to
    "return None, leave the field blank" -- this is a pre-fill
    convenience the dispatcher can always fill in by hand, not a gate
    with anywhere to quarantine to."""
    if not vendor_address:
        return None
    from dispatch.models import IFTA_JURISDICTIONS
    codes = set(IFTA_JURISDICTIONS)
    for token in re.split(r"[\s,]+", vendor_address.strip()):
        candidate = token.strip(".").upper()
        if candidate in codes:
            return candidate
    return None
