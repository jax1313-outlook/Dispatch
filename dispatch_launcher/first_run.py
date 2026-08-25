"""The one-double-click path: everything that has to be true before Start works.

`dispatch.bat` opens the Control Center menu, which is right for somebody who knows
Dispatch and wants Restart or Settings. It is the wrong first contact for somebody who has
never run it, for two reasons that only show up on a real first attempt:

*It presents a menu before it presents a result.* Mike double-clicks, and Dispatch has not
started -- it is waiting for him to type a number. "One click, Dispatch starts" is a
different promise from "one click, a menu appears".

*It refuses to start on a fresh machine, correctly, and there is nothing he can do about
it.* `portal/config.py` blocks an operational start while `PORTAL_SECRET_KEY` or
`DISPATCH_EMAIL_SECRET` still hold the values published in this repository -- anyone who can
read the source can forge a session cookie or mint a stakeholder link, so refusing is the
only defensible behaviour. But the remedy is `setx` in a Command Prompt, and requiring that
of a non-developer means Dispatch never starts at all.

So this module does what an installer does: generates real per-machine secrets, persists
them, checks the dependency, and hands off to the ordinary Start path. Nothing here weakens
the refusal -- it *satisfies* it, which is the opposite. The published defaults stay
rejected; what changes is that the machine now has values of its own.

**The logic lives here and not in the .cmd file** because a batch file cannot be tested and
this is the code path a first-time operator meets before anything else has had a chance to
work. `DISPATCH_START_HERE.cmd` finds an interpreter and calls `start-here`; every decision
below it is Python the suite exercises.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from dataclasses import dataclass, field

from dispatch_launcher import control, locations

#: Bytes of entropy per generated secret. 48 URL-safe characters or so -- far past
#: anything that matters for HMAC, and short enough to paste if it ever has to be.
_SECRET_BYTES = 36

#: Set to "1" by the test suite so a check never shells out to `setx`.
NO_PERSIST_ENV = "DISPATCH_LAUNCHER_NO_PERSIST"


@dataclass
class FirstRunStep:
    """One thing that had to be true, and whether it was."""

    name: str
    ok: bool
    detail: str
    #: True when this step changed the machine rather than only inspecting it.
    changed: bool = False
    #: False for a step whose failure does not stop Dispatch. A browser that
    #: will not open is the whole category: Dispatch is running, the address is
    #: on screen, and marking that STOP next to a line saying "Dispatch is
    #: RUNNING" teaches an operator that the marks mean nothing.
    fatal: bool = True

    @property
    def mark(self) -> str:
        if self.ok:
            return "OK  "
        return "STOP" if self.fatal else "NOTE"


@dataclass
class FirstRunReport:
    steps: list[FirstRunStep] = field(default_factory=list)
    started: bool = False
    #: The plain-language sentence to show if something stopped it.
    blocker: str = ""
    #: What Mike should do about the blocker. Never a stack trace.
    remedy: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def ok(self) -> bool:
        return self.started and all(step.ok for step in self.steps if step.fatal)

    def add(
        self,
        name: str,
        ok: bool,
        detail: str,
        *,
        changed: bool = False,
        fatal: bool = True,
    ) -> None:
        self.steps.append(
            FirstRunStep(name=name, ok=ok, detail=detail, changed=changed, fatal=fatal)
        )


# ── secrets ──────────────────────────────────────────────────────────────────


def _published_defaults() -> dict[str, str]:
    """The application's own table, read rather than copied.

    A second copy here would drift the first time a third secret is added, and the drift
    would be invisible: this module would keep reporting a fresh machine as ready while the
    portal refused to start on the secret nobody told the launcher about.
    """
    from portal.config import _PUBLISHED_DEFAULTS

    return dict(_PUBLISHED_DEFAULTS)


def unset_or_published(environ: dict[str, str] | None = None) -> list[str]:
    """Secrets that are missing, or still hold the value published in this repository.

    Both are the same problem wearing different clothes, and `portal.config` already treats
    them as one: a variable set to the value in the source file is not configured, it is
    advertised.
    """
    environ = os.environ if environ is None else environ
    return sorted(
        name
        for name, published in _published_defaults().items()
        if environ.get(name, published) == published
    )


def generate_secret() -> str:
    return secrets.token_urlsafe(_SECRET_BYTES)


def persist_secret(name: str, value: str) -> tuple[bool, str]:
    """Write the value where a future window will find it, and say what happened.

    `setx` writes the user's registry environment, which is what survives the console
    closing. It does **not** reach the process that called it, so the caller must also set
    it in this process -- that is the difference this function's docstring exists to record,
    because getting it wrong produces the most confusing possible symptom: Dispatch works
    now and is broken tomorrow.

    On anything other than Windows there is no `setx`; the value is live for this session
    and the caller is told so plainly rather than being allowed to believe it was saved.
    """
    if os.environ.get(NO_PERSIST_ENV) == "1":
        return False, "not saved (persistence disabled for this run)"
    if not sys.platform.startswith("win"):
        return False, (
            "set for this session only -- setx is a Windows command and this is not Windows"
        )
    try:
        completed = subprocess.run(
            ["setx", name, value],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Never let this stop the launch. A session-only secret still starts Dispatch;
        # it just has to be generated again next time, and the report says so.
        return False, f"set for this session only -- setx could not run ({exc.__class__.__name__})"
    if completed.returncode != 0:
        return False, "set for this session only -- setx reported an error"
    return True, "saved for future windows"


def ensure_secrets(report: FirstRunReport) -> None:
    """Give this machine real secrets if it does not have them.

    The generated value is **never** printed, logged, or returned. The report says a secret
    was created and whether it was saved; it does not say what it is. There is no flag that
    reveals it.
    """
    missing = unset_or_published()
    if not missing:
        report.add(
            "Security settings",
            True,
            "This machine already has its own settings. Nothing was changed.",
        )
        return

    saved: list[str] = []
    session_only: list[str] = []
    for name in missing:
        value = generate_secret()
        os.environ[name] = value  # this process, right now
        persisted, _how = persist_secret(name, value)
        (saved if persisted else session_only).append(name)

    if saved and not session_only:
        detail = (
            f"Created and saved {len(saved)} security setting(s) for this machine "
            f"({', '.join(saved)}). The values are not shown anywhere, by design."
        )
    elif saved:
        detail = (
            f"Created {len(saved) + len(session_only)} security setting(s). "
            f"{', '.join(saved)} saved for future windows; "
            f"{', '.join(session_only)} apply to this session only."
        )
    else:
        detail = (
            f"Created {len(session_only)} security setting(s) for this session only "
            f"({', '.join(session_only)}). They will be created again next time."
        )
    report.add("Security settings", True, detail, changed=True)


# ── dependency ───────────────────────────────────────────────────────────────


def flask_installed() -> bool:
    from importlib.util import find_spec

    try:
        return find_spec("flask") is not None
    except (ImportError, ValueError):  # pragma: no cover - malformed install only
        return False


def install_flask() -> tuple[bool, str]:
    """Install the one hard dependency, because a non-developer cannot run pip.

    Only Flask. This is not a general installer and must not become one -- `paramiko` and
    `anthropic` are optional and Dispatch reports them `ABSENT` without complaint.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", "flask"],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not run pip ({exc.__class__.__name__})"
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        return False, tail[-1][:200] if tail else "pip reported an error"
    return True, "installed"


def ensure_flask(report: FirstRunReport) -> bool:
    if flask_installed():
        report.add("Flask", True, "Already installed.")
        return True

    ok, detail = install_flask()
    if ok and flask_installed():
        report.add("Flask", True, "Was missing. Installed it.", changed=True)
        return True

    report.add("Flask", False, f"Missing, and it could not be installed: {detail}")
    report.blocker = "Dispatch needs a component called Flask, and it is not installed."
    report.remedy = [
        "Open the Start menu, type: Command Prompt, and open it.",
        "Type this line exactly, then press Enter:",
        "    py -3 -m pip install flask",
        "When it finishes, double-click DISPATCH_START_HERE again.",
        "If it says 'py' is not recognized, Python is not installed -- see python.org/downloads",
        "and tick 'Add Python to PATH' during setup.",
    ]
    return False


def remedy_for(message: str, details: list[str] | None = None) -> list[str]:
    """Turn a start failure into something a non-developer can act on.

    `control.start()` already produces one accurate plain sentence, and for most failures
    its own details are the best available advice. This adds instructions for the failure
    that is both common and un-actionable as stated: "port 8080 is already in use" tells a
    developer everything and tells Mike nothing.

    Keyed on the message rather than an error code because the message is what the operator
    is looking at -- if the two ever disagree, the screen is the one that has to be right.
    """
    details = list(details or [])
    if "already in use" in message:
        return details + [
            "Something else on this computer is using the address Dispatch wants.",
            "Usually that is a copy of Dispatch that was left running.",
            "",
            "Try this first: close every black Dispatch window, wait ten seconds,",
            "and double-click DISPATCH_START_HERE again.",
            "",
            "If that does not work, restart the computer and try once more.",
        ]
    if "PORTAL_SECRET_KEY" in message or "DISPATCH_EMAIL_SECRET" in message:
        # Should be unreachable -- ensure_secrets() runs first and fixes exactly this.
        # Kept because "unreachable" is a claim about today's code, and the operator
        # standing in front of a stopped Dispatch deserves a next step either way.
        return details + [
            "Dispatch could not create its security settings automatically.",
            "Double-click DISPATCH_START_HERE once more; this often clears on a",
            "second run. If it does not, this one needs a builder.",
        ]
    return details or [
        "Open the Dispatch Control Center (dispatch.bat) and choose Refresh Status.",
        "It prints the reason in plain language.",
    ]


# ── the PIN, without which Dispatch opens a door he cannot walk through ──────

#: Set by the suite. Also the honest escape hatch for a genuinely non-interactive
#: run, where prompting would hang forever waiting for a keystroke nobody will type.
NO_PIN_PROMPT_ENV = "DISPATCH_LAUNCHER_NO_PIN_PROMPT"

#: The identity this build creates. `portal.models.identity` supports exactly one.
AUTHORITY_USER_ID = "mike"
AUTHORITY_DISPLAY_NAME = "Mike Zachary"

MIN_PIN_LENGTH = 4


def identity_exists() -> bool:
    from portal.models import identity as identity_model

    return identity_model.has_any_identity()


def _interactive(stream=None) -> bool:
    """Is there a person at a keyboard? Prompting when there is not, hangs."""
    if os.environ.get(NO_PIN_PROMPT_ENV) == "1":
        return False
    stream = stream if stream is not None else sys.stdin
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def prompt_for_pin(*, getpass_fn=None, attempts: int = 3, first_time: bool = True) -> str | None:
    """Ask twice, echo neither, and say what was wrong rather than just "invalid".

    Returns the PIN, or None if the person gave up or ran out of attempts. `getpass_fn` is
    injected so the suite can drive this without a terminal.

    `first_time` exists because the same prompt serves setup and reset, and telling somebody
    resetting a forgotten PIN that they "only do this once" is both false and faintly
    insulting -- they are visibly doing it a second time.
    """
    import getpass as _getpass

    getpass_fn = getpass_fn or _getpass.getpass

    print()
    if first_time:
        print("  Dispatch needs a PIN before you can sign in.")
        print("  You choose it now, you only do this once, and nothing is shown as you type.")
    else:
        print("  Choose the new PIN. Nothing is shown as you type.")
    print(f"  It must be at least {MIN_PIN_LENGTH} characters. Digits are fine.")
    print()

    for remaining in range(attempts, 0, -1):
        try:
            pin = getpass_fn("  Choose a PIN: ")
            confirm = getpass_fn("  Type it again: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if pin != confirm:
            print("  Those did not match. Nothing was saved.")
        elif len(pin) < MIN_PIN_LENGTH:
            print(f"  Too short -- it needs at least {MIN_PIN_LENGTH} characters.")
        else:
            return pin

        if remaining > 1:
            print("  Try again.")
            print()
    return None


def ensure_identity(report: FirstRunReport, *, getpass_fn=None) -> None:
    """Create the sign-in identity if this machine has none.

    Placed **before** Start in `first_run`, because the alternative is what shipped: Dispatch
    starts, the browser opens on a sign-in page, and every PIN is rejected with a message
    naming a console script that is not installed. A working server behind a door nobody can
    open is not a working Dispatch, and it is a worse failure than not starting -- it looks
    like success.

    The PIN never appears on screen, in the report, or in a log. Only its existence does.
    """
    try:
        if identity_exists():
            report.add(
                "Sign-in PIN",
                True,
                "Already set on this machine. Nothing was changed.",
            )
            return
    except Exception as exc:  # pragma: no cover - unreadable data directory only
        report.add(
            "Sign-in PIN",
            True,
            f"Could not be checked ({exc.__class__.__name__}). Dispatch will still start.",
            fatal=False,
        )
        return

    if not _interactive():
        report.add(
            "Sign-in PIN",
            True,
            "Not set, and there is no keyboard attached to this run. Dispatch will start, "
            "but you will not be able to sign in until a PIN is set -- run this again from a "
            "normal window, or use Reset PIN in the Dispatch Control Center.",
            fatal=False,
        )
        return

    pin = prompt_for_pin(getpass_fn=getpass_fn)
    if pin is None:
        report.add(
            "Sign-in PIN",
            True,
            "Not set. Dispatch will start, but the sign-in page will not let you in until "
            "you set one -- double-click DISPATCH_START_HERE again, or use Reset PIN in the "
            "Dispatch Control Center.",
            fatal=False,
        )
        return

    from portal.models import identity as identity_model

    try:
        identity_model.bootstrap_authority(AUTHORITY_USER_ID, AUTHORITY_DISPLAY_NAME, pin)
    except identity_model.IdentityError as exc:
        report.add("Sign-in PIN", False, f"Could not be set: {exc}")
        report.blocker = "Dispatch could not save your PIN."
        report.remedy = [
            "Double-click DISPATCH_START_HERE again and choose a PIN once more.",
            "If it fails the same way twice, this one needs a builder.",
        ]
        return

    report.add(
        "Sign-in PIN",
        True,
        "Set. Use it on the Dispatch sign-in page. It is not stored anywhere you can read "
        "it back, so if you forget it, use Reset PIN in the Dispatch Control Center.",
        changed=True,
    )


def reset_pin(*, getpass_fn=None, input_fn=None) -> "control.ControlResult":
    """The Control Center's `[P] Reset PIN`. The way back in from a forgotten PIN.

    Lives in this module rather than `control.py` because it is PIN work and reuses
    `prompt_for_pin` -- `control.py` is about processes, and a second copy of the prompt is
    exactly the duplication that produces two behaviours from one rule.

    It does **not** ask for the old PIN. The person who needs this does not have it; that is
    the whole situation. What stands in for it is a typed confirmation, because a reset must
    not be reachable by mis-keying a menu letter, and physical access to this machine -- see
    `identity.set_pin` for why that is the honest trust basis rather than a shortcut.
    """
    if not identity_exists():
        return control.ControlResult(
            action="reset-pin",
            ok=False,
            message="There is no PIN on this machine yet, so there is nothing to reset.",
            details=[
                "Double-click DISPATCH_START_HERE and it will ask you to choose one.",
            ],
        )

    if not _interactive():
        return control.ControlResult(
            action="reset-pin",
            ok=False,
            message="Resetting the PIN needs a keyboard, and this run does not have one.",
            details=["Open the Dispatch Control Center in a normal window and choose [P]."],
        )

    input_fn = input_fn or input
    print()
    print("  RESET PIN")
    print()
    print("  This replaces the Dispatch sign-in PIN with a new one you choose now.")
    print("  You will not be asked for the old one -- this is the way back in when it")
    print("  has been forgotten. Anyone at this keyboard can do it.")
    print()
    print("  Nothing else changes. Loads, milestones and evidence are untouched.")
    print()
    try:
        answer = input_fn("  Type RESET to continue, or press Enter to cancel: ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if (answer or "").strip().upper() != "RESET":
        return control.ControlResult(
            action="reset-pin", ok=True, message="Cancelled. The PIN was not changed."
        )

    pin = prompt_for_pin(getpass_fn=getpass_fn, first_time=False)
    if pin is None:
        return control.ControlResult(
            action="reset-pin", ok=True, message="Cancelled. The PIN was not changed."
        )

    from portal.models import identity as identity_model

    user_id = identity_model.get_authority_user_id() or AUTHORITY_USER_ID
    try:
        identity_model.set_pin(user_id, pin)
    except identity_model.IdentityError as exc:
        return control.ControlResult(
            action="reset-pin", ok=False, message=f"The PIN was not changed: {exc}"
        )

    return control.ControlResult(
        action="reset-pin",
        ok=True,
        message="The PIN has been reset. Use the new one on the Dispatch sign-in page.",
        details=[
            "Any lockout from earlier failed attempts has been cleared.",
            "If Dispatch is open in a browser, sign out and back in.",
        ],
    )


# ── the desktop shortcut, which is the actual fix ────────────────────────────

#: Skips shortcut creation. Set by the suite, and available to anyone who does not
#: want Dispatch putting an icon on their desktop.
NO_SHORTCUT_ENV = "DISPATCH_LAUNCHER_NO_SHORTCUT"

SHORTCUT_NAME = "Dispatch.lnk"


def desktop_dir() -> "os.PathLike[str] | None":
    """This user's Desktop, or None if it cannot be located."""
    from pathlib import Path

    candidate = Path(os.path.expanduser("~")) / "Desktop"
    return candidate if candidate.is_dir() else None


def create_desktop_shortcut(target: "os.PathLike[str]") -> tuple[bool, str]:
    """Put a `Dispatch` icon on the Desktop pointing at `target`.

    **This is the fix for the defect, not a convenience.** The reported problem was not
    "Dispatch will not start" -- it was *"I cannot find it."* And that is accurate rather
    than careless: the repository root holds 13 folders and 70 files, most of them named
    `DISPATCH_SOMETHING.md`, and Windows hides known extensions by default, so a folder
    named `dispatch` and a launcher named `dispatch.bat` **display under the same name**,
    with the folder listed first because Explorer sorts folders above files. Clicking the
    obvious thing opens a folder of Python source.

    A launch file nobody can find is a launch file that does not exist. A Desktop icon is
    findable by construction, and after the first run the repository never has to be opened
    again.

    Creation is best-effort and never blocks a launch: an operator with a stopped Dispatch
    and no icon is better off than one with an icon and a refusal.
    """
    from pathlib import Path

    if os.environ.get(NO_SHORTCUT_ENV) == "1":
        return False, "skipped"
    if not sys.platform.startswith("win"):
        return False, (
            "desktop shortcuts are a Windows feature and this is not Windows"
        )
    desktop = desktop_dir()
    if desktop is None:
        return False, "this user's Desktop folder could not be found"

    link = Path(desktop) / SHORTCUT_NAME
    if link.exists():
        return False, "already there"

    target = Path(target)
    # WScript.Shell is present on every supported Windows and needs no dependency.
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
        "$s.TargetPath = '{target}';"
        "$s.WorkingDirectory = '{working}';"
        "$s.Description = 'Start Dispatch';"
        "$s.Save()"
    ).format(link=link, target=target, working=target.parent)
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"could not be created ({exc.__class__.__name__})"
    if completed.returncode != 0 or not link.exists():
        return False, "could not be created"
    return True, str(link)


def ensure_desktop_shortcut(report: FirstRunReport) -> None:
    target = locations.repo_root() / "DISPATCH_START_HERE.cmd"
    created, detail = create_desktop_shortcut(target)
    if created:
        report.add(
            "Desktop shortcut",
            True,
            f"Put a Dispatch icon on your Desktop: {detail}. From now on you can start "
            "Dispatch from there and never open this folder again. Delete the icon if you "
            "do not want it.",
            changed=True,
            fatal=False,
        )
        return
    if detail == "already there":
        report.add(
            "Desktop shortcut",
            True,
            "The Dispatch icon is already on your Desktop.",
            fatal=False,
        )
        return
    report.add("Desktop shortcut", True, f"Not created: {detail}.", fatal=False)


# ── the whole path ───────────────────────────────────────────────────────────


def first_run(*, open_browser: bool = True) -> FirstRunReport:
    """Make a fresh machine ready, start Dispatch, and open it. In that order.

    Order matters and is not arbitrary. Secrets before the dependency check, because a
    missing secret is the failure that stops a first run and it is free to fix. The
    dependency before Start, because Start's failure message for a missing Flask is
    accurate but not actionable by the person reading it. Start before the browser, because
    opening a browser at a port nothing is listening on shows a connection error and looks
    exactly like Dispatch being broken.
    """
    report = FirstRunReport()

    report.add("Dispatch folder", True, str(locations.repo_root()))

    ensure_secrets(report)
    if not ensure_flask(report):
        return report

    # Before Start, deliberately: see ensure_identity's docstring. A server behind a
    # door nobody can open looks like success and is not.
    ensure_identity(report)
    if report.blocker:
        return report

    result = control.start()
    report.started = bool(result.ok)
    report.add(
        "Start",
        report.started,
        result.message or ("Dispatch is running." if report.started else "Did not start."),
    )

    if not report.started:
        report.blocker = result.message or "Dispatch did not start."
        report.remedy = remedy_for(report.blocker, result.details)
        return report

    from dispatch_launcher import probe

    report.url = probe.probe_runtime().url

    # After Start, deliberately. It is the answer to "I cannot find it", not a
    # precondition for running, and a shortcut created beside a Dispatch that
    # failed to start would be an icon that reproduces the failure on every click.
    ensure_desktop_shortcut(report)

    if open_browser:
        opened = control.open_portal()
        report.add(
            "Open in browser",
            bool(opened.ok),
            opened.message
            or ("Opened." if opened.ok else "Could not open a browser automatically."),
            fatal=False,
        )
    return report


def render(report: FirstRunReport) -> str:
    """What Mike reads. No jargon, no traceback, and never a secret value."""
    lines = ["", "  DISPATCH", ""]
    for step in report.steps:
        mark = step.mark
        changed = "  (changed)" if step.changed else ""
        lines.append(f"    [{mark}] {step.name}{changed}")
        lines.append(f"           {step.detail}")
    lines.append("")

    if report.started:
        lines.append(f"    Dispatch is RUNNING at {report.url}")
        lines.append("")
        lines.append("    Your browser should have opened. If it did not, open it")
        lines.append(f"    yourself and go to:  {report.url}")
        lines.append("")
        lines.append("    Anything marked NOTE above is not a problem. Dispatch is")
        lines.append("    running. Anything marked STOP would have stopped it.")
        lines.append("")
        lines.append("    Leave this window open while you use Dispatch.")
        lines.append("    To stop Dispatch, press any key in this window.")
    else:
        lines.append(f"    DISPATCH DID NOT START.")
        lines.append("")
        lines.append(f"    {report.blocker}")
        if report.remedy:
            lines.append("")
            lines.append("    What to do:")
            for line in report.remedy:
                lines.append(f"      {line}")
    lines.append("")
    return "\n".join(lines)
