"""Connecting a Microsoft account, from the launcher, as the operator.

The device-code flow is the one that fits: Dispatch prints a short code, Mike
signs in on any browser as himself, and the token that comes back carries his
own permissions rather than an administrator's tenant-wide grant. It works on a
personal outlook.com account and on a Microsoft 365 work account, and no client
secret ever sits on the laptop.

This module is the operator surface for it. It performs no network call unless
DISPATCH_MS_CLIENT_ID is set, and it never reports a connection it did not make.
"""

from __future__ import annotations

import os
from pathlib import Path

from dispatch.msauth import (
    AuthError,
    AuthNotConfigured,
    DeviceCodeTokenProvider,
    TokenCache,
    provider_from_environment,
)
from dispatch.transport.selection import _token_cache_path, describe_transports


def _cache_path() -> Path | None:
    return _token_cache_path()


def status_text() -> str:
    provider = provider_from_environment(_cache_path())
    account = provider.account()
    lines = [f"  Microsoft account: {provider.status()}" + (f" ({account})" if account else "")]
    lines.append("")
    lines.append("  Outbound message transports:")
    for row in describe_transports():
        mark = ">" if row["selected"] else " "
        lines.append(f"    {mark} {row['describe']}")
    return "\n".join(lines)


def connect(*, printer=print, provider: DeviceCodeTokenProvider | None = None) -> int:
    """Run the device-code flow. Returns a process exit code.

    `printer` and `provider` are injected so the whole interaction can be driven
    by a test without a console and without Microsoft.
    """
    client_id = os.environ.get("DISPATCH_MS_CLIENT_ID", "").strip()
    if provider is None:
        if not client_id:
            printer(
                "  DISPATCH_MS_CLIENT_ID is not set.\n"
                "\n"
                "  Register an application in the Azure portal as a PUBLIC client with\n"
                "  device-code flow enabled, then set its Application (client) ID:\n"
                "\n"
                "      setx DISPATCH_MS_CLIENT_ID <the application id>\n"
                "\n"
                "  There is no client secret. A public client does not hold one, and the\n"
                "  secret-based flow would grant tenant-wide mailbox access this program\n"
                "  neither needs nor wants.\n"
                "\n"
                "  Full steps: docs/connectors/MICROSOFT_365_ACTIVATION.md"
            )
            return 1
        cache = TokenCache(_cache_path()) if _cache_path() else None
        provider = DeviceCodeTokenProvider(client_id=client_id, cache=cache)

    try:
        begun = provider.begin()
    except AuthNotConfigured as exc:
        printer(f"  {exc}")
        return 1
    except AuthError as exc:
        printer(f"  Could not start sign-in: {exc}")
        return 2

    printer("")
    printer(f"  1. Open:  {begun['verification_uri']}")
    printer(f"  2. Enter this code:  {begun['user_code']}")
    printer("  3. Sign in as the account Dispatch should send mail as.")
    printer("")
    printer("  Waiting for you to finish...")

    try:
        token = provider.complete(begun)
    except AuthError as exc:
        printer(f"  Sign-in did not complete: {exc}")
        return 2

    printer("")
    printer(f"  Connected as {token.account or 'the signed-in account'}.")
    printer("  Dispatch can now send mail through Microsoft Graph as that account.")
    printer("")
    printer("  This proves the sign-in worked. It does not prove a message has been")
    printer("  delivered -- send one and look in Sent Items.")
    return 0


def disconnect(*, printer=print) -> int:
    path = _cache_path()
    if path is None:
        printer("  No token cache is configured; nothing to remove.")
        return 0
    TokenCache(path).clear()
    printer(f"  Removed the stored Microsoft token ({path}).")
    printer("  Outbound mail falls back to whatever else is configured.")
    return 0
