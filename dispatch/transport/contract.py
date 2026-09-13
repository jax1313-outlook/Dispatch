"""The port. One message shape, one result shape, one refusal shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

#: The truth vocabulary, used here exactly as CLAUDE.md section 6 fixes it.
LIVE = "LIVE"
CONFIGURED = "CONFIGURED"
UNCONFIGURED = "UNCONFIGURED"
SIMULATED = "SIMULATED"
UNAVAILABLE = "UNAVAILABLE"


class TransportError(RuntimeError):
    """The transport tried and failed. Retryable unless it says otherwise."""

    retryable = True


class TransportUnconfigured(TransportError):
    """The transport was asked to send without the settings it requires.

    Not retryable: retrying a missing client id every five minutes for four
    hours accomplishes nothing except filling the delivery log with the same
    line. `dispatch.delivery` reads this and abandons immediately.
    """

    retryable = False


@dataclass(frozen=True)
class OutboundMessage:
    """What Dispatch wants said, independent of who carries it.

    Deliberately not an `email.message.EmailMessage`: Graph's sendMail takes
    JSON, not MIME, and a port whose message type is one provider's wire format
    is not a port. Each adapter builds its own representation from this.
    """

    to: tuple[str, ...]
    subject: str
    body_text: str
    body_html: str = ""
    cc: tuple[str, ...] = ()
    reply_to: str = ""
    from_address: str = ""
    #: What this message is about, carried through to the delivery record so a
    #: failure can be traced back to the load without parsing the subject line.
    subject_ref: str = ""
    headers: dict = field(default_factory=dict)

    def recipients(self) -> tuple[str, ...]:
        return tuple(self.to) + tuple(self.cc)


@dataclass(frozen=True)
class TransportResult:
    """What happened, in the words the rest of the program already uses."""

    status: str
    receipt: str
    provider: str
    detail: str = ""

    @property
    def delivered(self) -> bool:
        """True only when a real relay accepted it.

        SIMULATED is not delivery. A .eml written to Archive/Outbox is a record
        that Dispatch would have sent something, and reporting it as sent is the
        one mistake this whole layer exists to make impossible.
        """
        return self.status == LIVE


class MessageTransport(Protocol):
    """Four members. An adapter that needs a fifth is doing something else."""

    transport_id: str
    provider_name: str

    def status(self) -> str:
        """One truth word, without sending anything."""

    def describe(self) -> str:
        """`LIVE -- SMTP relay smtp.office365.com`. Checkable by a person.

        Naming the provider matters: "LIVE -- Email Transport" is a claim about
        Dispatch, where "LIVE -- Microsoft Graph as dispatch@example.com" is a
        claim about the world, and only the second one can be checked.
        """

    def send(self, message: OutboundMessage) -> TransportResult:
        """Send it, or raise TransportError. Never return a false success."""
