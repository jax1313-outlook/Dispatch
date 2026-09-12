"""Which transport this machine will actually use, and what to call it.

Order matters and is not a preference list: it is most-specific-first. A machine
with a Microsoft account connected should use Graph even if an old SMTP host is
still sitting in the environment, because the newer setting is the one somebody
configured deliberately and the older one is what they are migrating off.
"""

from __future__ import annotations

import os

from dispatch.msauth import provider_from_environment
from dispatch.transport.adapters import (
    FileOutboxTransport,
    GraphMailTransport,
    SmtpBasicTransport,
    SmtpOAuth2Transport,
)
from dispatch.transport.contract import LIVE, SIMULATED, UNCONFIGURED

#: Most specific first. FileOutbox is last and always succeeds, so there is
#: always a transport and never a branch where Dispatch has nowhere to put a
#: message it has already decided to send.
TRANSPORT_ORDER = ("graph", "smtp_oauth2", "smtp_basic", "file_outbox")


def _token_cache_path():
    from pathlib import Path

    explicit = os.environ.get("DISPATCH_MS_TOKEN_CACHE")
    if explicit:
        return Path(explicit)
    memory = os.environ.get("DISPATCH_MEMORY_ROOT")
    if memory:
        return Path(memory) / "auth" / "microsoft-token.json"
    return None


def build(transport_id: str, *, token_provider=None):
    """One transport by name, with nothing decided for it."""
    provider = token_provider or provider_from_environment(_token_cache_path())
    if transport_id == "graph":
        return GraphMailTransport(token_provider=provider)
    if transport_id == "smtp_oauth2":
        return SmtpOAuth2Transport(token_provider=provider)
    if transport_id == "smtp_basic":
        return SmtpBasicTransport()
    if transport_id == "file_outbox":
        return FileOutboxTransport()
    raise ValueError(f"unknown transport: {transport_id}")


def select_transport(*, token_provider=None, preferred: str | None = None):
    """The transport this machine is configured for.

    `DISPATCH_TRANSPORT` pins one explicitly, which is what an operator
    migrating between providers needs -- otherwise adding a Microsoft client id
    would silently move every outbound message onto Graph mid-week.
    """
    pinned = preferred or os.environ.get("DISPATCH_TRANSPORT", "").strip()
    if pinned:
        return build(pinned, token_provider=token_provider)

    for transport_id in TRANSPORT_ORDER:
        transport = build(transport_id, token_provider=token_provider)
        if transport.status() != UNCONFIGURED:
            return transport
    return FileOutboxTransport()


def describe_transports(*, token_provider=None) -> list[dict]:
    """Every transport and its state, for the Settings and Maintenance screens.

    Rendering all four rather than only the chosen one is deliberate: the
    question an operator actually has is "why is it still writing .eml files",
    and the answer is visible only when the ones that are UNCONFIGURED are shown
    alongside the one that was picked.
    """
    chosen = select_transport(token_provider=token_provider)
    rows = []
    for transport_id in TRANSPORT_ORDER:
        transport = build(transport_id, token_provider=token_provider)
        rows.append(
            {
                "transport_id": transport_id,
                "provider": transport.provider_name,
                "status": transport.status(),
                "describe": transport.describe(),
                "selected": transport_id == chosen.transport_id,
            }
        )
    return rows


def outbound_status() -> dict:
    """One summary a screen can render without knowing about transports."""
    transport = select_transport()
    status = transport.status()
    return {
        "transport_id": transport.transport_id,
        "status": status,
        "describe": transport.describe(),
        "delivering": status == LIVE,
        "simulated": status == SIMULATED,
    }
