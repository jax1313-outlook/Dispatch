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

Every non-ASCII character is kept out of anything printed here on purpose: a
Windows console redirected to a file uses the machine's ANSI code page, and a
launcher that raises UnicodeEncodeError while reporting a problem is a launcher
that fails at the only moment it matters.
"""

from __future__ import annotations

import argparse
import sys

from dispatch_launcher import control, locations, probe, status as status_module

MENU = """
  [1] Start Dispatch
  [2] Stop Dispatch
  [3] Restart Dispatch
  [4] Open Portal in browser
  [5] Refresh status
  [Q] Quit
"""

_ACTIONS = ("start", "stop", "restart", "open")


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


def run_action(action: str) -> control.ControlResult:
    if action == "start":
        return control.start()
    if action == "stop":
        return control.stop()
    if action == "restart":
        return control.restart()
    if action == "open":
        return control.open_portal()
    raise ValueError(f"unknown action: {action}")


def run_menu(*, input_fn=input) -> int:
    """The interactive loop. `input_fn` is injected so the suite can drive it."""
    _print_status()
    while True:
        print(MENU)
        try:
            choice = input_fn("  Choose: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if choice in ("q", "quit", "exit", "6"):
            return 0
        if choice in ("1", "start"):
            _print_result(run_action("start"))
        elif choice in ("2", "stop"):
            _print_result(run_action("stop"))
        elif choice in ("3", "restart"):
            _print_result(run_action("restart"))
        elif choice in ("4", "open"):
            _print_result(run_action("open"))
        elif choice in ("5", "status", ""):
            _print_status()
        else:
            print(f"\n  '{choice}' is not one of the choices. Pick a number, or Q to quit.\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dispatch_launcher",
        description="Start, stop and inspect the Dispatch operations portal.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("menu", "status", *_ACTIONS),
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

    result = run_action(args.action)
    _print_result(result)
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
