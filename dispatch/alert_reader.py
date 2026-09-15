"""Load-board alert emails, read into loads. Deterministic, and never a guess.

Owner direction, 2026-09-15: alerts from specific board senders are sorted into
a "Load Alerts" folder of the operations mailbox, *"then the reader can do it's
thing."* This is the reader. It takes one message that has already been read out
of the mailbox (`dispatch/connectors/alert_mailbox.py`) and answers three
questions, in order:

  1. **Is the sender on the list?** Anyone else is ignored and counted, never
     carded.
  2. **How many loads does it hold?** An alert often lists several. It is split
     into one block per load when the shape of the text says where one ends and
     the next begins -- and when it cannot tell, it says so rather than cutting.
  3. **What does each block say?** Read by the paste reader that already exists
     (`dispatch/listing.py`), with a board's own labels translated first when a
     sender profile names them.

**Pure.** No mailbox, no network, no database, no clock. Links in an alert are
removed, never opened (D1). A block nothing could be read from comes back as
*needs a look*, and nothing downstream turns it into a card. A load with no
rate, or missing a city, is a card with the gap shown (Owner rulings,
2026-09-15).

SENDER PROFILES -- HOW A BOARD IS TUNED
=======================================

No board's alert has been seen yet (Mike will forward real ones). So nothing
here is written for a board: every alert goes through the generic reader, and a
profile is only a set of *hints* keyed by the sender's domain --

    {"name": "shown on the card as the board",
     "split": "a regular expression matching the line that starts each load",
     "kind": "listing" or "email",
     "labels": {"Orig": "origin", "Dest": "destination", "Pay": "rate", ...},
     "ignore_after": ["a line that starts the footer", ...]}

-- held in the load-alert settings file, editable on the settings screen. Every
key is optional. `labels` maps a board's own words to the facts the paste
reader already knows (`listing.LABELS`).
"""

from __future__ import annotations

import re

from dispatch import listing

#: The facts a profile's labels may point at. The paste reader's own list.
FACTS = tuple(listing.LABELS)

#: Where the useful part of an alert usually ends. Case-insensitive, line start.
FOOTER_STARTS = (
    "unsubscribe", "manage your alerts", "manage alerts", "manage your notifications",
    "you are receiving this", "you received this", "to stop receiving",
    "this email was sent", "this message was sent", "privacy policy",
    "view in browser", "view this email in your browser", "copyright", "©",
)

_SEPARATOR = re.compile(r"^\s*(?:[-=_*~#]\s*){3,}$")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_FORWARD_MARK = re.compile(
    r"^\s*(?:-{2,}\s*(?:original message|forwarded message)\s*-{2,}|begin forwarded message:?)\s*$",
    re.I)
_FORWARD_SUBJECT = re.compile(r"^\s*(?:fw|fwd)\s*:", re.I)
_HEADER_FROM = re.compile(r"^\s*from:\s*(.+)$", re.I)
_ADDRESS = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_DOLLAR_RATE = re.compile(r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d{3,})(?:\.\d{2})?(?!\s*(?:/\s*mi|per\s*mi))",
                          re.I)
_ORIGIN_LABELS = set(listing.LABELS["origin"]) | set(listing.LABELS["pickup"])


# ------------------------------------------------------------------ senders

def normalise_senders(entries) -> list:
    """The sender list as stored: lower case, trimmed, de-duplicated, in order.

    An entry is a whole address (`alerts@board.example`) or a domain
    (`board.example` or `@board.example`), which allows every address there.
    """
    seen, out = set(), []
    for raw in entries or []:
        for part in re.split(r"[,;\s]+", str(raw or "")):
            value = part.strip().lower().strip("<>")
            if not value or value in seen:
                continue
            if "@" in value.lstrip("@"):
                if not _ADDRESS.fullmatch(value):
                    continue
            elif not re.fullmatch(r"@?[\w\-]+(?:\.[\w\-]+)+", value):
                continue
            seen.add(value)
            out.append(value)
    return out


def address_of(sender: str) -> str:
    """The bare address out of `Name <address>` or an address."""
    match = _ADDRESS.search(str(sender or ""))
    return match.group(0).lower() if match else ""


def domain_of(sender: str) -> str:
    address = address_of(sender)
    return address.split("@", 1)[1] if "@" in address else ""


def sender_allowed(sender: str, allowed) -> bool:
    """Whether a sender is on the list. Exact address, or a listed domain or its subdomain."""
    address = address_of(sender)
    if not address:
        return False
    domain = address.split("@", 1)[1]
    for entry in normalise_senders(allowed):
        if "@" in entry.lstrip("@"):
            if address == entry:
                return True
            continue
        listed = entry.lstrip("@")
        if domain == listed or domain.endswith("." + listed):
            return True
    return False


# ---------------------------------------------------------------- profiles

def profile_for(sender: str, profiles: dict | None) -> tuple:
    """`(domain_key, profile)` for a sender: the most specific listed domain, or `("", {})`."""
    domain = domain_of(sender)
    best = ("", {})
    for key, profile in (profiles or {}).items():
        listed = str(key or "").strip().lower().lstrip("@")
        if not listed or not isinstance(profile, dict):
            continue
        if (domain == listed or domain.endswith("." + listed)) and len(listed) > len(best[0]):
            best = (listed, profile)
    return best


def check_profiles(profiles) -> list:
    """Problems with a profiles block, in words. Empty when it is usable."""
    problems = []
    if not isinstance(profiles, dict):
        return ["Board hints must be a set of domains, each with its hints."]
    for key, profile in profiles.items():
        if not isinstance(profile, dict):
            problems.append("%s: its hints must be a set of named values." % key)
            continue
        unknown = set(profile) - {"name", "split", "kind", "labels", "ignore_after"}
        if unknown:
            problems.append("%s: unknown hint %s." % (key, ", ".join(sorted(unknown))))
        if profile.get("split"):
            try:
                re.compile(str(profile["split"]), re.M)
            except re.error as exc:
                problems.append("%s: the split pattern does not read (%s)." % (key, exc))
        if profile.get("kind") not in (None, "", "listing", "email"):
            problems.append("%s: kind must be listing or email." % key)
        labels = profile.get("labels") or {}
        if not isinstance(labels, dict):
            problems.append("%s: labels must pair a board's word with a fact." % key)
        else:
            for word, fact in labels.items():
                if fact not in FACTS:
                    problems.append("%s: %r is not a fact the reader knows (%s)."
                                    % (key, fact, ", ".join(FACTS)))
        ignore = profile.get("ignore_after") or []
        if not isinstance(ignore, list):
            problems.append("%s: ignore_after must be a list of lines." % key)
    return problems


# ------------------------------------------------------------------ cleaning

def unwrap_forward(subject: str, body: str) -> tuple:
    """`(original_sender, body)` for a forwarded alert, or `("", body)`.

    How Mike tests with a real alert: he forwards it. The board is then named in
    the forwarded header, not in the envelope, and the header block is not part
    of any load.
    """
    lines = str(body or "").splitlines()
    marked = None
    for index, line in enumerate(lines):
        if _FORWARD_MARK.match(line):
            marked = index
            break
    if marked is None and not _FORWARD_SUBJECT.match(str(subject or "")):
        return "", str(body or "")
    start = marked + 1 if marked is not None else 0
    original = ""
    header_end = start
    for index in range(start, min(len(lines), start + 12)):
        line = lines[index].strip()
        found = _HEADER_FROM.match(line)
        if found and not original:
            original = address_of(found.group(1))
        if re.match(r"^\s*(?:from|sent|date|to|cc|subject):", line, re.I):
            header_end = index + 1
        elif line and header_end > start:
            break
    if not original:
        return "", str(body or "")
    return original, "\n".join(lines[header_end:])


def clean(body: str, profile: dict | None = None) -> str:
    """The part of an alert worth reading: links out, footer off, board labels translated."""
    profile = profile or {}
    stops = [s.lower() for s in FOOTER_STARTS] + [
        str(s).strip().lower() for s in (profile.get("ignore_after") or []) if str(s).strip()]
    labels = {str(k).strip().lower(): v for k, v in (profile.get("labels") or {}).items()
              if v in FACTS}
    kept = []
    for raw in str(body or "").splitlines():
        line = raw.rstrip()
        low = line.strip().lstrip(">").strip().lower()
        if low and any(low.startswith(stop) for stop in stops):
            break
        line = _URL.sub("", line).rstrip()
        if raw.strip() and not line.strip():
            continue
        if labels:
            match = re.match(r"^(\s*)([A-Za-z][A-Za-z #./\-]{0,30}?)\s*(:|\t)\s*(.*)$", line)
            if match and match.group(2).strip().lower() in labels:
                fact = labels[match.group(2).strip().lower()]
                line = "%s%s: %s" % (match.group(1), listing.LABELS[fact][0].title(),
                                     match.group(4))
        kept.append(line)
    return "\n".join(kept).strip()


# ----------------------------------------------------------------- splitting

def _lane_evidence(text: str) -> int:
    """How many places a piece of text names."""
    return len(listing._places(text))


def _is_lane_line(line: str) -> bool:
    """A line that starts a load: two places on it, or an origin label."""
    stripped = line.strip().lstrip(">").strip()
    if _lane_evidence(stripped) >= 2:
        return True
    match = re.match(r"^([A-Za-z][A-Za-z #./\-]{0,30}?)\s*(?::|\t)", stripped)
    return bool(match and match.group(1).strip().lower() in _ORIGIN_LABELS
                and _lane_evidence(stripped) >= 1)


def _looks_like_a_load(block: str) -> bool:
    return _lane_evidence(block) >= 1 or bool(_DOLLAR_RATE.search(block))


def split(text: str, profile: dict | None = None) -> dict:
    """One block per load. `{"blocks": [...], "how": "...", "unsure": "..."}`.

    In order: the profile's own split pattern; separator lines; a new load at
    every line that starts a lane. Text before the first load (a greeting, the
    search's name) is not a load and is left out. When the text holds more rates
    than the blocks found, it is not cut by guesswork -- `unsure` says why, and
    the caller treats the message as needing a look.
    """
    profile = profile or {}
    text = str(text or "")
    lines = text.splitlines()
    blocks: list = []
    how = "one load"

    pattern = str(profile.get("split") or "").strip()
    if pattern:
        starts = [i for i, line in enumerate(lines) if re.search(pattern, line)]
        if starts:
            blocks = ["\n".join(lines[a:b]) for a, b in zip(starts, starts[1:] + [len(lines)])]
            how = "board split pattern"

    if not blocks:
        parts, current = [], []
        for line in lines:
            if _SEPARATOR.match(line):
                parts.append("\n".join(current))
                current = []
            else:
                current.append(line)
        parts.append("\n".join(current))
        loads = [p for p in parts if _lane_evidence(p) >= 1]
        if len(loads) >= 2:
            blocks = loads
            how = "separator lines"

    if not blocks:
        starts = [i for i, line in enumerate(lines) if _is_lane_line(line)]
        if len(starts) >= 2:
            blocks = ["\n".join(lines[a:b]) for a, b in zip(starts, starts[1:] + [len(lines)])]
            how = "one load per lane line"

    if not blocks:
        blocks = [text]

    blocks = [b.strip() for b in blocks if b.strip() and _looks_like_a_load(b)]
    rates = len(_DOLLAR_RATE.findall(text))
    unsure = ""
    if len(blocks) <= 1 and rates >= 2:
        unsure = ("It seems to hold %d loads (%d rates) but they could not be told apart."
                  % (rates, rates))
    return {"blocks": blocks, "how": how, "unsure": unsure}


# ------------------------------------------------------------------- reading

def read_alert(message: dict, *, allowed, profiles: dict | None = None) -> dict:
    """Read one alert message. Pure.

    Returns::

        {"allowed": bool, "sender": str, "board": str, "how": str,
         "loads": [{"text", "kind", "fields", "card_extras", "missing"}],
         "needs_look": [{"reason", "fields", "missing", "text"}]}

    `loads` carry at least one freight fact -- a load with no rate or no city is
    still a load (Owner rulings 2026-09-15). Nothing is carded from
    `needs_look`, which holds only what nothing could be read from.
    """
    sender = address_of(message.get("sender", ""))
    subject = str(message.get("subject") or "")
    body = str(message.get("body") or "")
    outcome = {"allowed": False, "sender": sender, "original_sender": "", "board": "",
               "how": "", "loads": [], "needs_look": []}
    if not sender_allowed(sender, allowed):
        return outcome
    original, body = unwrap_forward(subject, body)
    # A forward is read only when the board that wrote it is on the list too, so
    # adding his own address to test with does not make every forward a load.
    if original and not sender_allowed(original, allowed):
        return outcome
    outcome["allowed"] = True
    outcome["original_sender"] = original
    board_sender = original or sender
    key, profile = profile_for(board_sender, profiles)
    outcome["board"] = str(profile.get("name") or key or domain_of(board_sender))
    kind = "email" if profile.get("kind") == "email" else "listing"

    cleaned = clean(body, profile)
    pieces = split(cleaned, profile)
    outcome["how"] = pieces["how"]

    if pieces["unsure"]:
        outcome["needs_look"].append({"reason": pieces["unsure"], "fields": {},
                                      "missing": [], "text": cleaned[:2000]})
        return outcome
    if not pieces["blocks"]:
        outcome["needs_look"].append({"reason": "No load could be read in it.",
                                      "fields": {}, "missing": [], "text": cleaned[:2000]})
        return outcome

    for block in pieces["blocks"]:
        read = (listing.parse_offer_email(block) if kind == "email"
                else listing.parse_listing(block))
        # Owner rulings, 2026-09-15: a load without a rate, or missing a city, is
        # still a card (rate pending). Only a block nothing could be read from
        # needs a look.
        if read["nothing_read"]:
            outcome["needs_look"].append({
                "reason": "No load could be read in it.",
                "fields": read["fields"], "missing": read["missing"], "text": block[:2000]})
            continue
        outcome["loads"].append({"text": block, "kind": kind, "fields": read["fields"],
                                 "card_extras": read["card_extras"],
                                 "missing": read["missing"]})
    return outcome
