"""The thing Mike actually uses: a text menu, and a one-shot command line.

Deliberately a numbered text menu rather than a window. A GUI would mean a
framework dependency the mission forbids, a second thing to keep working across
Python upgrades, and a control surface that cannot be driven from a scheduled
task or read over the phone. A numbered menu in a console window is boring,
inspectable, works over Remote Desktop, and is the same code path the test suite
drives.

Two ways in, one behaviour:

    dispatch.bat                       double-click: status, then the menu
    python -m dispatch_launcher        the same
    python -m dispatch_launcher status one reading, then exit (exit code 0/1)
    python -m dispatch_launcher start|stop|restart|open

Every non-ASCII character in the *status and result text* is kept out on
purpose: a Windows console redirected to a file uses the machine's ANSI code
page, and a launcher that raises UnicodeEncodeError while reporting a problem is
a launcher that fails at the only moment it matters.

The menu's icons are the one exception, and they are handled rather than
assumed -- see `dispatch_launcher.glyphs`. They are drawn when the output stream
can encode them and dropped when it cannot, so the same menu is correct on a
UTF-8 Windows Terminal and on a console still running cp437.
"""

from __future__ import annotations

import argparse
import sys

from dispatch_launcher import (
    control,
    glyphs,
    locations,
    probe,
    settings as settings_module,
    status as status_module,
)

#: The eight controls of Dispatch Control Center v1, in the specified order.
#: (key, glyph, label, action). The order is deliberate and is not alphabetical
#: or grouped by risk: it is the order of a working day -- start, look at it,
#: adjust it, and only then the two that interrupt what is running. Stop is last
#: because it is the one you must not hit by accident.
MENU_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("1", glyphs.START, "Start", "start"),
    ("2", glyphs.OPEN, "Open Dispatch", "open"),
    ("3", glyphs.REFRESH, "Refresh Status", "status"),
    ("4", glyphs.SETTINGS, "Settings", "settings"),
    ("5", glyphs.VERSION, "Version", "version"),
    ("6", glyphs.RESTART, "Restart", "restart"),
    ("7", glyphs.RESET, "Reset Session", "reset-session"),
    ("8", glyphs.STOP, "Stop Dispatch", "stop"),
)

#: Controls added after Control Center v1 was specified. They are **lettered, not
#: numbered**, and deliberately so: the eight above are a settled specification and
#: renumbering them to slot a ninth into the middle would break the one thing an
#: operator learns by muscle memory. `[Q] Quit` already established the convention,
#: so a lettered control is not a new idea here -- just an unused shelf.
#:
#: Reset PIN lives here because a forgotten PIN previously had no recovery path at
#: all: `bootstrap_authority()` refuses once an identity exists, so the only way back
#: in was deleting identity.json by hand. Ruling recorded in DECISION_LOG.md
#: 2026-08-25.
EXTRA_ITEMS: tuple[tuple[str, str, str, str], ...] = (
    ("P", glyphs.RESET_PIN, "Reset PIN", "reset-pin"),
)

#: Every spelling the menu accepts for each item, so an operator who types the
#: word instead of the number is not told they are wrong.
_ALIASES: dict[str, tuple[str, ...]] = {
    "start": ("start",),
    "open": ("open", "open dispatch", "browser", "portal"),
    "status": ("status", "refresh", "refresh status", ""),
    "settings": ("settings", "config", "configuration"),
    "version": ("version", "about"),
    "restart": ("restart",),
    "reset-session": ("reset", "reset session", "reset-session"),
    "reset-pin": ("reset pin", "reset-pin", "pin", "forgot pin", "forgotten pin"),
    "stop": ("stop", "stop dispatch"),
}

#: Actions that change something. `status`, `settings` and `version` observe and
#: are therefore not here -- the one-shot command line runs them without the
#: launcher ever writing a file.
_ACTIONS = ("start", "stop", "restart", "open", "reset-session", "reset-pin")

#: Everything the command line accepts, including the read-only views.
#: `start-here` is what DISPATCH_START_HERE.cmd calls. It is not on the menu:
#: the menu is for somebody who already has Dispatch working, and this is the
#: path for somebody who does not yet.
_COMMANDS = ("menu", "status", "settings", "version", "start-here", *_ACTIONS)


def render_menu() -> str:
    """The menu, with icons if the console can draw them and without if not."""
    lines = [""]
    for key, glyph, label, _action in MENU_ITEMS:
        lines.append(f"  [{key}] {glyphs.prefix(glyph)}{label}")
    for key, glyph, label, _action in EXTRA_ITEMS:
        lines.append(f"  [{key}] {glyphs.prefix(glyph)}{label}")
    lines.append("  [Q] Quit")
    lines.append("")
    return "\n".join(lines)


def resolve_choice(choice: str) -> str | None:
    """Which action a typed choice means, or None if it means nothing."""
    cleaned = choice.strip().lower()
    for key, _glyph, _label, action in MENU_ITEMS + EXTRA_ITEMS:
        if cleaned == key.lower():
            return action
    for action, spellings in _ALIASES.items():
        if cleaned in spellings:
            return action
    return None


def _print_result(result: control.ControlResult) -> None:
    print()
    print(f"  {result.message}")
    for detail in result.details:
        if detail:
            print(f"      {detail}")
    print()


def _print_status(*, facts: probe.RuntimeFacts | None = None) -> status_module.LauncherStatus:
    reading = status_module.collect_status(facts=facts)
    print()
    print(status_module.render(reading))
    print()
    return reading


def _print_settings() -> settings_module.SettingsView:
    view = settings_module.collect_settings()
    print()
    print(settings_module.render_settings(view))
    print()
    return view


def _print_version() -> settings_module.VersionView:
    view = settings_module.collect_version()
    print()
    print(settings_module.render_version(view))
    print()
    return view


def run_action(action: str) -> control.ControlResult:
    if action == "start":
        return control.start()
    if action == "stop":
        return control.stop()
    if action == "restart":
        return control.restart()
    if action == "open":
        return control.open_portal()
    if action == "reset-session":
        return control.reset_session()
    if action == "reset-pin":
        from dispatch_launcher import first_run as _first_run

        return _first_run.reset_pin()
    raise ValueError(f"unknown action: {action}")


def run_menu(*, input_fn=input) -> int:
    """The interactive loop. `input_fn` is injected so the suite can drive it."""
    _print_status()
    while True:
        print(render_menu())
        try:
            raw = input_fn("  Choose: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        choice = (raw or "").strip().lower()
        if choice in ("q", "quit", "exit"):
            return 0

        action = resolve_choice(choice)
        if action is None:
            print(f"\n  '{choice}' is not one of the choices. Pick a number, or Q to quit.\n")
            continue

        if action == "status":
            _print_status()
        elif action == "settings":
            _print_settings()
        elif action == "version":
            _print_version()
        else:
            _print_result(run_action(action))
            # A control that changed something is followed by a fresh reading,
            # so the operator never has to ask for the status they just earned.
            _print_status()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dispatch_launcher",
        description="Start, stop and inspect the Dispatch operations portal.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=_COMMANDS,
        default="menu",
        help="what to do; omit for the interactive menu",
    )
    parser.add_argument(
        "--logs",
        action="store_true",
        help="print the launcher log directory and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.logs:
        print(locations.logs_dir())
        return 0

    if args.action == "menu":
        return run_menu()

    if args.action == "status":
        reading = _print_status()
        # Exit code carries the one fact a scheduled task cares about.
        return 0 if reading.running else 1

    if args.action == "settings":
        view = _print_settings()
        # Non-zero when a setting is actually stopping Dispatch from starting,
        # so `dispatch_launcher settings` is usable as a pre-flight check.
        return 1 if view.blocking else 0

    if args.action == "version":
        _print_version()
        return 0

    if args.action == "start-here":
        from dispatch_launcher import first_run as _first_run

        report = _first_run.first_run()
        print(_first_run.render(report))
        return 0 if report.started else 1

    result = run_action(args.action)
    _print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
