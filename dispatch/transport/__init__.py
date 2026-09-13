"""How a message leaves Dispatch — as a port, with the provider behind it.

Two facts from the audit shaped this package, and neither is about code quality.

**There is no transport in the connector layer at all.** `dispatch/connectors/`
is ~3,000 lines of capability declaration, authorisation gating and refusal
shape across eight connectors, and it contains no HTTP client: no `requests`, no
`httpx`, no `urllib`, no `msal`. "Eight connectors" is real architecture, and
100% of the integration cost -- OAuth, token refresh, pagination, retry, delta
sync -- was still ahead. Nothing here changes that honestly-stated position by
pretending a connection exists.

**The two auth methods chosen are the two Microsoft is closing.**
`outlook_connector.py` declares `oauth_client_credentials` with a tenant id,
client id and secret. That is app-only Graph: it needs an Entra ID tenant (it
cannot work against a personal Microsoft account at all) and it grants
tenant-wide mailbox access. For one operator reading one calendar, delegated
device-code is both the correct scope and the only flow that works on a personal
account. Meanwhile `cin_lite/email_delivery.py` sends with
`smtplib.login(user, password)` on port 587 -- SMTP AUTH basic authentication,
which Microsoft 365 disables by default on every tenant and is retiring. The one
path that actually reaches brokers is built on the mechanism being switched off.

So: a port, and adapters behind it.

    OutboundMessage  ->  MessageTransport  ->  one of
                                                 FileOutboxTransport   SIMULATED
                                                 SmtpBasicTransport    LIVE, legacy
                                                 SmtpOAuth2Transport   LIVE, XOAUTH2
                                                 GraphMailTransport    LIVE, Graph

`select_transport()` returns the one this machine is configured for **and the
truth word for it**, so a surface renders what is actually happening rather than
a claim about it. With nothing configured that is `FileOutboxTransport` and
`SIMULATED`, which is what Dispatch does today and what it will keep saying until
somebody configures a provider.

No adapter here invents a token. `SmtpOAuth2Transport` and `GraphMailTransport`
both require a `TokenProvider` (`dispatch/msauth.py`), and with none supplied
they refuse with `UNCONFIGURED` rather than attempting an anonymous call that
would fail confusingly at the server.
"""

from __future__ import annotations

from dispatch.transport.contract import (
    MessageTransport,
    OutboundMessage,
    TransportError,
    TransportResult,
    TransportUnconfigured,
)
from dispatch.transport.selection import (
    TRANSPORT_ORDER,
    describe_transports,
    select_transport,
)

__all__ = [
    "MessageTransport",
    "OutboundMessage",
    "TransportError",
    "TransportResult",
    "TransportUnconfigured",
    "TRANSPORT_ORDER",
    "describe_transports",
    "select_transport",
]
