"""Scanner Connector — documents arrive as candidates, never as evidence.

A scanner is the most tempting connector to get wrong, because what it produces
looks exactly like what Dispatch already stores. A bill of lading that came off a
desktop scanner and a bill of lading a driver photographed at the dock are the
same PDF; the difference is that the second one has a human attached to it, and
``dispatch/services.py::attach_evidence`` records that human in
``uploaded_by``.

So this connector's normalized payload is deliberately *not* an evidence record.
It carries the scanned artifact's location, its checksum, its page count and its
capture time -- everything needed for a person to look at it and say "yes, that
belongs to load 4471" -- and stops there. Attaching it to a load stays with
``attach_evidence``, which the boundary forbids this module from importing, so
the separation is structural rather than remembered.

The same reasoning applies to OCR text: a scanner that extracts a rate and a
weight is producing a *reading*, and a reading with a confidence attached is a
candidate for a human to confirm. Section 6.2's Possible-Future rule is exactly
this: projections, estimates and extractions may never silently mutate Current
Reality. The repository already holds the pattern -- ``ifta_fuel_purchases``
carries an ``extraction_confidence`` column beside a receipt's values, precisely
so an extracted number is visibly an extracted number.

No scanner is connected. The Settings page's System Keys card already lists
"Scanner" as one of its seven integration types with no credentials in it, which
is the same fact this connector reports with a truth word.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorRequest,
    ConnectorResult,
)

PAYLOAD_KIND = "scanned_document"


class ScannerConnector(BaseConnector):
    """Receives scanned documents from a scanning device or service. None is connected."""

    connector_id = "scanner"
    connector_name = "Scanner Connector"
    required_config_keys = ("DISPATCH_SCANNER_API_URL", "DISPATCH_SCANNER_API_KEY")
    credential_keys = ("DISPATCH_SCANNER_API_KEY",)
    auth_method = "api_key"
    capability_declaration = CapabilityDeclaration(
        collects=(
            "scanned document artifacts",
            "page counts and checksums",
            "optical character recognition readings with confidence",
        ),
        produces=("document candidates for a human to attach to a load",),
        notes=(
            "A scanned document is a candidate until a person attaches it. Evidence records, "
            "and the uploaded_by identity on them, are written by dispatch/services.py and "
            "nowhere else. An OCR reading is a reading, carried with its confidence."
        ),
    )

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        return self.unconfigured(
            request,
            extra=(
                "No scanner is connected. Documents continue to reach Dispatch the way they do "
                "today: a person uploads them, and the upload records who did it."
            ),
        )
