"""The delegated Microsoft flow, proven against the protocol — not against Microsoft.

`outlook_connector.py` declares oauth_client_credentials: app-only Graph, which
requires an Entra ID tenant, cannot authenticate a personal Microsoft account at
all, and grants tenant-wide mailbox permissions. For one operator reading one
calendar, delegated device code is both the correct scope and the only flow that
works on a personal account.

Every test here drives the flow through an injected poster. Nothing has been run
against Microsoft in this environment and no test in this file claims otherwise:
what is proven is the request shape, the polling rules, the expiry arithmetic and
the refusal behaviour.
"""

from __future__ import annotations

import json

import pytest

from dispatch.msauth import (
    DEFAULT_SCOPES,
    AuthError,
    AuthNotConfigured,
    DeviceCodeTokenProvider,
    NullTokenProvider,
    Token,
    TokenCache,
    provider_from_environment,
)

CLIENT_ID = "11111111-2222-3333-4444-555555555555"


class Poster:
    """Records requests and replays scripted answers."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, url, fields, timeout=30):
        self.calls.append({"url": url, "fields": fields})
        return self.answers.pop(0) if self.answers else {"error": "unexpected_call"}


DEVICE_CODE = {
    "user_code": "ABCD-EFGH",
    "device_code": "dev-code",
    "verification_uri": "https://microsoft.com/devicelogin",
    "expires_in": 900,
    "interval": 5,
    "message": "To sign in, use a web browser...",
}


def _id_token(username="mike@example.com") -> str:
    import base64

    claims = base64.urlsafe_b64encode(
        json.dumps({"preferred_username": username}).encode()
    ).decode().rstrip("=")
    return f"header.{claims}.signature"


TOKEN_OK = {
    "access_token": "access-1",
    "refresh_token": "refresh-1",
    "expires_in": 3600,
    "scope": " ".join(DEFAULT_SCOPES),
    "id_token": _id_token(),
}


class TestTheDefaultIsRefusal:
    def test_no_client_id_means_no_provider(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_MS_CLIENT_ID", raising=False)
        provider = provider_from_environment()
        assert isinstance(provider, NullTokenProvider)
        assert provider.status() == "UNCONFIGURED"

    def test_it_says_what_to_do_rather_than_failing_opaquely(self):
        with pytest.raises(AuthNotConfigured) as caught:
            NullTokenProvider().access_token()
        assert "connect-microsoft" in str(caught.value)

    def test_there_is_no_client_secret_setting(self, monkeypatch):
        """A secret would mean the app-only grant this module exists to replace."""
        import dispatch.msauth as module

        source = module.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        assert "DISPATCH_MS_CLIENT_SECRET" not in text.replace(
            "there is deliberately no\n    DISPATCH_MS_CLIENT_SECRET", ""
        ) or text.count("DISPATCH_MS_CLIENT_SECRET") == 1


class TestTheDeviceCodeFlow:
    def test_begin_asks_for_a_code_with_the_least_privilege_scopes(self):
        poster = Poster(DEVICE_CODE)
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, poster=poster)

        begun = provider.begin()

        assert begun["user_code"] == "ABCD-EFGH"
        assert poster.calls[0]["url"].endswith("/common/oauth2/v2.0/devicecode")
        scopes = poster.calls[0]["fields"]["scope"].split()
        assert "offline_access" in scopes
        assert "https://graph.microsoft.com/Mail.Send" in scopes
        # The program does not read the operator's mailbox, so the scope must not
        # ask to.
        assert not any(s.endswith("Mail.Read") for s in scopes)

    def test_begin_refuses_without_a_client_id_and_says_how_to_get_one(self):
        with pytest.raises(AuthNotConfigured) as caught:
            DeviceCodeTokenProvider().begin()
        assert "public client" in str(caught.value)

    def test_complete_polls_through_authorization_pending(self):
        slept = []
        poster = Poster({"error": "authorization_pending"}, {"error": "authorization_pending"}, TOKEN_OK)
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID, poster=poster, sleeper=slept.append
        )

        token = provider.complete(DEVICE_CODE)

        assert token.access_token == "access-1"
        assert token.refresh_token == "refresh-1"
        assert token.account == "mike@example.com"
        assert len(slept) == 2

    def test_slow_down_widens_the_interval_rather_than_being_ignored(self):
        slept = []
        poster = Poster({"error": "slow_down"}, TOKEN_OK)
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID, poster=poster, sleeper=slept.append
        )
        provider.complete(DEVICE_CODE)
        assert slept == [10.0], "ignoring slow_down is how a client gets throttled"

    @pytest.mark.parametrize(
        "error,fragment",
        [("expired_token", "expired"), ("authorization_declined", "declined")],
    )
    def test_a_terminal_error_stops_immediately(self, error, fragment):
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID, poster=Poster({"error": error}), sleeper=lambda s: None
        )
        with pytest.raises(AuthError) as caught:
            provider.complete(DEVICE_CODE)
        assert fragment in str(caught.value).lower()

    def test_it_gives_up_when_the_code_expires(self):
        clock = iter([0, 0, 1000, 1000, 2000])
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID,
            poster=Poster({"error": "authorization_pending"}, {"error": "authorization_pending"}),
            sleeper=lambda s: None,
            clock=lambda: next(clock),
        )
        with pytest.raises(AuthError) as caught:
            provider.complete(DEVICE_CODE)
        assert "Timed out" in str(caught.value)


class TestTokensAndRefresh:
    def test_a_valid_token_is_served_without_a_call(self):
        poster = Poster()
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, poster=poster, clock=lambda: 0)
        provider._token = Token(access_token="a", expires_at=10_000, refresh_token="r")
        assert provider.access_token() == "a"
        assert poster.calls == []

    def test_an_expiring_token_is_refreshed_before_it_dies(self):
        """Refreshed early, so it cannot expire between the check and the call."""
        poster = Poster({"access_token": "access-2", "expires_in": 3600})
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, poster=poster, clock=lambda: 0)
        provider._token = Token(access_token="old", expires_at=60, refresh_token="r")

        assert provider.access_token() == "access-2"
        assert poster.calls[0]["fields"]["grant_type"] == "refresh_token"

    def test_a_refresh_keeps_the_existing_refresh_token_when_none_comes_back(self):
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID,
            poster=Poster({"access_token": "a2", "expires_in": 3600}),
            clock=lambda: 0,
        )
        provider._token = Token(access_token="old", expires_at=0, refresh_token="keep-me")
        assert provider.refresh().refresh_token == "keep-me"

    def test_a_refused_refresh_clears_the_cache_rather_than_failing_forever(self, tmp_path):
        cache = TokenCache(tmp_path / "token.json")
        cache.save(Token(access_token="old", expires_at=0, refresh_token="dead"))
        provider = DeviceCodeTokenProvider(
            client_id=CLIENT_ID,
            poster=Poster({"error": "invalid_grant", "error_description": "revoked"}),
            cache=cache, clock=lambda: 0,
        )
        with pytest.raises(AuthError):
            provider.access_token()
        assert cache.load() is None

    def test_no_refresh_token_says_sign_in_again(self):
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, poster=Poster(), clock=lambda: 0)
        with pytest.raises(AuthError) as caught:
            provider.access_token()
        assert "Sign in again" in str(caught.value)


class TestStatusIsHonest:
    def test_no_client_id_is_unconfigured(self):
        assert DeviceCodeTokenProvider().status() == "UNCONFIGURED"

    def test_a_client_id_alone_is_configured_not_live(self):
        assert DeviceCodeTokenProvider(client_id=CLIENT_ID).status() == "CONFIGURED"

    def test_a_stored_refresh_token_is_configured_not_live(self, tmp_path):
        """A refresh token on file has not been exercised. LIVE would be a claim
        about a call that has not happened."""
        cache = TokenCache(tmp_path / "t.json")
        cache.save(Token(access_token="expired", expires_at=0, refresh_token="r"))
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, cache=cache, clock=lambda: 10_000)
        assert provider.status() == "CONFIGURED"

    def test_a_valid_token_is_live(self, tmp_path):
        cache = TokenCache(tmp_path / "t.json")
        cache.save(Token(access_token="a", expires_at=10_000, refresh_token="r", account="m@e.test"))
        provider = DeviceCodeTokenProvider(client_id=CLIENT_ID, cache=cache, clock=lambda: 0)
        assert provider.status() == "LIVE"
        assert provider.account() == "m@e.test"


class TestTheTokenCache:
    def test_it_round_trips(self, tmp_path):
        cache = TokenCache(tmp_path / "t.json")
        cache.save(Token(access_token="a", expires_at=123.0, refresh_token="r",
                         scopes=("s",), account="m@e.test"))
        loaded = cache.load()
        assert loaded.access_token == "a"
        assert loaded.account == "m@e.test"

    def test_a_missing_or_corrupt_file_is_no_token_rather_than_a_crash(self, tmp_path):
        assert TokenCache(tmp_path / "absent.json").load() is None
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        assert TokenCache(bad).load() is None

    def test_the_protector_is_injected_not_assumed(self, tmp_path):
        """How a refresh token is protected is the host's decision. This module
        writing plain text because that is easy on Linux would be making it."""
        protected = {}

        def protect(raw):
            protected["called"] = True
            return b"X" + raw

        cache = TokenCache(tmp_path / "t.json", protect=protect, unprotect=lambda b: b[1:])
        cache.save(Token(access_token="a", expires_at=1.0))
        assert protected["called"]
        assert (tmp_path / "t.json").read_bytes().startswith(b"X")
        assert cache.load().access_token == "a"
