"""The menu's icons, and the reason they are allowed to disappear.

Dispatch Control Center v1 specifies a glyph for each control:

    > Start   (globe) Open Dispatch   (arrows) Refresh Status   (gear) Settings
    (info) Version   (circle-arrow) Restart   (undo) Reset Session   (square) Stop

Every one of those is outside cp437 and cp1252, which are what a Windows console
still uses when it has not been switched to UTF-8. Printing them blind gives one
of two bad outcomes: mojibake, or a `UnicodeEncodeError` raised *while the
launcher is trying to tell the operator something*. The second is worse than
having no icons at all -- a control panel that crashes while reporting a problem
is a control panel that fails at the only moment it matters.

So the glyphs are used when the output stream can actually encode them and are
dropped when it cannot. Dropped, not transliterated: a row of invented ASCII
stand-ins (`>`, `@`, `~`, `*`) is noise that has to be decoded rather than read,
and the bracketed number beside each item is already the thing Mike types. A
menu with no icons is a clean menu. A menu with `~` meaning "refresh" is a
puzzle.

`dispatch.bat` asks Windows for the UTF-8 code page before starting Python, so
on a normal modern Windows install the glyphs do appear. This module is what
makes the launcher correct on the installs where that does not work, without
anybody having to find out the hard way.
"""

from __future__ import annotations

import os
import sys

#: Set to "0" to force the plain menu, or "1" to force glyphs. Anything else,
#: including unset, means "decide by asking the stream". Exists for the test
#: suite and for an operator whose console lies about its encoding.
GLYPH_ENV = "DISPATCH_LAUNCHER_GLYPHS"

START = "▶"          # ▶
OPEN = "\U0001f310"       # 🌐
REFRESH = "\U0001f504"    # 🔄
SETTINGS = "⚙"       # ⚙
VERSION = "ℹ"        # ℹ
RESTART = "↻"        # ↻
RESET = "⎌"          # ⎌
STOP = "■"           # ■
RESET_PIN = "\U0001f511"  # 🔑

#: Every glyph the menu uses. If the stream cannot encode all of them it gets
#: none of them -- a menu where three rows have icons and five do not looks
#: broken, and "looks broken" is indistinguishable from "is broken" to someone
#: deciding whether to trust the thing with their business.
ALL = (START, OPEN, REFRESH, SETTINGS, VERSION, RESTART, RESET, STOP, RESET_PIN)


def stream_supports(stream=None) -> bool:
    """Can this stream encode every menu glyph?

    Asks the stream's own encoder rather than pattern-matching the encoding
    name: `sys.stdout.encoding` can be "utf-8" on a stream that is really a
    pipe with something else behind it, and can be missing entirely when stdout
    has been replaced by a test double or a captured buffer.
    """
    stream = stream if stream is not None else sys.stdout
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        # No declared encoding: a StringIO, a captured buffer, or a redirect
        # whose target is unknown. Unknown is not a reason to gamble.
        return False
    try:
        for glyph in ALL:
            glyph.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def enabled(stream=None) -> bool:
    """Whether the menu should draw its icons. The environment wins."""
    forced = (os.environ.get(GLYPH_ENV) or "").strip()
    if forced == "0":
        return False
    if forced == "1":
        return True
    return stream_supports(stream)


def prefix(glyph: str, *, stream=None) -> str:
    """The glyph plus its trailing space, or an empty string.

    Callers concatenate this in front of a label, so a disabled glyph costs no
    leading whitespace and the menu closes up cleanly rather than showing a
    column of gaps.
    """
    return f"{glyph} " if enabled(stream) else ""
