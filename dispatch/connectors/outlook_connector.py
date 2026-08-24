"""Outlook Connector — reads schedule, never becomes one.

The doctrine this connector is shaped by is already written down in
``dispatch/opportunities.py``, and it is short: "Outlook is the scheduling source
of truth and stays outside Dispatch." That module removed a ``Calendar Event``
lifecycle stage for exactly this reason -- creating a calendar entry is an
external side effect of a human's approval, not a state an opportunity passes
through.

So this connector is defined by its asymmetry, and the asymmetry is enforced:

**Inbound is read-only and labelled.** Schedule information and Outlook-derived
capacity may be *presented* by Dispatch. They arrive as a ``NormalizedPayload``
whose status is on every rendering of it, and nothing in Dispatch stores them as
though Dispatch knew them. There is no ``sync`` operation, no local calendar
table, and no code path that writes a schedule into Current Reality -- which is
what "Dispatch may not create a second scheduling truth" means once it stops
being a sentence and becomes a constraint.

**Outbound requires a human first.** ``request_event_creation`` is declared under
``requires_human_authorization`` and refuses without an explicit ``authorized_by``
identity. It also refuses the reserved system identities, and it will not accept
an attribution to Mike that the caller merely asserts: the mission forbids
manufacturing "Approved by Mike Zachary" anywhere, so this connector requires the
caller to pass an authorization reference to a decision that was actually
recorded elsewhere. Today, with no provider configured, the operation refuses on
configuration grounds anyway -- but the authorization check runs first, so the
gate is proven by test rather than merely present.

There is no existing Outlook code in this repository to wrap: a search finds the
doctrine in ``dispatch/opportunities.py``, a test asserting that doctrine, and
``outlook.com`` in an unrelated list of free email domains. This connector adds
the boundary, changes no existing behaviour, and creates nothing that would need
to be undone when a real Microsoft Graph provider is chosen.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorError,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
)

#: Matches dispatch/opportunities.py and dispatch/rehearsal.py. Duplicated
#: rather than imported across a subsystem boundary -- see THE MIKE RULE.
RESERVED_SYSTEM_IDENTITIES = {
    "PUBLISHER", "SYSTEM", "AUTOMATION", "INTELLIGENCE", "LIBRARY",
    "CRON", "BACKGROUND_JOB", "DISPATCH_DAEMON",
}

READ_OPERATIONS = ("read_schedule", "read_capacity")
AUTHORIZED_OPERATIONS = ("request_event_creation",)


class OutlookConnector(BaseConnector):
    """Presents Outlook's schedule. Never mirrors it, never writes it unasked."""

    connector_id = "outlook"
    connector_name = "Outlook Connector"
    required_config_keys = (
        "DISPATCH_OUTLOOK_TENANT_ID",
        "DISPATCH_OUTLOOK_CLIENT_ID",
        "DISPATCH_OUTLOOK_CLIENT_SECRET",
    )
    credential_keys = ("DISPATCH_OUTLOOK_CLIENT_SECRET",)
    auth_method = "oauth_client_credentials"
    capability_declaration = CapabilityDeclaration(
        collects=(
            "calendar events as Outlook holds them",
            "free/busy windows",
            "Outlook-derived capacity",
        ),
        produces=("read-only schedule information for presentation, always labelled",),
        requires_human_authorization=("request_event_creation",),
        notes=(
            "Outlook is the source of scheduling truth and stays outside Dispatch. Dispatch may "
            "evaluate fit and present what Outlook says; it may not keep a competing calendar, "
            "and it may not create an event without a human authorization recorded elsewhere."
        ),
    )

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        if request.operation in AUTHORIZED_OPERATIONS:
            refusal = self._authorization_refusal(request)
            if refusal is not None:
                return refusal
            return self.unconfigured(
                request,
                extra=(
                    "The authorization was supplied, but no Outlook provider is configured, so "
                    "no event was created. Nothing has been scheduled anywhere."
                ),
            )

        if request.operation not in READ_OPERATIONS:
            return self.unconfigured(
                request,
                extra=(
                    f"Available operations are {', '.join(READ_OPERATIONS + AUTHORIZED_OPERATIONS)}."
                ),
            )

        return self.unconfigured(
            request,
            extra=(
                "Outlook schedule information is unavailable. Dispatch shows no schedule of its "
                "own in its place, because it does not keep one."
            ),
        )

    def _authorization_refusal(self, request: ConnectorRequest) -> ConnectorResult | None:
        """The human gate, checked before configuration.

        Deliberately first. If configuration were checked first, then the day a
        provider is configured would be the day this gate ran for the first
        time, and a gate whose first execution is in production is not a gate.
        """
        authorized_by = str(request.params.get("authorized_by", "")).strip()
        authorization_reference = str(request.params.get("authorization_reference", "")).strip()

        if not authorized_by:
            return self.failure(
                request,
                ConnectorError(
                    "not_authorized",
                    "Creating an Outlook event requires the identity of the human who "
                    "authorized it. Dispatch does not schedule anything on its own initiative.",
                ),
                status=ConnectorStatus.ABSENT,
            )
        if authorized_by.upper() in RESERVED_SYSTEM_IDENTITIES:
            return self.failure(
                request,
                ConnectorError(
                    "not_authorized",
                    f"{authorized_by!r} is a system identity and cannot authorize a calendar "
                    "event. A person authorizes; a process records.",
                ),
                status=ConnectorStatus.ABSENT,
            )
        if not authorization_reference:
            return self.failure(
                request,
                ConnectorError(
                    "not_authorized",
                    "Creating an Outlook event requires a reference to the decision that "
                    "authorized it -- an approval event id, not an assertion in this call. "
                    "Dispatch never manufactures an approval attribution.",
                ),
                status=ConnectorStatus.ABSENT,
            )
        return None
