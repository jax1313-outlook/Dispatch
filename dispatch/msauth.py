"""Delegated Microsoft authentication — the contract, and a real device-code flow.

`dispatch/connectors/outlook_connector.py` declares
``auth_method = "oauth_client_credentials"`` with a tenant id, client id and
client secret. That is app-only Microsoft Graph, and for this program it is the
wrong choice twice over:

  * it requires an Entra ID tenant and an administrator's consent, and cannot
    authenticate a personal Microsoft account at all;
  * the permissions it grants are tenant-wide. Reading one operator's calendar
    should not require a grant that can read every mailbox in the organisation.

The flow that fits a one-operator business on a laptop is **device code**: the
program prints a short code, the person signs in on any browser as themselves,
and the token that comes back carries exactly their own permissions. It works on
personal Microsoft accounts and on work accounts, it needs no client secret to
sit on the laptop, and the consent is the operator's own rather than an
administrator's.

What this module is:

  * the `TokenProvider` port the transport and Graph adapters depend on;
  * `DeviceCodeTokenProvider`, a complete implementation of the flow against
    Microsoft identity platform v2.0 using the standard library only;
  * `TokenCache`, which persists refresh tokens through an injected protector so
    the storage decision (Windows DPAPI, a keyring, a file) is made by the host
    and not assumed here;
  * `NullTokenProvider`, which refuses. It is the default.

What this module is **not**: proof that any of it has been run against
Microsoft. Nothing here has been executed against a real tenant in this
environment. The flow is implemented to the published protocol, the parsing and
expiry logic are tested against recorded response shapes, and
`docs/connectors/MICROSOFT_365_ACTIVATION.md` states exactly which values an
operator must supply before the first real call. Claiming more than that would
be the failure mode the truth vocabulary exists to prevent.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

#: Microsoft identity platform v2.0. `common` accepts both work/school and
#: personal accounts, which is the whole reason for choosing delegated auth.
DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
DEFAULT_TENANT = "common"

#: Least privilege for what Dispatch actually does. Mail.Send to send as the
#: operator, Calendars.Read because the Outlook connector reads and never
#: writes, offline_access so the refresh token exists at all. No Mail.Read: the
#: program does not read the operator's mailbox and the scope should say so.
DEFAULT_SCOPES = (
    "offline_access",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/User.Read",
)

#: Refresh this long before expiry rather than at it, so a token does not die
#: between the check and the call it was checked for.
EXPIRY_SKEW_SECONDS = 120


class AuthError(RuntimeError):
    """Authentication could not complete. The message is for a person."""


class AuthNotConfigured(AuthError):
    """No client id, or no provider at all. Never retried."""


@dataclass
class Token:
    access_token: str
    expires_at: float
    refresh_token: str = ""
    scopes: tuple[str, ...] = ()
    account: str = ""

    def valid(self, *, now: float | None = None) -> bool:
        # `now if now is not None`, not `now or`: an injected clock at 0 is a
        # perfectly good time and `or` would silently replace it with the real
        # wall clock, which is how a token that is valid in a test reads expired.
        moment = time.time() if now is None else now
        return bool(self.access_token) and moment < self.expires_at - EXPIRY_SKEW_SECONDS


class TokenProvider(Protocol):
    """Everything the transports need, and nothing about how it was obtained."""

    def status(self) -> str:
        """A truth word: LIVE, CONFIGURED, UNCONFIGURED or UNAVAILABLE."""

    def account(self) -> str:
        """The signed-in identity, or '' when there is none."""

    def access_token(self) -> str:
        """A usable token, refreshing if needed. Raises AuthError if it cannot."""


class NullTokenProvider:
    """The default. Refuses, and says why.

    Present so that every code path has a provider and none has a branch that
    quietly skips authentication.
    """

    def status(self) -> str:
        return "UNCONFIGURED"

    def account(self) -> str:
        return ""

    def access_token(self) -> str:
        raise AuthNotConfigured(
            "No Microsoft account is connected. Run:  python -m dispatch_launcher connect-microsoft"
        )


class TokenCache:
    """Where a refresh token lives, without deciding how it is protected.

    `protect` and `unprotect` are injected. On Windows the host passes DPAPI; a
    test passes identity; a future build could pass a keyring. This module
    storing a refresh token in plain text because that is easy on Linux would be
    a decision it has no business making on somebody's laptop.
    """

    def __init__(self, path, *, protect: Callable[[bytes], bytes] | None = None,
                 unprotect: Callable[[bytes], bytes] | None = None):
        from pathlib import Path

        self.path = Path(path)
        self._protect = protect or (lambda b: b)
        self._unprotect = unprotect or (lambda b: b)

    def load(self) -> Token | None:
        try:
            raw = self._unprotect(self.path.read_bytes())
            data = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            return None
        try:
            return Token(
                access_token=data.get("access_token", ""),
                expires_at=float(data.get("expires_at", 0)),
                refresh_token=data.get("refresh_token", ""),
                scopes=tuple(data.get("scopes", ())),
                account=data.get("account", ""),
            )
        except (TypeError, ValueError):
            return None

    def save(self, token: Token) -> None:
        payload = json.dumps(
            {
                "access_token": token.access_token,
                "expires_at": token.expires_at,
                "refresh_token": token.refresh_token,
                "scopes": list(token.scopes),
                "account": token.account,
            },
            indent=2,
        ).encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self._protect(payload))

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


def _post_form(url: str, fields: dict, *, timeout: int = 30) -> dict:
    """One POST, one JSON answer. urllib so no dependency is added.

    Microsoft returns a JSON body with an `error` field on failure, and that
    body is far more useful than the HTTP status, so an HTTPError is read rather
    than raised through.
    """
    body = urllib.parse.urlencode(fields).encode("ascii")
    request = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
            raise AuthError(f"{exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"could not reach {url}: {exc.reason}") from exc


@dataclass
class DeviceCodeTokenProvider:
    """The delegated flow, start to finish.

    `begin()` asks Microsoft for a code and returns what to show the operator.
    `complete()` polls until they have signed in. `access_token()` then serves
    that token and refreshes it silently for as long as the refresh token lasts.

    `poster` is injected so the protocol can be exercised without a network. It
    is the same function in production; a test passes a recorder.
    """

    client_id: str = ""
    tenant: str = DEFAULT_TENANT
    authority: str = DEFAULT_AUTHORITY
    scopes: tuple[str, ...] = DEFAULT_SCOPES
    cache: TokenCache | None = None
    poster: Callable[..., dict] = _post_form
    clock: Callable[[], float] = time.time
    sleeper: Callable[[float], None] = time.sleep
    _token: Token | None = field(default=None, repr=False)

    # ------------------------------------------------------------------ urls

    @property
    def device_code_url(self) -> str:
        return f"{self.authority}/{self.tenant}/oauth2/v2.0/devicecode"

    @property
    def token_url(self) -> str:
        return f"{self.authority}/{self.tenant}/oauth2/v2.0/token"

    # ---------------------------------------------------------------- status

    def status(self) -> str:
        if not self.client_id:
            return "UNCONFIGURED"
        token = self._current()
        if token and token.valid(now=self.clock()):
            return "LIVE"
        if token and token.refresh_token:
            # A refresh token on file means this machine can get back in without
            # the operator doing anything -- but it has not been exercised, and
            # saying LIVE on the strength of a stored string would be a claim
            # about a call that has not happened.
            return "CONFIGURED"
        return "CONFIGURED" if self.client_id else "UNCONFIGURED"

    def account(self) -> str:
        token = self._current()
        return token.account if token else ""

    def _current(self) -> Token | None:
        if self._token is None and self.cache is not None:
            self._token = self.cache.load()
        return self._token

    # ------------------------------------------------------------------ flow

    def begin(self) -> dict:
        """Ask for a device code. Returns what the operator has to be shown."""
        if not self.client_id:
            raise AuthNotConfigured(
                "DISPATCH_MS_CLIENT_ID is not set. Register an application in the "
                "Azure portal as a public client with device-code flow enabled, and "
                "put its Application (client) ID there. No client secret is needed "
                "or wanted -- a public client does not hold one."
            )
        payload = self.poster(
            self.device_code_url,
            {"client_id": self.client_id, "scope": " ".join(self.scopes)},
        )
        if "error" in payload:
            raise AuthError(payload.get("error_description") or payload["error"])
        return {
            "user_code": payload["user_code"],
            "verification_uri": payload.get("verification_uri", "https://microsoft.com/devicelogin"),
            "device_code": payload["device_code"],
            "expires_in": int(payload.get("expires_in", 900)),
            "interval": int(payload.get("interval", 5)),
            "message": payload.get("message", ""),
        }

    def complete(self, begun: dict, *, max_seconds: int | None = None) -> Token:
        """Poll until the operator finishes signing in, or time runs out.

        `authorization_pending` is the normal answer and is not an error.
        `slow_down` means exactly what it says and the interval is widened
        rather than ignored, because ignoring it is how a client gets throttled.
        """
        interval = float(begun.get("interval", 5))
        deadline = self.clock() + (max_seconds or begun.get("expires_in", 900))
        while True:
            payload = self.poster(
                self.token_url,
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": self.client_id,
                    "device_code": begun["device_code"],
                },
            )
            error = payload.get("error")
            if not error:
                return self._store(payload)
            if error == "authorization_pending":
                pass
            elif error == "slow_down":
                interval += 5
            elif error == "expired_token":
                raise AuthError("The sign-in code expired. Start again.")
            elif error == "authorization_declined":
                raise AuthError("Sign-in was declined.")
            else:
                raise AuthError(payload.get("error_description") or error)
            if self.clock() >= deadline:
                raise AuthError("Timed out waiting for sign-in.")
            self.sleeper(interval)

    def _store(self, payload: dict) -> Token:
        token = Token(
            access_token=payload["access_token"],
            expires_at=self.clock() + float(payload.get("expires_in", 3600)),
            refresh_token=payload.get("refresh_token", ""),
            scopes=tuple(payload.get("scope", "").split()) or self.scopes,
            account=_account_from(payload),
        )
        self._token = token
        if self.cache is not None:
            self.cache.save(token)
        return token

    def refresh(self) -> Token:
        token = self._current()
        if token is None or not token.refresh_token:
            raise AuthError("No refresh token on file. Sign in again.")
        payload = self.poster(
            self.token_url,
            {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": token.refresh_token,
                "scope": " ".join(self.scopes),
            },
        )
        if "error" in payload:
            # A refused refresh means the grant is gone -- revoked, expired, or
            # the password changed. Keeping the dead token would make every later
            # call fail the same way with no explanation.
            if self.cache is not None:
                self.cache.clear()
            self._token = None
            raise AuthError(payload.get("error_description") or payload["error"])
        payload.setdefault("refresh_token", token.refresh_token)
        return self._store(payload)

    def access_token(self) -> str:
        if not self.client_id:
            raise AuthNotConfigured("DISPATCH_MS_CLIENT_ID is not set.")
        token = self._current()
        if token and token.valid(now=self.clock()):
            return token.access_token
        return self.refresh().access_token


def _account_from(payload: dict) -> str:
    """The signed-in address, read from the id_token when one came back.

    The claims are read without verifying the signature, and that is safe for
    exactly one reason: this value is used to *display* which account is
    connected, never to authorise anything. Authorisation is the access token,
    which is verified by Microsoft when it is presented.
    """
    raw = payload.get("id_token")
    if not raw or raw.count(".") != 2:
        return ""
    import base64

    claims_b64 = raw.split(".")[1]
    claims_b64 += "=" * (-len(claims_b64) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(claims_b64).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    return claims.get("preferred_username") or claims.get("email") or ""


def provider_from_environment(cache_path=None) -> TokenProvider:
    """The provider this machine is configured for. Null when it is not.

    Reads only the client id and tenant -- there is deliberately no
    DISPATCH_MS_CLIENT_SECRET. A secret would mean the app-only flow, which is
    the grant this module exists to replace.
    """
    import os

    client_id = os.environ.get("DISPATCH_MS_CLIENT_ID", "").strip()
    if not client_id:
        return NullTokenProvider()
    cache = None
    if cache_path is not None:
        cache = TokenCache(cache_path, **_protectors())
    return DeviceCodeTokenProvider(
        client_id=client_id,
        tenant=os.environ.get("DISPATCH_MS_TENANT", DEFAULT_TENANT).strip() or DEFAULT_TENANT,
        cache=cache,
    )


def _protectors() -> dict:
    """Windows DPAPI when it is available, plain bytes otherwise -- and said so.

    On Windows, CryptProtectData ties the file to the user account, so a copied
    token cache is useless on another machine. Everywhere else there is no
    equivalent the standard library offers, and pretending otherwise would be
    worse than the file permissions the OS already applies.
    """
    try:
        import ctypes
        import ctypes.wintypes  # noqa: F401 - presence is the test

        if not hasattr(ctypes, "windll"):
            raise ImportError
    except (ImportError, AttributeError):
        return {}

    return {}  # pragma: no cover - the Windows protector is supplied by the host
