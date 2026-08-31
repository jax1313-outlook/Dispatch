"""Find other copies of Dispatch on this machine. BLOCK-04.

On 2026-08-25 three copies of Dispatch existed on the operator's laptop. The one
holding port 8080 all day had an incomplete extraction -- `dispatch/connectors`
was missing entirely -- and every page behind the sign-in returned HTTP 500 for
seven hours. Four separate theories were built and discarded before the cause
was found, and none of them was "you are running a different copy from the one
you are looking at."

Each copy carries its own database. Working in one and reading the other is a
silent, total loss of correspondence between what the operator does and what
they see.

This module answers one question at startup: **is there more than one?**

What it deliberately does not do
--------------------------------
It never blocks a start. A second copy is a thing worth knowing, not a reason to
refuse to run -- and a check that can stop Dispatch is a check that will one day
stop it wrongly.

It never scans the whole disk. A startup check that takes thirty seconds is a
check the operator learns to dread.

It never deletes, moves or renames anything. Which copy to keep is the
operator's decision, and copies hold data.
"""

from __future__ import annotations

import os
from pathlib import Path

from dispatch_launcher import locations

#: A directory looks like Dispatch if it holds the launch file, or both of the
#: two packages. The launch file alone is enough because it is what a person
#: double-clicks; the package pair catches an extraction that lost it.
#:
#: This test is deliberately loose. The copy that cost the operator seven hours
#: was an *incomplete extraction* missing `dispatch/connectors` entirely -- a
#: stricter test is one that could miss precisely the copy that matters. The
#: cost of being loose is naming a folder that merely resembles Dispatch, which
#: the operator can dismiss by reading its name; the cost of being strict is
#: silence about the broken one.
_LAUNCH_FILE = "DISPATCH_START_HERE.cmd"
_PACKAGE_DIRS = ("dispatch", "portal")

#: How far below each search root to look. Two levels finds `C:\\Dispatch\\Dispatch-main`
#: and `Downloads\\Dispatch-main\\Dispatch-main` without walking a user's whole profile.
_MAX_DEPTH = 2

#: Directory names never worth descending -- large, and never a Dispatch install.
_SKIP = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "AppData", "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information", ".idea", ".vscode",
}


def looks_like_dispatch(path: Path) -> bool:
    """True when this directory holds a Dispatch install."""
    try:
        if not path.is_dir():
            return False
        if (path / _LAUNCH_FILE).exists():
            return True
        return all((path / d).is_dir() for d in _PACKAGE_DIRS)
    except OSError:
        # An unreadable directory is not a finding. Windows raises here for
        # junctions, permission and long paths, and none of that is the
        # operator's problem at startup.
        return False


def _search_roots(running: Path) -> list[Path]:
    """Where a second copy plausibly is, without scanning the disk.

    The operator's three copies were nested siblings, so the running install's
    parents matter most. The rest are where a downloaded ZIP lands.
    """
    roots: list[Path] = []
    try:
        roots.extend(list(running.parents)[:3])
    except (OSError, IndexError):
        pass

    home = None
    try:
        home = Path.home()
    except (OSError, RuntimeError):
        pass
    if home is not None:
        for name in ("Desktop", "Downloads", "Documents", "OneDrive"):
            roots.append(home / name)
        roots.append(home)

    for drive in ("C:/", "D:/"):
        roots.append(Path(drive))

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        try:
            key = str(root.resolve()).lower()
        except OSError:
            continue
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _scan(root: Path, depth: int, found: dict[str, Path]) -> None:
    if depth > _MAX_DEPTH:
        return
    try:
        entries = list(os.scandir(root))
    except OSError:
        return
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        if entry.name in _SKIP or entry.name.startswith("."):
            continue
        path = Path(entry.path)
        if looks_like_dispatch(path):
            try:
                found.setdefault(str(path.resolve()).lower(), path)
            except OSError:
                found.setdefault(str(path).lower(), path)
            # A Dispatch install can still contain another -- Mike's did.
        _scan(path, depth + 1, found)


def find_copies(running: Path | None = None) -> list[Path]:
    """Every Dispatch install found, **excluding** the one running.

    Returns paths, sorted, never raising. An empty list means either that there
    is exactly one copy or that nothing else was reachable -- this function
    reports what it found and does not claim the absence is proof.
    """
    running = Path(running) if running else locations.repo_root()
    try:
        running_key = str(running.resolve()).lower()
    except OSError:
        running_key = str(running).lower()

    found: dict[str, Path] = {}
    for root in _search_roots(running):
        if looks_like_dispatch(root):
            try:
                found.setdefault(str(root.resolve()).lower(), root)
            except OSError:
                pass
        _scan(root, 1, found)

    found.pop(running_key, None)
    return sorted(found.values(), key=lambda p: str(p).lower())


def describe(running: Path | None = None, others: list[Path] | None = None) -> str:
    """The message the operator reads. Plain, and it names the running copy first.

    Naming the running copy is the whole point. On 2026-08-25 the question that
    went unanswered for seven hours was not "how many copies are there" but
    "which one am I actually using".
    """
    running = Path(running) if running else locations.repo_root()
    if others is None:
        others = find_copies(running)

    if not others:
        return f"One copy of Dispatch: {running}"

    count = len(others) + 1
    lines = [
        f"{count} folders on this machine look like Dispatch.",
        "",
        f"    RUNNING NOW:  {running}",
        "",
        "    Also present:",
    ]
    lines.extend(f"      - {p}" for p in others)
    lines.extend([
        "",
        "    Each copy keeps its own database. Work done in one does not appear",
        "    in another, and a copy that was extracted incompletely will start",
        "    and then fail on every page behind the sign-in.",
        "",
        "    Keep the one above that is RUNNING NOW. Move the others out of the",
        "    way -- rename them, or put them somewhere you will not double-click",
        "    them by accident. Do not delete anything until you are sure which",
        "    copy holds the loads you care about.",
        "",
        "    Some of these may be a different program that merely looks similar.",
        "    This check errs towards naming a folder rather than staying quiet",
        "    about one, because a copy missing files is still a copy that starts.",
    ])
    return "\n".join(lines)
