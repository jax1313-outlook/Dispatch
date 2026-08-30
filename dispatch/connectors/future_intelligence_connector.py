"""Future External Intelligence Connector — the named placeholder, kept empty on purpose.

Section 6.4 lists eight connectors and this is the eighth: the slot for external
intelligence Dispatch has not chosen yet -- market rate indices, broker credit
and days-to-pay data, carrier authority and safety records, fuel price feeds,
freight demand signals.

A placeholder is normally a bad idea and this one is registered for a specific
reason: the alternative is that the first such source arrives with no boundary
around it, because writing a boundary is more work than writing a fetch. Having
the slot registered means the first question asked of that source is "which
capabilities does it declare and what status does it report", not "where do I
put this".

It declares **no capabilities**. Not an empty gesture -- a declared capability is
a claim about what Dispatch can do, and there is nothing here that can do
anything. ``fetch`` refuses with ``UNCONFIGURED`` for every operation, and there
is no configuration that would make it succeed, because there is no provider and
no code behind it.

What this connector must never become, whatever is eventually plugged in: a
source of operational truth that arrives unlabelled. Market intelligence is the
most persuasive kind of unlabelled data -- a rate index looks like a fact -- and
it is a Possible Future in the mission's sense. It informs a human decision and
it never mutates Current Reality.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorRequest,
    ConnectorResult,
)


class FutureExternalIntelligenceConnector(BaseConnector):
    """The registered slot for external intelligence Dispatch has not chosen."""

    connector_id = "future_intelligence"
    connector_name = "Future External Intelligence Connector"
    required_config_keys = ()
    credential_keys = ()
    auth_method = "none"
    capability_declaration = CapabilityDeclaration(
        collects=(),
        produces=(),
        notes=(
            "No provider, no capabilities, no configuration. The slot exists so that the first "
            "external intelligence source Dispatch adopts is built behind this contract instead "
            "of beside it. Anything it eventually produces is a Possible Future: advisory, "
            "labelled, and never a mutation of Current Reality."
        ),
    )

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        return self.unconfigured(
            request,
            extra=(
                "No external intelligence source has been selected. This connector is a "
                "registered slot, not an integration."
            ),
        )
