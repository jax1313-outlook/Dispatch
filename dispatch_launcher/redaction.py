"""Secret redaction for everything the launcher writes down.

The launcher writes three kinds of file: a server log (the portal's own stdout
and stderr), a launcher action log, and a last-failure record. All three are
plain text on disk, all three get read out loud over the phone or pasted into a
support message, and all three can contain a value that must never travel --
`PORTAL_SECRET_KEY`, `DISPATCH_EMAIL_SECRET`, a signed `?token=` in a URL the
portal logged, or the DISPATCH_PIN.

This is not hypothetical for this repository: `.gitignore` already carries a
comment recording that a committed Werkzeug log leaked a debugger PIN in the
Jules repository and had to be removed by hand.

The rule is the one the mission brief states: redact the **value** of anything
whose **name** matches `*SECRET*`, `*KEY*`, `*PASSWORD*`, `*TOKEN*` or `*PIN*`,
and keep the name. A name is what an operator needs ("PORTAL_SECRET_KEY is not
set"); the value is what must never appear.

Over-redaction is the deliberate failure direction. `monkey=1` contains "key" and
will be redacted; `DISPATCH_SPINE_MODE` contains "PIN" and will be redacted. A
launcher log that hides one harmless value is a nuisance. A launcher log that
prints one real signing key is a breach.
"""

from __future__ import annotations

import re
from typing import Mapping

#: What a redacted value is replaced with. Distinctive on purpose -- an operator
#: reading a log can tell "this was removed" apart from "this was empty".
REDACTED = "[REDACTED]"

#: Substring markers, matched case-insensitively against the *name*. Mirrors the
#: markers `dispatch.backup._is_secret_name` uses for backup manifests, plus PIN,
#: which the portal's authority gate introduced after that list was written.
SECRET_NAME_MARKERS = ("SECRET", "KEY", "PASSWORD", "TOKEN", "PIN", "CREDENTIAL")

_MARKER_ALTERNATION = "|".join(SECRET_NAME_MARKERS)

# name = value / name: value / "name": "value" / ?name=value&...
#
# `name_quote` exists for the JSON case: a log line reads `"PORTAL_SECRET_KEY":
# "..."` and without it the closing quote after the name stops the match dead,
# leaving the value in the file. That is the shape a redaction bug takes -- it
# does not raise, it just quietly fails to redact.
#
# The value stops at whitespace, a quote, or any of the characters that end a
# value inside a URL, a JSON object or a shell line, so a redaction never eats
# the rest of the line.
_ASSIGNMENT = re.compile(
    rf"(?P<name>[A-Za-z0-9_.\-]*(?:{_MARKER_ALTERNATION})[A-Za-z0-9_.\-]*)"
    r"(?P<name_quote>[\"']?)"
    r"(?P<sep>\s*[:=]\s*)"
    r"(?P<quote>[\"']?)"
    r"(?P<value>[^\s\"',;&)\]}]+)"
    r"(?P=quote)",
    re.IGNORECASE,
)


def is_secret_name(name: str) -> bool:
    """True when *name* looks like it names a credential rather than a setting."""
    upper = name.upper()
    return any(marker in upper for marker in SECRET_NAME_MARKERS)


def redact_text(text: str) -> str:
    """Return *text* with the value of every secret-looking assignment removed.

    Applied to every byte the launcher itself writes. It is NOT applied to the
    portal's own log stream, which is written by the portal process straight to
    its file descriptor -- see `control.start()`, which documents that trade-off
    and why the launcher redacts on the way *out* of that file instead.
    """
    if not text:
        return text

    def _replace(match: re.Match[str]) -> str:
        quote = match.group("quote")
        name_quote = match.group("name_quote")
        return (
            f"{match.group('name')}{name_quote}{match.group('sep')}"
            f"{quote}{REDACTED}{quote}"
        )

    return _ASSIGNMENT.sub(_replace, text)


def redact_mapping(values: Mapping[str, str]) -> dict[str, str]:
    """Return a copy of *values* with every secret-named value replaced.

    Used for the environment snapshot written into the launcher log, so the log
    records *which* settings were in force at launch without recording any of
    their credentials.
    """
    return {
        name: (REDACTED if is_secret_name(name) else value)
        for name, value in values.items()
    }
