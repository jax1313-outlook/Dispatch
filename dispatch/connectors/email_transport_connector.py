"""Email Transport Connector — a truthful wrapper around the mail path that exists.

``cin_lite/email_delivery.py`` is the sole mail transport for the whole program
and this connector does not replace one line of it. Section 6.4 says so plainly:
"Where the repository already has Outlook, email, or other integration code,
wrap or migrate it behind the contract rather than duplicating it." A second
send path would be a second set of retry semantics, a second Outbox and a second
answer to "was that email actually sent", which is the question this connector
exists to answer honestly.

What the wrapper adds is the status word. ``email_delivery._send_or_write``
already makes the distinction that matters -- it either talks to a real SMTP
relay or it writes an ``.eml`` file into ``Archive/Outbox`` and returns a receipt
string saying which happened -- but that distinction lived only in a sentence
returned to a caller who usually discarded it. Mapped onto the mission's
vocabulary it is exactly:

    "sent via <host> to <addrs>"                     -> LIVE
        an SMTP server accepted the message; the receipt naming the host and the
        recipients is the evidence, fingerprinted into ExchangeEvidence.

    "not sent (SMTP not configured); written to <p>" -> SIMULATED
        no mail left the building. A file that looks exactly like an email was
        produced instead, which is precisely the case Section 6.3 has in mind
        when it forbids a SIMULATED payload rendering as operational
        intelligence: the message was NOT delivered and nothing may imply it was.

    "delivery failed (<exc>); written to <p>"        -> UNAVAILABLE
        configured, attempted, refused. The exception text is redacted before it
        is stored, because an SMTP failure is one of the few places a password
        genuinely does end up inside an error string.

The receipt string is parsed rather than the transport being re-implemented, and
the prefixes are pinned by ``tests/test_connectors.py``, which drives the real
``email_delivery`` code through all three branches (no host, a stub relay that
accepts, a stub relay that raises) and asserts the connector's classification.
If someone changes a receipt's wording, that test fails rather than this
connector silently reporting the wrong truth word.

**Retry is deliberately not added here.** ``_send_or_write`` already falls back
to a file on failure, so a retry at this layer would produce a second ``.eml``
for the same message and, on an intermittent relay, a duplicate delivery.
``RetryStatus`` reports one attempt, honestly.
"""

from __future__ import annotations

import os

from dispatch.connectors.contract import (
    AuthenticationStatus,
    BaseConnector,
    CapabilityDeclaration,
    ConfigurationStatus,
    ConnectorError,
    ConnectorIdentity,
    ConnectorRequest,
    ConnectorResult,
    ConnectorStatus,
    ExchangeEvidence,
    RetryStatus,
    utc_now,
)

#: The receipt prefixes ``cin_lite/email_delivery.py`` returns. Pinned by test.
RECEIPT_SENT_PREFIX = "sent via "
RECEIPT_NOT_CONFIGURED_PREFIX = "not sent (SMTP not configured)"
RECEIPT_FAILED_PREFIX = "delivery failed"

PAYLOAD_KIND = "email_delivery_receipt"


class EmailTransportConnector(BaseConnector):
    """Sends operational mail through the program's one transport, and says how."""

    connector_id = "email_transport"
    connector_name = "Email Transport Connector"
    required_config_keys = ("DISPATCH_SMTP_HOST",)
    credential_keys = ("DISPATCH_SMTP_USER", "DISPATCH_SMTP_PASSWORD")
    auth_method = "smtp_login"
    capability_declaration = CapabilityDeclaration(
        collects=(),
        produces=(
            "delivery receipts for outbound operational mail",
            "Archive/Outbox .eml artifacts when no relay is configured",
        ),
        notes=(
            "Transport only. What an email says, and whether it may be sent, is settled by "
            "COMI routing and the Publisher before anything reaches this connector."
        ),
    )

    #: Injected in tests; the real module in every other case. Not a fallback --
    #: there is no second implementation, only a seam for driving the three
    #: receipt branches without a network.
    def _delivery_module(self):
        from cin_lite import email_delivery

        return email_delivery

    # ---------------------------------------------------------------- identity

    def identity(self) -> ConnectorIdentity:
        """The provider is whichever relay is configured, or the fallback itself.

        Naming the relay host matters on the LIVE path: "LIVE -- SMTP relay
        smtp.example.com" is checkable by a person, where "LIVE -- Email
        Transport Connector" is a claim about Dispatch rather than about the
        world. On the fallback path the provider is named as what it is, so the
        label a surface renders reads "SIMULATED -- Archive/Outbox .eml fallback"
        and nobody has to know what that means to know it is not delivery.
        """
        host = self._config_value("DISPATCH_SMTP_HOST")
        if host:
            return ConnectorIdentity(
                connector_id=self.connector_id,
                connector_name=self.connector_name,
                provider_id=host,
                provider_name=f"SMTP relay {host}",
            )
        return ConnectorIdentity(
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            provider_name="Archive/Outbox .eml fallback (no relay configured)",
        )

    # ---------------------------------------------------------------- status

    def configuration(self) -> ConfigurationStatus:
        """CONFIGURED when a relay host is set; otherwise UNCONFIGURED and honest
        about what happens instead."""
        host = self._config_value("DISPATCH_SMTP_HOST")
        if not host:
            return ConfigurationStatus(
                ConnectorStatus.UNCONFIGURED,
                required_keys=self.required_config_keys,
                missing_keys=self.required_config_keys,
                detail=(
                    "No SMTP relay is configured. Messages are written to Archive/Outbox as "
                    ".eml files and are SIMULATED: nothing is delivered to anyone."
                ),
            )
        return ConfigurationStatus(
            ConnectorStatus.CONFIGURED,
            required_keys=self.required_config_keys,
            present_keys=self.required_config_keys,
            detail=f"SMTP relay configured on port {os.environ.get('DISPATCH_SMTP_PORT', '587')}.",
        )

    def authentication(self) -> AuthenticationStatus:
        """A relay may legitimately need no credentials, and that is ``ABSENT``.

        ``UNCONFIGURED`` would be wrong for a correctly configured open relay on
        a trusted network; ``ABSENT`` says the step was not performed, which is
        what actually happened.
        """
        if not self._config_value("DISPATCH_SMTP_HOST"):
            return AuthenticationStatus(
                ConnectorStatus.UNCONFIGURED,
                method=self.auth_method,
                credential_names=self.credential_keys,
                detail="No relay configured, so there is nothing to authenticate against.",
            )
        if not self._config_value("DISPATCH_SMTP_USER"):
            return AuthenticationStatus(
                ConnectorStatus.ABSENT,
                method="none",
                detail="The relay is configured without SMTP authentication.",
            )
        return AuthenticationStatus(
            ConnectorStatus.UNVERIFIED,
            method=self.auth_method,
            credential_names=self.credential_keys,
            detail=(
                "SMTP credentials are present. They are unproven until a message is actually "
                "accepted by the relay."
            ),
        )

    # ---------------------------------------------------------------- the verb

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        """``operation='send'``: hand the message to the existing transport.

        Every other operation is refused rather than ignored -- a connector that
        quietly returns nothing for a verb it does not implement is a connector
        whose caller thinks something happened.
        """
        if request.operation != "send":
            return self.failure(
                request,
                ConnectorError(
                    "provider_error",
                    f"{self.connector_name} implements 'send' only; {request.operation!r} is "
                    "not one of its operations.",
                ),
                status=ConnectorStatus.UNAVAILABLE,
            )

        params = dict(request.params)
        recipients = list(params.get("to") or [])
        subject = str(params.get("subject", ""))
        body = str(params.get("body", ""))
        fallback_id = str(params.get("fallback_id", "")) or "connector-message"

        if not recipients:
            return self.failure(
                request,
                ConnectorError(
                    "malformed_payload",
                    "A send request needs at least one recipient. Nothing was attempted.",
                ),
                status=ConnectorStatus.UNAVAILABLE,
            )

        receipt = self._delivery_module().send(subject, body, recipients, fallback_id)
        return self._classify(request, receipt, recipients)

    def _classify(
        self, request: ConnectorRequest, receipt: str, recipients: list[str]
    ) -> ConnectorResult:
        """Turn the transport's receipt sentence into a truth word.

        The order of these branches matters: a failure receipt also mentions a
        written file, so "delivery failed" is tested before the fallback shape,
        and only a receipt that begins with "sent via" is allowed to reach LIVE.
        """
        attempted = RetryStatus(1, request.max_attempts, False, 0.0)
        host = self._config_value("DISPATCH_SMTP_HOST")

        if receipt.startswith(RECEIPT_SENT_PREFIX):
            evidence = ExchangeEvidence.from_response(
                endpoint=host or receipt[len(RECEIPT_SENT_PREFIX):].split(" ")[0],
                response=receipt,
                transport="smtp",
            )
            payload = self.payload(
                PAYLOAD_KIND,
                {
                    "delivered": True,
                    "recipients": recipients,
                    "receipt": receipt,
                    "outbox_path": "",
                },
                status=ConnectorStatus.LIVE,
                source_reference=host,
                source_timestamp=utc_now(),
                confidence=1.0,
                evidence=evidence,
            )
            return self.success(request, payload, retry=attempted)

        if receipt.startswith(RECEIPT_FAILED_PREFIX):
            return self.failure(
                request,
                ConnectorError(
                    "transport_failure",
                    "The SMTP relay did not accept the message. It was written to "
                    "Archive/Outbox instead and delivered to nobody.",
                    retryable=True,
                    detail=receipt,
                ),
                status=ConnectorStatus.UNAVAILABLE,
                retry=attempted,
            )

        if receipt.startswith(RECEIPT_NOT_CONFIGURED_PREFIX):
            payload = self.payload(
                PAYLOAD_KIND,
                {
                    "delivered": False,
                    "recipients": recipients,
                    "receipt": receipt,
                    "outbox_path": receipt.split("written to ", 1)[-1],
                    "note": (
                        "SIMULATED delivery: an .eml file was written to Archive/Outbox. "
                        "No message reached any recipient."
                    ),
                },
                status=ConnectorStatus.SIMULATED,
                source_reference="Archive/Outbox",
                source_timestamp=utc_now(),
                confidence=0.0,
            )
            return self.success(request, payload, retry=attempted)

        # An unrecognised receipt is treated as a failure, not as a success. The
        # transport's wording changed and this connector no longer knows what
        # happened; claiming delivery on a sentence it cannot read is the one
        # outcome that would be worse than a false alarm.
        return self.failure(
            request,
            ConnectorError(
                "malformed_payload",
                "The mail transport returned a receipt this connector does not recognise, so "
                "whether the message was delivered is unknown.",
                detail=receipt,
            ),
            status=ConnectorStatus.UNAVAILABLE,
            retry=attempted,
        )
