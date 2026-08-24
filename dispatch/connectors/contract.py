"""The connector contract — one shape every external boundary speaks.

Operational Readiness Mission Section 6. Dispatch has to be ready to talk to
outside systems -- a load board, an accounting package, a scanner, Outlook, an
SMTP relay, a mapping provider -- **before any of them are chosen**. The danger
in building that readiness early is not that the code is unused; it is that an
unused integration quietly starts *looking* used. A placeholder that returns a
plausible number, a health field that defaults to "ok", a card that renders
sample data without a label: each is a false connection claim, and a dispatcher
who believes one of them has been lied to by his own software.

So this module defines the contract, and the contract is built to make the lie
structurally hard rather than merely discouraged:

**Status is not optional and not free-text.** Every payload, configuration
answer, authentication answer, health answer and audit row carries a
:class:`ConnectorStatus`, whose members are exactly the mission's Section 1.8
truth words. There is no `ok`, no `connected`, no `active`, no `healthy`. Words
that a reader could mistake for evidence of a real exchange -- CONNECTED,
VERIFIED, CURRENT, ONLINE -- are listed in :data:`FORBIDDEN_STATUS_WORDS` and
:func:`parse_status` refuses them by name, so the refusal is visible in a
traceback rather than absent from a code review.

**LIVE requires evidence, at construction time.** :class:`Provenance` refuses to
exist with ``status=LIVE`` and no :class:`ExchangeEvidence`. Evidence means an
endpoint, a response fingerprint and a completion timestamp -- artifacts only a
real exchange produces. A connector cannot claim LIVE by setting a field,
because the field cannot be set alone.

**A capability cannot be declared for something a connector may never own.**
Section 6.2 puts lifecycle transitions, human decisions, pricing authority,
acceptance authority, scheduling truth and operational doctrine outside the
boundary. :class:`CapabilityDeclaration` refuses to be constructed with any of
them, so the prohibition is enforced where the connector is *written*, not only
where it runs (the runtime half lives in ``dispatch/connectors/boundary.py``).

**Secrets are scrubbed on the way in, not on the way out.** Every free-text
field that could carry a credential -- an error detail, a health message, an
audit reason -- runs through :func:`redact` inside ``__post_init__``. Redacting
at render time would mean the secret still exists in the object, and one
consumer that formats it by hand undoes the protection everywhere. Redacting at
construction means the value is never in the record to begin with.

**A refusal says which connector refused and why.** ``UNCONFIGURED`` on its own
is a state; :meth:`ConnectorResult.refusal_message` turns it into a sentence a
human can act on. Section 6.7 requires that a function needing a connector fail
with a clear, labeled refusal rather than degrade silently, and
:func:`require_payload` is the one call site that turns a refusal into an
exception carrying that sentence.

The truth vocabulary is duplicated here rather than imported from
``dispatch/readiness.py`` on purpose, following THE MIKE RULE (DECISION_LOG.md):
subsystems stay standalone and do not reach across each other for constants.
``tests/test_connectors.py`` asserts the two lists still agree, so the
duplication cannot drift.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, TypeVar, runtime_checkable


# --------------------------------------------------------------------------- vocabulary


class ConnectorStatus(str, Enum):
    """Section 1.8's truth words, and nothing else.

    ``str`` mixin so a status compares equal to its word, serialises into JSON
    unchanged, and can be dropped straight into a template. The point of the
    enum is that there is no other way to spell any of these.
    """

    LIVE = "LIVE"
    """Actual communication with the real external system occurred and is evidenced."""

    CONFIGURED = "CONFIGURED"
    """Credentials/endpoints present and validated; no live exchange evidenced yet."""

    UNCONFIGURED = "UNCONFIGURED"
    """Required configuration absent."""

    SIMULATED = "SIMULATED"
    """A mock or stand-in produced the data."""

    UNAVAILABLE = "UNAVAILABLE"
    """Configured but the last attempt failed."""

    MANUAL = "MANUAL"
    """A human performed the step outside Dispatch and recorded it."""

    ABSENT = "ABSENT"
    """The step was not performed at all."""

    UNVERIFIED = "UNVERIFIED"
    """Implemented in code but not proven on Mike's machine."""

    def __str__(self) -> str:  # pragma: no cover - trivial, but keeps f-strings honest
        return self.value


#: The vocabulary as bare words. Mirrors ``dispatch.readiness.TRUTH_WORDS``.
TRUTH_WORDS: tuple[str, ...] = tuple(s.value for s in ConnectorStatus)

#: Words that read like evidence of a real exchange and are not in the
#: vocabulary. Named explicitly so a connector author who reaches for one gets a
#: refusal that says why, instead of an enum lookup failure they might "fix" by
#: adding the member.
FORBIDDEN_STATUS_WORDS: frozenset[str] = frozenset(
    {
        "CONNECTED", "VERIFIED", "CURRENT", "ONLINE", "ACTIVE", "OK", "HEALTHY",
        "READY", "REAL", "SUCCESS", "GOOD", "UP", "ENABLED", "WORKING",
    }
)


def parse_status(word: str) -> ConnectorStatus:
    """Turn a word into a status, refusing the near-misses by name."""
    text = (word or "").strip().upper()
    if text in FORBIDDEN_STATUS_WORDS:
        raise ValueError(
            f"{word!r} is not a Dispatch truth word. It reads as evidence of a real "
            f"exchange and is not one. Use one of: {', '.join(TRUTH_WORDS)}."
        )
    try:
        return ConnectorStatus(text)
    except ValueError:
        raise ValueError(
            f"{word!r} is not one of the Section 1.8 truth words: {', '.join(TRUTH_WORDS)}. "
            "Synonyms and softer variants are not allowed."
        ) from None


#: Statuses that assert a real exchange happened and therefore require
#: :class:`ExchangeEvidence` before they can be attached to a payload.
EVIDENCED_STATUSES: frozenset[ConnectorStatus] = frozenset({ConnectorStatus.LIVE})

#: Statuses that must never render as operational intelligence without their
#: label being shown alongside the data (Section 6.3).
LABEL_REQUIRED_STATUSES: frozenset[ConnectorStatus] = frozenset(
    {ConnectorStatus.SIMULATED, ConnectorStatus.UNAVAILABLE, ConnectorStatus.UNCONFIGURED,
     ConnectorStatus.MANUAL, ConnectorStatus.ABSENT, ConnectorStatus.UNVERIFIED}
)


# --------------------------------------------------------------------------- redaction

#: Environment variables whose *values* are secrets. Any of these values
#: appearing inside a status, error, log line or audit row would be a leak, so
#: :func:`redact` removes them by value wherever they turn up -- including
#: inside an exception message a provider library raised, which is the usual way
#: a password escapes.
SECRET_ENV_VARS: tuple[str, ...] = (
    "DISPATCH_SMTP_PASSWORD",
    "DISPATCH_SMTP_USER",
    "DISPATCH_EMAIL_SECRET",
    "PORTAL_SECRET_KEY",
    "ANTHROPIC_API_KEY",
    "DISPATCH_SAM_API_KEY",
    "DISPATCH_LOAD_API_KEY",
    "DISPATCH_ACCOUNTING_API_KEY",
    "DISPATCH_SCANNER_API_KEY",
    "DISPATCH_OUTLOOK_CLIENT_SECRET",
    "DISPATCH_MAPPING_API_KEY",
    "DISPATCH_ROUTE_RISK_API_KEY",
    "DISPATCH_EXTERNAL_INTEL_API_KEY",
)

REDACTED = "[REDACTED]"

#: Shapes a secret takes when it is embedded in a string rather than being one:
#: an Authorization header, a query parameter, a connection string password.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(bearer|basic|token)\s+[A-Za-z0-9._\-+/=]{6,}"),
    re.compile(r"(?i)\b(api[_-]?key|apikey|password|passwd|secret|client[_-]?secret|access[_-]?token)"
               r"\s*[=:]\s*[^\s,;&)'\"]+"),
)

#: Values short enough that removing them by value would redact ordinary prose.
#: A four-character password is not protected here; it is also not a password.
_MIN_SECRET_LENGTH = 6


def redact(text: str) -> str:
    """Remove secret values and secret-shaped fragments from a string.

    Two passes, in this order. First every configured secret's literal value is
    replaced, because that catches a credential no pattern would recognise.
    Then the patterns catch credentials this process never held -- a provider's
    error text quoting the header it rejected, for instance.
    """
    if not text:
        return text
    cleaned = str(text)
    for var in SECRET_ENV_VARS:
        value = os.environ.get(var, "")
        if value and len(value) >= _MIN_SECRET_LENGTH:
            cleaned = cleaned.replace(value, REDACTED)
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(lambda m: f"{m.group(1)} {REDACTED}", cleaned)
    return cleaned


def contains_secret(text: str) -> bool:
    """True when a string still carries a configured secret value.

    Used by the tests, and by :func:`redact`'s callers when they want to assert
    rather than clean.
    """
    if not text:
        return False
    haystack = str(text)
    for var in SECRET_ENV_VARS:
        value = os.environ.get(var, "")
        if value and len(value) >= _MIN_SECRET_LENGTH and value in haystack:
            return True
    return False


# --------------------------------------------------------------------------- time / ids


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(stamp: str) -> datetime | None:
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = datetime.strptime(stamp, fmt)
        except (ValueError, TypeError):
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


#: Public name for the timestamp helper. The connector modules all stamp times
#: the same way -- ``%Y-%m-%dT%H:%M:%SZ``, matching every other timestamp in
#: this repository -- and importing one function is how that stays true.
utc_now = _utc_now


# --------------------------------------------------------------------------- evidence


@dataclass(frozen=True)
class ExchangeEvidence:
    """Proof that a real exchange with a real external system happened.

    Every field here is something only an actual round trip produces: the
    endpoint that answered, a fingerprint of what it said, and when it finished.
    A connector that has not talked to anything cannot fill these in, which is
    the whole mechanism behind "no LIVE without evidence".

    The fingerprint is a SHA-256 of the response bytes rather than the bytes
    themselves. It is enough to prove two readings came from the same answer and
    to tie an audit row to a payload, and it cannot leak a response body that
    might contain a customer's data or a bearer token.
    """

    endpoint: str
    response_fingerprint: str
    completed_at: str = field(default_factory=_utc_now)
    request_id: str = ""
    transport: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoint", redact(self.endpoint))
        if not self.endpoint:
            raise ValueError("Exchange evidence needs the endpoint that answered.")
        if not self.response_fingerprint:
            raise ValueError(
                "Exchange evidence needs a fingerprint of the response. Without one there "
                "is nothing distinguishing a real answer from an assumed one."
            )
        if not self.completed_at:
            raise ValueError("Exchange evidence needs the time the exchange completed.")

    @classmethod
    def from_response(
        cls,
        endpoint: str,
        response: bytes | str,
        *,
        transport: str = "",
        request_id: str = "",
    ) -> "ExchangeEvidence":
        raw = response.encode("utf-8", "replace") if isinstance(response, str) else response
        return cls(
            endpoint=endpoint,
            response_fingerprint=hashlib.sha256(raw).hexdigest(),
            transport=transport,
            request_id=request_id or _new_id("REQ"),
        )

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "response_fingerprint": self.response_fingerprint,
            "completed_at": self.completed_at,
            "request_id": self.request_id,
            "transport": self.transport,
        }


# --------------------------------------------------------------------------- identity


@dataclass(frozen=True)
class ConnectorIdentity:
    """Who the connector is, and which provider (if any) it has been pointed at.

    ``provider_id`` empty means no provider has been selected. That is the
    honest state for seven of the eight connectors today and it is deliberately
    not defaulted to a vendor name: naming a provider Dispatch has not been
    configured for would be a false connection claim in the identity itself.
    """

    connector_id: str
    connector_name: str
    provider_id: str = ""
    provider_name: str = ""

    def __post_init__(self) -> None:
        if not self.connector_id or not self.connector_name:
            raise ValueError("A connector needs both an id and a human-readable name.")

    @property
    def provider_selected(self) -> bool:
        return bool(self.provider_id)

    @property
    def provider_label(self) -> str:
        return self.provider_name or self.provider_id or "no provider selected"

    def to_dict(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "provider_selected": self.provider_selected,
            "provider_label": self.provider_label,
        }


#: Section 6.2, verbatim in substance: what a connector transports and
#: normalizes, and what it never owns. A capability naming any of these is
#: refused at construction.
FORBIDDEN_CAPABILITIES: tuple[str, ...] = (
    "lifecycle transitions",
    "human decisions",
    "pricing authority",
    "acceptance authority",
    "scheduling truth",
    "operational doctrine",
)

_FORBIDDEN_CAPABILITY_TOKENS: tuple[str, ...] = (
    "lifecycle", "transition", "decide", "decision", "approve", "approval",
    "accept", "acceptance", "price", "pricing", "rate authority", "schedule truth",
    "scheduling truth", "doctrine", "commit load", "cancel load",
)


@dataclass(frozen=True)
class CapabilityDeclaration:
    """What one connector can collect, what it can produce, and what it may not.

    ``collects`` and ``produces`` are free-text on purpose -- a mapping provider
    and a scanner have nothing in common to enumerate -- but both are checked
    against :data:`_FORBIDDEN_CAPABILITY_TOKENS`. A connector cannot declare
    "approve load" or "set pricing" even as a string, so the Section 6.2
    prohibition is enforced at the point a connector is authored.

    ``requires_human_authorization`` is the third list and the interesting one:
    an operation that a human must authorise before it runs at all (Outlook
    event creation is the live example). Listing it here does not grant it; it
    records that the operation exists and is gated.
    """

    collects: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    requires_human_authorization: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        for group in (self.collects, self.produces, self.requires_human_authorization):
            for item in group:
                lowered = item.lower()
                for token in _FORBIDDEN_CAPABILITY_TOKENS:
                    if token in lowered:
                        raise ValueError(
                            f"Capability {item!r} claims authority a connector may never hold. "
                            f"Section 6.2 reserves {', '.join(FORBIDDEN_CAPABILITIES)} to Spine, "
                            "Route Risk evaluation, COMI, Publisher and Mike."
                        )

    @property
    def never(self) -> tuple[str, ...]:
        """What every connector is structurally barred from, listed for display."""
        return FORBIDDEN_CAPABILITIES

    def to_dict(self) -> dict:
        return {
            "collects": list(self.collects),
            "produces": list(self.produces),
            "requires_human_authorization": list(self.requires_human_authorization),
            "never": list(self.never),
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- status answers


@dataclass(frozen=True)
class ConfigurationStatus:
    """Whether the configuration a connector needs is present -- by key name only.

    ``present_keys`` holds names, never values, and that is the entire security
    design of this dataclass: there is no field a value could be put in. A
    connector answering "am I configured" therefore cannot leak the credential
    that makes it so, however carelessly the answer is later rendered.
    """

    status: ConnectorStatus
    required_keys: tuple[str, ...] = ()
    present_keys: tuple[str, ...] = ()
    missing_keys: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", redact(self.detail))
        if not isinstance(self.status, ConnectorStatus):
            raise ValueError(
                f"{self.status!r} is not a Dispatch truth word. Pass a ConnectorStatus member; "
                f"parse_status() converts a word into one and refuses the near-misses."
            )

    @property
    def configured(self) -> bool:
        return self.status is ConnectorStatus.CONFIGURED

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "configured": self.configured,
            "required_keys": list(self.required_keys),
            "present_keys": list(self.present_keys),
            "missing_keys": list(self.missing_keys),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class AuthenticationStatus:
    """Whether the connector can authenticate -- again, names only.

    ``UNVERIFIED`` is the honest answer for a connector whose credentials are
    present but which has never completed an authenticated call: the code is
    there, nothing has proven it on Mike's machine. ``CONFIGURED`` here means an
    authentication handshake actually validated, which for every connector in
    this repository today is not yet true.
    """

    status: ConnectorStatus
    method: str = "none"
    credential_names: tuple[str, ...] = ()
    detail: str = ""
    last_authenticated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", redact(self.detail))
        for name in self.credential_names:
            if contains_secret(name):
                raise ValueError(
                    "credential_names carries a secret value. This field names credentials; "
                    "it never holds them."
                )
        if self.status is ConnectorStatus.LIVE and not self.last_authenticated_at:
            raise ValueError(
                "LIVE authentication requires the timestamp of the authenticated exchange "
                "that proved it."
            )

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "method": self.method,
            "credential_names": list(self.credential_names),
            "detail": self.detail,
            "last_authenticated_at": self.last_authenticated_at,
        }


@dataclass(frozen=True)
class HealthStatus:
    """Connection health and the last successful communication.

    There is no boolean here. "Healthy" is exactly the kind of word that lets an
    unconfigured connector render green, so health is a truth word plus the two
    timestamps that back it: when the last attempt happened, and when the last
    success did. A connector that has never been attempted reports ``ABSENT``
    with both timestamps empty, which is a different and more useful statement
    than "unhealthy".
    """

    status: ConnectorStatus
    last_attempt_at: str = ""
    last_success_at: str = ""
    last_error: str = ""
    consecutive_failures: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "last_error", redact(self.last_error))
        if self.status is ConnectorStatus.LIVE and not self.last_success_at:
            raise ValueError(
                "LIVE health requires the timestamp of the last successful communication. "
                "Without it the claim has no evidence behind it."
            )

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "last_attempt_at": self.last_attempt_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


# --------------------------------------------------------------------------- provenance


@dataclass(frozen=True)
class Provenance:
    """Where one piece of connector data came from, and how much to trust it.

    Section 6.3 requires source timestamp, received timestamp, source reference,
    freshness and confidence to travel *with* the payload. Freshness is derived
    rather than stored -- a stored freshness is a number that was true once --
    and confidence is a declared 0..1 the connector owns, never a score computed
    from nothing.

    The construction-time rule that matters: ``status=LIVE`` without
    :class:`ExchangeEvidence` raises, and evidence attached to a SIMULATED or
    UNCONFIGURED payload raises too. Both directions are lies, in opposite
    directions.
    """

    connector_id: str
    provider: str
    status: ConnectorStatus
    source_reference: str = ""
    source_timestamp: str = ""
    received_timestamp: str = field(default_factory=_utc_now)
    confidence: float = 0.0
    evidence: ExchangeEvidence | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_reference", redact(self.source_reference))
        if self.status in EVIDENCED_STATUSES and self.evidence is None:
            raise ValueError(
                f"{self.status.value} claims a real exchange with an external system and must "
                "carry ExchangeEvidence proving one happened. A connector that has not talked "
                "to anything reports CONFIGURED, SIMULATED, UNCONFIGURED or UNAVAILABLE."
            )
        if self.evidence is not None and self.status not in EVIDENCED_STATUSES:
            raise ValueError(
                f"Exchange evidence was supplied with status {self.status.value}. Evidence of a "
                "real exchange means the status is LIVE; anything else misdescribes it."
            )
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence is a 0..1 declaration, not a percentage or a score.")

    @property
    def freshness_seconds(self) -> float | None:
        """Age of the observation at the moment it was received, or None.

        None when either timestamp is missing or unparseable -- which is a real
        answer, and better than the zero a default would produce.
        """
        source = _parse_iso(self.source_timestamp)
        received = _parse_iso(self.received_timestamp)
        if source is None or received is None:
            return None
        return (received - source).total_seconds()

    @property
    def freshness_label(self) -> str:
        seconds = self.freshness_seconds
        if seconds is None:
            return "freshness unknown"
        if seconds < 0:
            return "source timestamp is in the future"
        if seconds < 90:
            return f"{int(seconds)}s old at receipt"
        if seconds < 5400:
            return f"{int(seconds // 60)}m old at receipt"
        return f"{seconds / 3600:.1f}h old at receipt"

    def to_dict(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "provider": self.provider,
            "status": self.status.value,
            "source_reference": self.source_reference,
            "source_timestamp": self.source_timestamp,
            "received_timestamp": self.received_timestamp,
            "freshness_seconds": self.freshness_seconds,
            "freshness_label": self.freshness_label,
            "confidence": self.confidence,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


class UnlabeledDisplayError(RuntimeError):
    """Raised when connector data is about to be shown without its status.

    Section 6.3: "Any consumer displaying connector data must display the
    status. A SIMULATED or UNAVAILABLE payload must never render as operational
    intelligence without that label."
    """


@dataclass(frozen=True)
class NormalizedPayload:
    """Normalized data from one connector, inseparable from its label.

    ``data`` is deliberately not the thing a consumer is handed. Every rendering
    path goes through :meth:`to_display_dict`, which puts ``connector_status``
    and ``connector_label`` in the same mapping as the values, so a template
    that iterates the dict cannot show the numbers and miss the label. A
    consumer that insists on reaching for ``.data`` still can -- Python has no
    private -- but it has to write the reach out, and
    :func:`assert_labeled_display` exists so the surface that does can prove it
    kept the label.
    """

    provenance: Provenance
    kind: str
    data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> ConnectorStatus:
        return self.provenance.status

    @property
    def label(self) -> str:
        """The one-line label that must appear wherever this data appears."""
        return f"{self.status.value} — {self.provenance.provider or self.provenance.connector_id}"

    @property
    def is_operational_intelligence(self) -> bool:
        """True only for evidenced live data. Everything else is labelled context."""
        return self.status is ConnectorStatus.LIVE

    def to_display_dict(self) -> dict:
        return {
            "connector_status": self.status.value,
            "connector_label": self.label,
            "connector_id": self.provenance.connector_id,
            "provider": self.provenance.provider,
            "kind": self.kind,
            "is_operational_intelligence": self.is_operational_intelligence,
            # A surface can use this to decide how loudly to label, but not
            # whether to: connector_status is present either way.
            "label_required": self.status in LABEL_REQUIRED_STATUSES,
            "provenance": self.provenance.to_dict(),
            "data": dict(self.data),
        }


def assert_labeled_display(rendered: Mapping[str, Any]) -> Mapping[str, Any]:
    """Refuse a rendering of connector data that dropped the status label.

    A consuming surface calls this on whatever it is about to hand a template.
    It is cheap, it runs in production, and it turns "we remembered to show the
    label" from a review comment into a failure.
    """
    status = rendered.get("connector_status") if isinstance(rendered, Mapping) else None
    if not status:
        raise UnlabeledDisplayError(
            "Connector data is being displayed without its status. Render it through "
            "NormalizedPayload.to_display_dict() so the SIMULATED/UNCONFIGURED/LIVE label "
            "travels with the values."
        )
    parse_status(str(status))
    return rendered


# --------------------------------------------------------------------------- failures


#: The failure kinds a connector may report. A closed list so that "what went
#: wrong" is answerable across eight connectors written at different times.
ERROR_KINDS: tuple[str, ...] = (
    "unconfigured",
    "auth_failure",
    "timeout",
    "malformed_payload",
    "transport_failure",
    "provider_error",
    "refused_by_boundary",
    "not_authorized",
)


@dataclass(frozen=True)
class ConnectorError:
    """Why an attempt did not produce a payload."""

    kind: str
    reason: str
    retryable: bool = False
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", redact(self.reason))
        object.__setattr__(self, "detail", redact(self.detail))
        if self.kind not in ERROR_KINDS:
            raise ValueError(
                f"{self.kind!r} is not one of the connector error kinds: {', '.join(ERROR_KINDS)}"
            )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "retryable": self.retryable,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RetryStatus:
    """How many attempts were spent, and whether more are worth making.

    Retry policy lives with the result rather than inside a connector's private
    loop so that a caller -- and an auditor reading ``connector_audit`` -- can
    see that three attempts were made and all three timed out, rather than one
    opaque failure.
    """

    attempts: int = 0
    max_attempts: int = 1
    exhausted: bool = False
    next_delay_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "exhausted": self.exhausted,
            "next_delay_seconds": self.next_delay_seconds,
        }


#: Audit outcomes. ``refused`` and ``failed`` are kept apart because they answer
#: different questions: a refusal is Dispatch declining to try (unconfigured,
#: unauthorized, boundary), a failure is an attempt that did not come back.
AUDIT_OUTCOMES: tuple[str, ...] = ("ok", "refused", "failed")


@dataclass(frozen=True)
class AuditRecord:
    """One connector attempt, as it is written to ``connector_audit``.

    Every attempt gets one of these, including the attempts that never left the
    building. "The accounting connector was asked for a settlement export at
    14:02 and refused because it is UNCONFIGURED" is the sentence this table
    exists to be able to produce.
    """

    connector_id: str
    operation: str
    status: ConnectorStatus
    outcome: str
    audit_id: str = field(default_factory=lambda: _new_id("CAUD"))
    provider: str = ""
    reason: str = ""
    attempts: int = 0
    source_reference: str = ""
    evidence_fingerprint: str = ""
    at: str = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", redact(self.reason))
        object.__setattr__(self, "source_reference", redact(self.source_reference))
        if self.outcome not in AUDIT_OUTCOMES:
            raise ValueError(
                f"{self.outcome!r} is not an audit outcome: {', '.join(AUDIT_OUTCOMES)}"
            )

    def to_dict(self) -> dict:
        return {
            "audit_id": self.audit_id,
            "connector_id": self.connector_id,
            "provider": self.provider,
            "operation": self.operation,
            "status": self.status.value,
            "outcome": self.outcome,
            "reason": self.reason,
            "attempts": self.attempts,
            "source_reference": self.source_reference,
            "evidence_fingerprint": self.evidence_fingerprint,
            "at": self.at,
        }


class ConnectorRefusal(RuntimeError):
    """A function needed connector data and did not get it.

    Carries the labeled refusal sentence, so the caller that lets this escape to
    a user shows *why* -- Section 6.7's "clear, labeled refusal, not a silent
    degradation".
    """

    def __init__(self, result: "ConnectorResult") -> None:
        super().__init__(result.refusal_message())
        self.result = result
        self.status = result.status


@dataclass(frozen=True)
class ConnectorRequest:
    """What is being asked of a connector.

    ``operation`` is the connector's own verb ("fetch_conditions", "send",
    "export_settlement"). ``params`` is data, never credentials: a connector
    resolves its own configuration, so nothing here needs to carry a key.
    """

    operation: str
    params: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 15.0
    max_attempts: int = 1
    requested_by: str = ""

    def __post_init__(self) -> None:
        if not self.operation:
            raise ValueError("A connector request needs an operation.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts is at least 1 -- zero attempts is not a request.")


@dataclass(frozen=True)
class ConnectorResult:
    """The single return shape of every connector call.

    Exactly one of ``payload`` and ``error`` is set. A result cannot be both a
    success and a failure, and it cannot be neither -- an empty result would be
    the silent degradation Section 6.7 forbids, so it is refused at
    construction.
    """

    status: ConnectorStatus
    connector_id: str
    operation: str
    payload: NormalizedPayload | None = None
    error: ConnectorError | None = None
    retry: RetryStatus = field(default_factory=RetryStatus)
    audit: AuditRecord | None = None
    connector_name: str = ""

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.error is None):
            raise ValueError(
                "A connector result carries a payload or an error, never both and never "
                "neither. A result with neither is a silent degradation."
            )
        if self.payload is not None and self.payload.status is not self.status:
            raise ValueError(
                f"Result status {self.status.value} disagrees with its payload's "
                f"{self.payload.status.value}. The payload's provenance is the truth."
            )

    @property
    def ok(self) -> bool:
        return self.payload is not None

    def __bool__(self) -> bool:
        return self.ok

    def refusal_message(self) -> str:
        """One sentence naming the connector, its status and the reason."""
        if self.ok:
            return ""
        name = self.connector_name or self.connector_id
        reason = self.error.reason if self.error else "no reason recorded"
        return (
            f"{name} is {self.status.value}: {reason} "
            f"(operation {self.operation!r}, attempts {self.retry.attempts})."
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "ok": self.ok,
            "connector_id": self.connector_id,
            "connector_name": self.connector_name,
            "operation": self.operation,
            "payload": self.payload.to_display_dict() if self.payload else None,
            "error": self.error.to_dict() if self.error else None,
            "retry": self.retry.to_dict(),
            "audit": self.audit.to_dict() if self.audit else None,
            "refusal": self.refusal_message(),
        }

    def with_audit(self, audit: AuditRecord) -> "ConnectorResult":
        return replace(self, audit=audit)


def require_payload(result: ConnectorResult) -> NormalizedPayload:
    """Return the payload, or raise the labeled refusal.

    The one sanctioned way for a function that genuinely cannot proceed without
    connector data to stop. It stops loudly, with the connector named and the
    status word in the message.
    """
    if not result.ok or result.payload is None:
        raise ConnectorRefusal(result)
    return result.payload


T = TypeVar("T")


def attempt(
    operation: Callable[[], T],
    *,
    max_attempts: int = 1,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError,),
    backoff_seconds: float = 0.0,
) -> tuple[T | None, RetryStatus, BaseException | None]:
    """Run a provider call up to ``max_attempts`` times, reporting the retries.

    No sleeping. A connector call happens inside a request or a scheduled run,
    and a retry loop that sleeps turns a slow provider into a slow Dispatch;
    ``next_delay_seconds`` is reported so a scheduler can decide, which is the
    layer that should be deciding.

    Only ``retry_on`` exceptions are retried. An authentication failure is not
    retried at all -- retrying a rejected credential is how an account gets
    locked out, and the second attempt has no more chance than the first.
    """
    last_error: BaseException | None = None
    for number in range(1, max_attempts + 1):
        try:
            value = operation()
        except retry_on as exc:
            last_error = exc
            continue
        except Exception as exc:  # noqa: BLE001 - classified by the caller, never swallowed
            return None, RetryStatus(number, max_attempts, False, 0.0), exc
        return value, RetryStatus(number, max_attempts, False, 0.0), None
    return (
        None,
        RetryStatus(max_attempts, max_attempts, True, backoff_seconds),
        last_error,
    )


# --------------------------------------------------------------------------- the protocol


@runtime_checkable
class Connector(Protocol):
    """What every Dispatch connector implements.

    Six questions and one verb. The questions are the ones an operator asks of
    an integration he did not write and cannot see -- who are you, what can you
    do, are you configured, can you authenticate, are you healthy -- and each is
    answered with a truth word. The verb is :meth:`fetch`, which never raises
    for an operational failure: it returns a result carrying either a labeled
    payload or a labeled error.
    """

    def identity(self) -> ConnectorIdentity: ...

    def capabilities(self) -> CapabilityDeclaration: ...

    def configuration(self) -> ConfigurationStatus: ...

    def authentication(self) -> AuthenticationStatus: ...

    def health(self) -> HealthStatus: ...

    def fetch(self, request: ConnectorRequest) -> ConnectorResult: ...


class BaseConnector:
    """Shared, truthful defaults for the eight registered connectors.

    Subclasses that have no provider yet override almost nothing: the default
    :meth:`fetch` refuses with ``UNCONFIGURED`` and the reason names the exact
    environment keys that are missing. That default is what makes "skeletal but
    truthful" (Section 6.4) achievable without eight copies of the same honest
    refusal.

    A subclass that gains a real provider overrides :meth:`fetch` and builds its
    payloads through :meth:`payload`, which is where status and provenance are
    attached -- there is no path to a payload that skips them.
    """

    connector_id: str = ""
    connector_name: str = ""
    provider_id: str = ""
    provider_name: str = ""
    required_config_keys: tuple[str, ...] = ()
    credential_keys: tuple[str, ...] = ()
    auth_method: str = "none"
    capability_declaration: CapabilityDeclaration = CapabilityDeclaration()

    # ---------------------------------------------------------------- identity

    def identity(self) -> ConnectorIdentity:
        return ConnectorIdentity(
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            provider_id=self.provider_id,
            provider_name=self.provider_name,
        )

    def capabilities(self) -> CapabilityDeclaration:
        return self.capability_declaration

    # ---------------------------------------------------------------- config

    def _config_value(self, key: str) -> str:
        """Configuration comes from the environment, and only from there.

        Not from a database, not from a JSON file this process could write. A
        connector that could configure itself could also silently reconfigure
        itself, and the operator would have no single place to look.
        """
        return os.environ.get(key, "").strip()

    def configuration(self) -> ConfigurationStatus:
        present = tuple(k for k in self.required_config_keys if self._config_value(k))
        missing = tuple(k for k in self.required_config_keys if not self._config_value(k))
        if not self.required_config_keys:
            return ConfigurationStatus(
                ConnectorStatus.UNCONFIGURED,
                detail=(
                    f"{self.connector_name} has no provider chosen yet, so it has no "
                    "configuration keys to check. Provider selection is Mike's decision "
                    "(docs/connectors/PROVIDER_INSERTION.md)."
                ),
            )
        if missing:
            return ConfigurationStatus(
                ConnectorStatus.UNCONFIGURED,
                required_keys=self.required_config_keys,
                present_keys=present,
                missing_keys=missing,
                detail=f"Missing configuration: {', '.join(missing)}.",
            )
        return ConfigurationStatus(
            ConnectorStatus.CONFIGURED,
            required_keys=self.required_config_keys,
            present_keys=present,
            detail="All required configuration keys are present.",
        )

    def authentication(self) -> AuthenticationStatus:
        """Present credentials are ``UNVERIFIED`` until an exchange proves them.

        This is the distinction the mission's vocabulary was written for.
        Credentials in the environment prove that somebody typed something. They
        do not prove the provider accepts them, so the strongest honest answer
        before a real call is UNVERIFIED.
        """
        if not self.credential_keys:
            return AuthenticationStatus(
                ConnectorStatus.UNCONFIGURED,
                method=self.auth_method,
                detail="No authentication configured; no provider selected.",
            )
        missing = [k for k in self.credential_keys if not self._config_value(k)]
        if missing:
            return AuthenticationStatus(
                ConnectorStatus.UNCONFIGURED,
                method=self.auth_method,
                credential_names=self.credential_keys,
                detail=f"Missing credentials: {', '.join(missing)}.",
            )
        return AuthenticationStatus(
            ConnectorStatus.UNVERIFIED,
            method=self.auth_method,
            credential_names=self.credential_keys,
            detail=(
                "Credentials are present but no authenticated exchange has been performed, "
                "so they are unproven."
            ),
        )

    def health(self) -> HealthStatus:
        """Health of a connector that has never been attempted is ``ABSENT``.

        Once :meth:`fetch` runs, subclasses record the attempt and this reports
        what happened. Nothing here invents a green light for a connector that
        has never done anything.
        """
        config = self.configuration()
        if not config.configured:
            return HealthStatus(
                ConnectorStatus.UNCONFIGURED,
                last_error="",
            )
        return HealthStatus(ConnectorStatus.ABSENT)

    # ---------------------------------------------------------------- results

    def provenance(
        self,
        *,
        status: ConnectorStatus,
        source_reference: str = "",
        source_timestamp: str = "",
        confidence: float = 0.0,
        evidence: ExchangeEvidence | None = None,
    ) -> Provenance:
        return Provenance(
            connector_id=self.connector_id,
            provider=self.identity().provider_label,
            status=status,
            source_reference=source_reference,
            source_timestamp=source_timestamp,
            confidence=confidence,
            evidence=evidence,
        )

    def payload(
        self,
        kind: str,
        data: Mapping[str, Any],
        *,
        status: ConnectorStatus,
        source_reference: str = "",
        source_timestamp: str = "",
        confidence: float = 0.0,
        evidence: ExchangeEvidence | None = None,
    ) -> NormalizedPayload:
        return NormalizedPayload(
            provenance=self.provenance(
                status=status,
                source_reference=source_reference,
                source_timestamp=source_timestamp,
                confidence=confidence,
                evidence=evidence,
            ),
            kind=kind,
            data=dict(data),
        )

    def success(
        self,
        request: ConnectorRequest,
        payload: NormalizedPayload,
        *,
        retry: RetryStatus | None = None,
    ) -> ConnectorResult:
        return ConnectorResult(
            status=payload.status,
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            operation=request.operation,
            payload=payload,
            retry=retry or RetryStatus(1, request.max_attempts, False, 0.0),
        )

    def failure(
        self,
        request: ConnectorRequest,
        error: ConnectorError,
        *,
        status: ConnectorStatus,
        retry: RetryStatus | None = None,
    ) -> ConnectorResult:
        return ConnectorResult(
            status=status,
            connector_id=self.connector_id,
            connector_name=self.connector_name,
            operation=request.operation,
            error=error,
            retry=retry or RetryStatus(0, request.max_attempts, False, 0.0),
        )

    def unconfigured(self, request: ConnectorRequest, *, extra: str = "") -> ConnectorResult:
        config = self.configuration()
        missing = ", ".join(config.missing_keys) if config.missing_keys else "provider selection"
        reason = (
            f"{self.connector_name} has no configured provider. Missing: {missing}. "
            "Dispatch will not substitute a guess for an external answer."
        )
        if extra:
            reason = f"{reason} {extra}"
        return self.failure(
            request,
            ConnectorError("unconfigured", reason, retryable=False),
            status=ConnectorStatus.UNCONFIGURED,
        )

    # ---------------------------------------------------------------- the verb

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        """Truthful default: refuse, because nothing is configured.

        Overridden by the connectors that wrap code Dispatch already has (email
        transport, accounting, load board) and by the mock.
        """
        return self.unconfigured(request)

    # ---------------------------------------------------------------- display

    def status_summary(self) -> dict:
        """Everything a consuming surface needs, with the status word in it.

        A surface rendering the connector board calls this, so there is no path
        by which a connector appears on a screen without its truth word beside
        it.
        """
        config = self.configuration()
        auth = self.authentication()
        health = self.health()
        return {
            "connector_status": config.status.value,
            "identity": self.identity().to_dict(),
            "capabilities": self.capabilities().to_dict(),
            "configuration": config.to_dict(),
            "authentication": auth.to_dict(),
            "health": health.to_dict(),
        }
