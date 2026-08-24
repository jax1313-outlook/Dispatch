"""Accounting Connector — the handoff Dispatch already has, given a status word.

``dispatch/accounting_export.py`` is the prior art and it is unusually candid:
"no accounting/QuickBooks integration exists anywhere in this codebase... There
is no live integration here, on purpose." What it does instead is write one JSON
file per settlement into an export directory, for a human to import into
whatever books Level 1 Transport actually keeps.

That is not a gap this connector fills by pretending otherwise. It is a
*``MANUAL`` step*, in the mission's exact sense -- "a human performed the step
outside Dispatch and recorded it" -- and naming it that is the whole
contribution. Before this connector, a settlement export returned
``{"status": "written_locally"}``, which is true and reads, to anyone glancing at
a screen, like the money moved. After it, the same call comes back labelled
``MANUAL`` with the file path as its source reference, and every surface that
shows it has to show the label.

The export function itself is called, not copied: one place decides what a
settlement export record contains, and it is still the module that already knew.

Two things this connector will not do, whatever provider is chosen later:

* **It will not write a settlement, an invoice or a payment.** Those live in
  Current Reality (``dispatch/services.py``), the boundary forbids the import,
  and an accounting package's opinion about what was paid is an input to a human
  reconciliation, not a replacement for Dispatch's own record.
* **It will not decide what is owed.** Pricing authority is on Section 6.2's
  list of things a connector may never hold, and ``CapabilityDeclaration``
  refuses to let it be declared.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorError,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    utc_now,
)

PAYLOAD_KIND = "accounting_settlement_export"


class AccountingConnector(BaseConnector):
    """Hands settlement records to an accounting system. None is connected."""

    connector_id = "accounting"
    connector_name = "Accounting Connector"
    required_config_keys = ("DISPATCH_ACCOUNTING_API_URL", "DISPATCH_ACCOUNTING_API_KEY")
    credential_keys = ("DISPATCH_ACCOUNTING_API_KEY",)
    auth_method = "api_key"
    capability_declaration = CapabilityDeclaration(
        collects=("settlement export receipts",),
        produces=(
            "one JSON settlement export record per settlement, for manual import",
        ),
        notes=(
            "The local export is a MANUAL handoff: a bookkeeper imports the file outside "
            "Dispatch. Nothing here posts to any ledger, and nothing here writes a "
            "settlement, invoice or payment back into Dispatch."
        ),
    )

    def _export_module(self):
        from dispatch import accounting_export

        return accounting_export

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        """``operation='export_settlement'``: write the handoff file, labelled MANUAL.

        Not ``UNCONFIGURED``, even though no accounting provider is configured:
        something real and useful did happen -- a record was written for a human
        to act on -- and calling that "unconfigured" would hide a completed step.
        Not ``LIVE`` either, because no external system was told anything.
        ``MANUAL`` is the word that fits, and it is why the vocabulary has one.
        """
        if request.operation != "export_settlement":
            return self.unconfigured(
                request,
                extra=(
                    "No accounting provider is connected, so the only operation available is "
                    "'export_settlement', which writes a file for manual import."
                ),
            )

        settlement = dict(request.params.get("settlement") or {})
        if not settlement.get("settlement_id"):
            return self.failure(
                request,
                ConnectorError(
                    "malformed_payload",
                    "A settlement export needs a settlement_id. Nothing was written.",
                ),
                status=ConnectorStatus.UNAVAILABLE,
            )

        receipt = self._export_module().export_settlement(settlement)

        if receipt.get("status") != "written_locally":
            return self.failure(
                request,
                ConnectorError(
                    "transport_failure",
                    "The settlement export could not be written to the export directory.",
                    retryable=True,
                    detail=str(receipt.get("error", "")),
                ),
                status=ConnectorStatus.UNAVAILABLE,
            )

        payload = self.payload(
            PAYLOAD_KIND,
            {
                "settlement_id": settlement.get("settlement_id", ""),
                "load_id": settlement.get("load_id", ""),
                "invoice_number": settlement.get("invoice_number", ""),
                "export_path": receipt.get("path", ""),
                "posted_to_accounting_system": False,
                "note": (
                    "MANUAL handoff: a file was written for a human to import. No accounting "
                    "system was contacted and no ledger was posted."
                ),
            },
            status=ConnectorStatus.MANUAL,
            source_reference=str(receipt.get("path", "")),
            source_timestamp=utc_now(),
            confidence=0.0,
        )
        return self.success(request, payload)
