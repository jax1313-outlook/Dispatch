"""Load Board Connector — and the sample data it refuses to launder.

``dispatch/acquisition.py`` already normalizes load-board records into
Dispatch's load shape, and already has the two halves a connector needs: a
configurable API source (``DISPATCH_LOAD_API_URL``) and a local directory of
sample JSON files. This connector wraps it rather than growing a second
normalizer, because the load shape is the part that must not fork.

The one thing it does **not** reuse is ``acquire()``'s failure behaviour. That
function falls back to the local sample directory when the API call fails, which
is right for a development script and wrong for an operational boundary: a
dispatcher looking at loads that came out of ``portal/sample_dispatch_data``
after a provider outage would be looking at fiction presented as a market. So:

* ``operation='fetch_loads'`` is ``UNCONFIGURED`` until a real board is
  configured, and refuses. It does not quietly hand back samples.
* ``operation='sample_loads'`` returns the same local records deliberately, and
  labels them ``SIMULATED``. That is what they are, and with the label attached
  they are safe to demonstrate a screen with.

The distinction only exists because the mission's vocabulary makes it cheap to
express. Without a status word, both operations would have had to be the same
function returning the same-looking list.

**No provider is selected.** DAT and TruckSmart are the two named in the
Settings page's System Keys card (``portal/models/integrations_registry.py``),
neither is connected, and choosing between them -- along with the subscription
that makes either one work -- is Mike's decision, recorded in
``docs/connectors/PROVIDER_INSERTION.md``.
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

PAYLOAD_KIND = "load_board_offers"


class LoadBoardConnector(BaseConnector):
    """Reads load offers from a load board. None is connected."""

    connector_id = "load_board"
    connector_name = "Load Board Connector"
    required_config_keys = ("DISPATCH_LOAD_API_URL", "DISPATCH_LOAD_API_KEY")
    credential_keys = ("DISPATCH_LOAD_API_KEY",)
    auth_method = "bearer_token"
    capability_declaration = CapabilityDeclaration(
        collects=("posted load offers", "broker identity as posted", "posted rates"),
        produces=("normalized load offers for the Opportunity layer",),
        notes=(
            "An offer is a candidate, never a commitment. Opportunity scores it, Spine records "
            "the work item, and a human answers at the WAITING_FOR_MIKE gate. A posted rate is "
            "the board's number, not an agreed one."
        ),
    )

    def _acquisition_module(self):
        from dispatch import acquisition

        return acquisition

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        if request.operation == "sample_loads":
            return self._sample(request)
        if request.operation != "fetch_loads":
            return self.unconfigured(
                request,
                extra="Available operations are 'fetch_loads' and 'sample_loads'.",
            )
        return self.unconfigured(
            request,
            extra=(
                "No load board is connected. Dispatch will not present local sample files as "
                "market offers; ask for 'sample_loads' if labelled sample data is what you want."
            ),
        )

    def _sample(self, request: ConnectorRequest) -> ConnectorResult:
        """Local sample records, labelled SIMULATED, for demonstration only."""
        acquisition = self._acquisition_module()
        try:
            loads = acquisition._acquire_local(acquisition._get_source_dir())
        except OSError as exc:  # pragma: no cover - unreadable sample directory
            return self.failure(
                request,
                ConnectorError(
                    "transport_failure",
                    "The local sample load directory could not be read.",
                    retryable=False,
                    detail=str(exc),
                ),
                status=ConnectorStatus.UNAVAILABLE,
            )

        payload = self.payload(
            PAYLOAD_KIND,
            {
                "offer_count": len(loads),
                "offers": loads,
                "note": (
                    "SIMULATED: these records come from local sample files, not from any load "
                    "board. They are not offers and none of them can be booked."
                ),
            },
            status=ConnectorStatus.SIMULATED,
            source_reference=str(acquisition._get_source_dir()),
            source_timestamp=utc_now(),
            confidence=0.0,
        )
        return self.success(request, payload)
