"""The alert mailbox port: what Dispatch may ask a mailbox that holds load-board alerts.

Owner direction, 2026-09-15, on load-board alert emails becoming cards: *"i like
this very much"* ... *"can we use Ops@l1truck .com? if we can create a small
email sort to push the incoming emails from specific senders to a box then the
reader can do it's thing."*

The board sends the alert to Level 1's own mailbox. Reading his own mailbox is
not scraping (D1): nothing here fetches a page, follows a link, or logs into a
board.

WHAT THE PORT ALLOWS
====================

**One question, read-only:** *which messages arrived in this folder since this
time?* The port has no method that sends, replies, moves, deletes, flags or
marks a message read, and an adapter behind it must not add one. Which messages
Dispatch has already handled is remembered in Dispatch's own store, never by
changing the mailbox.

This file names no product. The adapter that reads a real mailbox on this node
lives beside it and is handed out by `registry.alert_mailbox()`; an IMAP or web
mail adapter could replace it by answering `read_since` in the same shape.

**Not one of the eight registered connectors.** `registry.CONNECTOR_IDS` is a
fixed, asserted count and a ninth is Mike's decision
(`docs/connectors/PROVIDER_INSERTION.md`). Like the outbound mail adapter, this
sits in the registry's reachability helpers, outside the governed eight.

THE ANSWER'S SHAPE
==================

    {"status": LIVE | UNAVAILABLE | UNCONFIGURED | SIMULATED,
     "reason": "why it is not LIVE, in words",
     "mailbox": "...", "folder": "...", "checked_at": "ISO time",
     "messages": [{"message_id", "sender", "subject", "received_at", "body"}]}

`LIVE` only when a read actually succeeded. `message_id` is the mailbox's own
stable id for the message; `body` is plain text with any HTML stripped.
"""

from __future__ import annotations

import html
import re

STATUS_LIVE = "LIVE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_UNCONFIGURED = "UNCONFIGURED"
STATUS_SIMULATED = "SIMULATED"

#: The words an answer may carry. From the locked eight, and no others.
STATUSES = (STATUS_LIVE, STATUS_UNAVAILABLE, STATUS_UNCONFIGURED, STATUS_SIMULATED)

#: What a message carries when it reaches the reader.
MESSAGE_KEYS = ("message_id", "sender", "subject", "received_at", "body")


class AlertMailboxPort:
    """Read-only. One method. Anything that changes a mailbox does not belong here."""

    name = "alert_mailbox"

    def read_since(self, *, mailbox: str, folder: str, since=None, limit: int = 200,
                   known=()) -> dict:
        """Messages in `folder` of `mailbox` received at or after `since`.

        `known` holds message ids Dispatch has already handled; an adapter may
        leave their bodies unread (they are still skipped by the caller either way).
        """
        raise NotImplementedError


def answer(status: str, *, mailbox: str = "", folder: str = "", reason: str = "",
           messages=None, checked_at: str = "") -> dict:
    """An answer in the port's shape. Refuses a status outside the locked words."""
    if status not in STATUSES:
        raise ValueError("%r is not a status word this port may report" % status)
    return {"status": status, "reason": str(reason or ""), "mailbox": str(mailbox or ""),
            "folder": str(folder or ""), "checked_at": str(checked_at or ""),
            "messages": list(messages or [])}


_BLOCK_TAGS = re.compile(
    r"<\s*(?:br|/p|/div|/tr|/li|/h[1-6]|/table|p|div|tr|li|h[1-6]|table)\b[^>]*>", re.I)
_CELL_TAGS = re.compile(r"<\s*/?\s*(?:td|th)\b[^>]*>", re.I)
_DROP_BLOCKS = re.compile(r"<\s*(script|style|head)\b.*?<\s*/\s*\1\s*>", re.I | re.S)
_ANY_TAG = re.compile(r"<[^>]+>")


def strip_html(markup: str) -> str:
    """Plain text out of an HTML mail body. Deterministic; follows nothing.

    Rows and paragraphs become lines and table cells become tab-separated, so a
    board's alert table reads the way it looks. Links are dropped with the rest
    of the markup -- the reader never opens one.
    """
    text = _DROP_BLOCKS.sub(" ", str(markup or ""))
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = _BLOCK_TAGS.sub("\n", text)
    text = _CELL_TAGS.sub("\t", text)
    text = _ANY_TAG.sub("", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = []
    for raw in text.splitlines():
        cells = [re.sub(r"[ \f\v]+", " ", c).strip() for c in raw.split("\t")]
        line = "\t".join(c for c in cells if c)
        lines.append(line)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return out.strip()
