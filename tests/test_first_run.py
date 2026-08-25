"""The one-double-click path, and the reasons each step of it exists.

`dispatch_launcher/first_run.py` is the first code a new operator meets. Everything it does
is something that would otherwise stop a first run dead, so these tests are mostly about
failure: what happens when there are no secrets, when Flask is missing, when the port is
held, when `setx` is not available. The happy path is the short one.

Two rules run through all of it:

- **A generated secret is never returned, printed, or logged.** Several tests assert the
  absence of the value rather than the presence of anything, which is the only way to test
  a negative that matters.
- **Nothing here weakens the refusal in `portal/config.py`.** The published defaults stay
  rejected. What changes is that the machine gets values of its own.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dispatch_launcher import control, first_run

REPO_ROOT = Path(__file__).resolve().parent.parent


#: The PIN used by every "is it stored or printed in plaintext?" assertion.
#:
#: Those assertions are substring searches, and a short numeric PIN makes them a coin
#: flip rather than a test. `generate_password_hash` renders a 128-character digest in
#: hex -- an alphabet of `0-9a-f` that **contains every digit a numeric PIN is made
#: of** -- so a 4-digit PIN appears inside an unrelated hash by pure chance about
#: 0.19% of the time, or 0.57% across the three Python versions CI runs.
#:
#: That is not a hypothetical: `test_it_stores_a_hash_and_never_the_pin` failed exactly
#: this way on py3.11 while 3.12 and 3.13 passed on the same commit, with `4417` found
#: inside `...36a1beb2594417a13679761c...`. The code was correct; the assertion was
#: unsound. A test that fails one run in 175 for a reason unrelated to the defect it
#: guards teaches people to re-run CI, which is how a real failure gets waved through.
#:
#: This value contains characters that cannot occur in a hex digest at all, and is long
#: enough that a chance match in the alphanumeric salt is not worth a number. A hit is
#: therefore a real leak, which is the only thing the assertion should be able to mean.
LEAK_PROBE_PIN = "leak-probe-pin-never-stored-in-plaintext"


@pytest.fixture(autouse=True)
def _never_shell_out(monkeypatch):
    """No test may run `setx` or `pip` against the machine running the suite."""
    monkeypatch.setenv(first_run.NO_PERSIST_ENV, "1")


# ── the launch file itself ───────────────────────────────────────────────────


class TestTheLaunchFileExists:
    """Mission: *one file, one click, Dispatch starts.* Assert the file, not the intent."""

    def test_dispatch_start_here_is_at_the_repository_root(self):
        path = REPO_ROOT / "DISPATCH_START_HERE.cmd"
        assert path.is_file(), (
            "DISPATCH_START_HERE.cmd is missing. It is the launch path for somebody who "
            "does not know the repository; a launcher he cannot find is a launcher that "
            "does not exist."
        )

    def test_it_uses_crlf_so_cmd_exe_can_run_it(self):
        raw = (REPO_ROOT / "DISPATCH_START_HERE.cmd").read_bytes()
        assert b"\r\n" in raw
        assert raw.replace(b"\r\n", b"").count(b"\n") == 0, (
            "A bare LF before a `goto :label` is not reliably tolerated by cmd.exe. "
            ".gitattributes pins this; the test is what proves the pin held on checkout."
        )

    def test_it_holds_no_logic_of_its_own(self):
        """A batch file cannot be tested, so it is not allowed to decide anything.

        It may find an interpreter and hold the window open. Everything else belongs in
        `first_run.py`, where the suite can reach it.
        """
        text = (REPO_ROOT / "DISPATCH_START_HERE.cmd").read_text(encoding="utf-8")
        assert "dispatch_launcher start-here" in text
        # The only branches permitted are the interpreter check and the two exit paths.
        labels = {line.strip() for line in text.splitlines() if line.strip().startswith(":")}
        assert labels <= {":no_python", ":did_not_start"}, (
            f"New control flow appeared in the launch file: {labels}. Logic belongs in "
            "dispatch_launcher/first_run.py where it can be tested."
        )

    def test_the_no_python_message_names_the_download_and_the_checkbox(self):
        """The single most likely first-run failure on a fresh laptop.

        "Add Python to PATH" is off by default and is the difference between Dispatch
        working and Dispatch appearing broken, so the message has to name it.
        """
        text = (REPO_ROOT / "DISPATCH_START_HERE.cmd").read_text(encoding="utf-8")
        assert "python.org/downloads" in text
        assert "Add Python to PATH" in text

    def test_every_failure_path_holds_the_window_open(self):
        """A window that closes instantly reads as "nothing happened"."""
        text = (REPO_ROOT / "DISPATCH_START_HERE.cmd").read_text(encoding="utf-8")
        for label in (":no_python", ":did_not_start"):
            section = text.split(label, 1)[1]
            assert "pause" in section.split("exit /b", 1)[0], (
                f"{label} can close the window before the message is read."
            )

    def test_the_launcher_cli_accepts_the_command_the_file_calls(self):
        """The file and the CLI must agree. This is how that stops drifting."""
        from dispatch_launcher import cli

        assert "start-here" in cli._COMMANDS


# ── secrets ──────────────────────────────────────────────────────────────────


class TestSecrets:
    def test_a_missing_secret_and_a_published_one_are_the_same_problem(self, monkeypatch):
        from portal.config import _PUBLISHED_DEFAULTS

        name, published = next(iter(_PUBLISHED_DEFAULTS.items()))
        monkeypatch.delenv(name, raising=False)
        assert name in first_run.unset_or_published()

        monkeypatch.setenv(name, published)
        assert name in first_run.unset_or_published(), (
            "A variable set to the value published in this repository is not configured -- "
            "it is advertised. portal.config treats the two identically and so must this."
        )

    def test_a_real_value_clears_it(self, monkeypatch):
        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.setenv(name, "a-real-per-machine-value-nobody-published")
        assert first_run.unset_or_published() == []

    def test_generated_secrets_are_long_and_never_repeat(self):
        made = {first_run.generate_secret() for _ in range(50)}
        assert len(made) == 50
        assert all(len(value) >= 40 for value in made)

    def test_ensure_secrets_sets_them_for_this_process(self, monkeypatch):
        import os

        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.delenv(name, raising=False)

        report = first_run.FirstRunReport()
        first_run.ensure_secrets(report)

        assert first_run.unset_or_published() == []
        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            assert os.environ[name]
        step = report.steps[-1]
        assert step.ok and step.changed

    def test_the_generated_value_never_reaches_the_report_or_the_screen(self, monkeypatch):
        """The test that matters. A secret Dispatch prints is a secret Dispatch leaked."""
        import os

        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.delenv(name, raising=False)

        report = first_run.FirstRunReport()
        first_run.ensure_secrets(report)

        values = [os.environ["PORTAL_SECRET_KEY"], os.environ["DISPATCH_EMAIL_SECRET"]]
        rendered = first_run.render(report)
        blob = rendered + repr(report)
        for value in values:
            assert value not in blob, "a generated secret reached the report or the screen"
        # The names are fine, and are what an operator needs to act.
        assert "PORTAL_SECRET_KEY" in rendered

    def test_nothing_is_changed_when_the_machine_already_has_its_own(self, monkeypatch):
        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.setenv(name, "already-set-by-a-human-with-setx")

        report = first_run.FirstRunReport()
        first_run.ensure_secrets(report)

        step = report.steps[-1]
        assert step.ok and not step.changed
        assert "Nothing was changed" in step.detail

    def test_persistence_is_reported_honestly_when_setx_is_unavailable(self, monkeypatch):
        """Off Windows there is no `setx`, and saying "saved" would be a lie."""
        monkeypatch.delenv(first_run.NO_PERSIST_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        persisted, how = first_run.persist_secret("PORTAL_SECRET_KEY", "value")
        assert persisted is False
        assert "this session only" in how

    def test_a_setx_failure_does_not_stop_the_launch(self, monkeypatch):
        """A session-only secret still starts Dispatch. Refusing over it would be worse."""
        monkeypatch.delenv(first_run.NO_PERSIST_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")

        def _boom(*args, **kwargs):
            raise OSError("setx is not on PATH")

        monkeypatch.setattr(first_run.subprocess, "run", _boom)
        persisted, how = first_run.persist_secret("PORTAL_SECRET_KEY", "value")
        assert persisted is False
        assert "this session only" in how

    def test_a_nonzero_setx_is_not_reported_as_saved(self, monkeypatch):
        monkeypatch.delenv(first_run.NO_PERSIST_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(
            first_run.subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "denied"),
        )
        persisted, how = first_run.persist_secret("PORTAL_SECRET_KEY", "value")
        assert persisted is False
        assert "session only" in how

    def test_a_successful_setx_is_reported_as_saved(self, monkeypatch):
        monkeypatch.delenv(first_run.NO_PERSIST_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(
            first_run.subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess(a, 0, "SUCCESS", ""),
        )
        persisted, how = first_run.persist_secret("PORTAL_SECRET_KEY", "value")
        assert persisted is True
        assert "future windows" in how

    def test_it_does_not_weaken_the_refusal_it_satisfies(self, monkeypatch):
        """The published defaults must still be rejected afterwards.

        The whole design rests on this: `first_run` gives the machine real values, it does
        not teach `portal.config` to accept fake ones.
        """
        from portal.config import _PUBLISHED_DEFAULTS, check_secrets

        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.delenv(name, raising=False)
        first_run.ensure_secrets(first_run.FirstRunReport())
        assert check_secrets() == []

        monkeypatch.setenv("PORTAL_SECRET_KEY", _PUBLISHED_DEFAULTS["PORTAL_SECRET_KEY"])
        monkeypatch.setenv("DISPATCH_MODE", "operational")
        with pytest.raises(Exception):
            check_secrets()


# ── Flask ────────────────────────────────────────────────────────────────────


class TestFlask:
    def test_an_installed_flask_is_left_alone(self):
        report = first_run.FirstRunReport()
        assert first_run.ensure_flask(report) is True
        assert report.steps[-1].ok and not report.steps[-1].changed

    def test_a_missing_flask_is_installed(self, monkeypatch):
        calls: list[str] = []
        state = {"installed": False}

        monkeypatch.setattr(
            first_run, "flask_installed", lambda: state["installed"]
        )

        def _install():
            calls.append("pip")
            state["installed"] = True
            return True, "installed"

        monkeypatch.setattr(first_run, "install_flask", _install)

        report = first_run.FirstRunReport()
        assert first_run.ensure_flask(report) is True
        assert calls == ["pip"]
        assert report.steps[-1].changed

    def test_an_uninstallable_flask_gives_instructions_a_person_can_follow(
        self, monkeypatch
    ):
        monkeypatch.setattr(first_run, "flask_installed", lambda: False)
        monkeypatch.setattr(
            first_run, "install_flask", lambda: (False, "no network")
        )

        report = first_run.FirstRunReport()
        assert first_run.ensure_flask(report) is False
        assert report.blocker
        joined = "\n".join(report.remedy)
        # A command to type, and where to type it. Not "install Flask".
        assert "pip install flask" in joined
        assert "Command Prompt" in joined
        rendered = first_run.render(report)
        assert "DISPATCH DID NOT START" in rendered
        assert "Traceback" not in rendered

    def test_install_flask_reports_a_pip_failure_rather_than_raising(self, monkeypatch):
        monkeypatch.setattr(
            first_run.subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "network unreachable"),
        )
        ok, detail = first_run.install_flask()
        assert ok is False
        assert "network unreachable" in detail

    def test_install_flask_survives_pip_not_existing(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise OSError("no pip")

        monkeypatch.setattr(first_run.subprocess, "run", _boom)
        ok, detail = first_run.install_flask()
        assert ok is False
        assert "could not run pip" in detail


# ── remedies ─────────────────────────────────────────────────────────────────


class TestRemedies:
    def test_a_port_conflict_becomes_something_mike_can_do(self):
        remedy = "\n".join(
            first_run.remedy_for("Dispatch could not start because port 8080 is already in use.")
        )
        assert "close every black Dispatch window" in remedy
        assert "restart the computer" in remedy
        assert "8080" not in remedy or "close every" in remedy

    def test_an_unrecognised_failure_still_names_a_next_step(self):
        remedy = first_run.remedy_for("Something nobody anticipated happened.")
        assert remedy
        assert any("Refresh Status" in line for line in remedy)

    def test_the_launchers_own_details_are_preferred_when_it_has_them(self):
        remedy = first_run.remedy_for(
            "Something unusual.", ["Process ID 4242 is holding the port."]
        )
        assert remedy == ["Process ID 4242 is holding the port."]


# ── the whole path ───────────────────────────────────────────────────────────


class TestFirstRun:
    def test_a_fresh_machine_reaches_a_running_dispatch(self, monkeypatch):
        for name in ("PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(
            control,
            "start",
            lambda: control.ControlResult(
                action="start", ok=True, message="Dispatch is running (process ID 42)"
            ),
        )

        report = first_run.first_run(open_browser=False)

        assert report.started is True
        assert report.ok is True
        assert [step.name for step in report.steps] == [
            "Dispatch folder",
            "Security settings",
            "Flask",
            "Sign-in PIN",
            "Start",
            "Desktop shortcut",
        ]
        rendered = first_run.render(report)
        assert "Dispatch is RUNNING" in rendered
        assert "press any key" in rendered

    def test_the_browser_is_opened_only_after_the_server_is_up(self, monkeypatch):
        """Order is the whole point.

        A browser pointed at a port nothing is listening on shows a connection error, which
        is indistinguishable from Dispatch being broken -- to the one person who most needs
        to be able to tell the difference.
        """
        order: list[str] = []
        monkeypatch.setattr(
            control,
            "start",
            lambda: (order.append("start"), control.ControlResult("start", True, "up"))[1],
        )
        monkeypatch.setattr(
            control,
            "open_portal",
            lambda: (order.append("open"), control.ControlResult("open", True, "opened"))[1],
        )
        first_run.first_run(open_browser=True)
        assert order == ["start", "open"]

    def test_a_browser_that_will_not_open_is_a_NOTE_and_not_a_STOP(self, monkeypatch):
        """Dispatch is running. Marking that STOP teaches the marks mean nothing."""
        monkeypatch.setattr(
            control, "start", lambda: control.ControlResult("start", True, "up")
        )
        monkeypatch.setattr(
            control,
            "open_portal",
            lambda: control.ControlResult("open", False, "no browser here"),
        )
        report = first_run.first_run(open_browser=True)

        assert report.started is True
        assert report.ok is True, "a browser failure must not fail the run"
        browser_step = report.steps[-1]
        assert browser_step.ok is False
        assert browser_step.fatal is False
        assert browser_step.mark == "NOTE"
        rendered = first_run.render(report)
        assert "[NOTE]" in rendered and "[STOP]" not in rendered
        assert "Dispatch is RUNNING" in rendered

    def test_a_failed_start_says_so_plainly_and_never_shows_a_traceback(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            control,
            "start",
            lambda: control.ControlResult(
                action="start",
                ok=False,
                message="Dispatch could not start because port 8080 is already in use.",
            ),
        )
        report = first_run.first_run(open_browser=False)

        assert report.started is False
        assert report.ok is False
        rendered = first_run.render(report)
        assert "DISPATCH DID NOT START" in rendered
        assert "[STOP]" in rendered
        assert "close every black Dispatch window" in rendered
        for noise in ("Traceback", "Exception", "errno", "File \""):
            assert noise not in rendered

    def test_the_flask_gate_stops_before_start_is_ever_attempted(self, monkeypatch):
        """A Start failure for a missing Flask is accurate and not actionable."""
        started: list[str] = []
        monkeypatch.setattr(first_run, "flask_installed", lambda: False)
        monkeypatch.setattr(first_run, "install_flask", lambda: (False, "offline"))
        monkeypatch.setattr(
            control,
            "start",
            lambda: (started.append("x"), control.ControlResult("start", True, "up"))[1],
        )

        report = first_run.first_run(open_browser=False)
        assert started == [], "Start was attempted with a known-missing dependency"
        assert report.started is False


# ── the desktop shortcut ─────────────────────────────────────────────────────


class TestDesktopShortcut:
    """The actual fix for the reported defect.

    Mike's words were *"I cannot find it"*, and he was right to say so: the repository root
    holds 13 folders and 70 files, and with Windows' default "hide extensions for known file
    types" the `dispatch` folder and `dispatch.bat` display under the same name -- with the
    folder listed first, because Explorer sorts folders above files.
    """

    def test_it_is_skipped_off_windows_and_says_why(self, monkeypatch):
        monkeypatch.delenv(first_run.NO_SHORTCUT_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "linux")

        created, detail = first_run.create_desktop_shortcut(Path("/x/DISPATCH_START_HERE.cmd"))
        assert created is False
        assert "not Windows" in detail

    def test_an_existing_icon_is_left_alone(self, monkeypatch, tmp_path):
        monkeypatch.delenv(first_run.NO_SHORTCUT_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        (desktop / first_run.SHORTCUT_NAME).write_text("existing")
        monkeypatch.setattr(first_run, "desktop_dir", lambda: desktop)

        def _must_not_run(*args, **kwargs):
            raise AssertionError("an existing shortcut was overwritten")

        monkeypatch.setattr(first_run.subprocess, "run", _must_not_run)
        created, detail = first_run.create_desktop_shortcut(tmp_path / "DISPATCH_START_HERE.cmd")
        assert created is False
        assert detail == "already there"

    def test_it_points_at_the_launch_file_and_the_repository_folder(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.delenv(first_run.NO_SHORTCUT_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr(first_run, "desktop_dir", lambda: desktop)
        target = tmp_path / "repo" / "DISPATCH_START_HERE.cmd"
        target.parent.mkdir()
        target.write_text("@echo off")

        seen: dict[str, str] = {}

        def _fake_powershell(argv, **kwargs):
            seen["script"] = argv[-1]
            (desktop / first_run.SHORTCUT_NAME).write_text("link")
            return subprocess.CompletedProcess(argv, 0, "", "")

        monkeypatch.setattr(first_run.subprocess, "run", _fake_powershell)
        created, detail = first_run.create_desktop_shortcut(target)

        assert created is True
        assert first_run.SHORTCUT_NAME in detail
        assert str(target) in seen["script"]
        # WorkingDirectory matters: the launch file does `cd /d "%~dp0"`, but a shortcut
        # launched from the Desktop with the wrong working directory is a class of bug
        # worth pinning rather than rediscovering.
        assert str(target.parent) in seen["script"]

    def test_a_powershell_failure_never_blocks_the_launch(self, monkeypatch, tmp_path):
        monkeypatch.delenv(first_run.NO_SHORTCUT_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        desktop = tmp_path / "Desktop"
        desktop.mkdir()
        monkeypatch.setattr(first_run, "desktop_dir", lambda: desktop)

        def _boom(*args, **kwargs):
            raise OSError("powershell is blocked by policy")

        monkeypatch.setattr(first_run.subprocess, "run", _boom)

        report = first_run.FirstRunReport()
        first_run.ensure_desktop_shortcut(report)

        step = report.steps[-1]
        assert step.ok is True, "a missing icon is not a failed launch"
        assert step.fatal is False
        assert "Not created" in step.detail

    def test_the_shortcut_is_made_after_start_not_before(self, monkeypatch):
        """An icon beside a Dispatch that failed to start reproduces the failure per click."""
        order: list[str] = []
        monkeypatch.setattr(
            control,
            "start",
            lambda: (order.append("start"), control.ControlResult("start", True, "up"))[1],
        )
        monkeypatch.setattr(
            first_run,
            "ensure_desktop_shortcut",
            lambda report: order.append("shortcut"),
        )
        first_run.first_run(open_browser=False)
        assert order == ["start", "shortcut"]

    def test_no_shortcut_is_attempted_when_dispatch_did_not_start(self, monkeypatch):
        attempted: list[str] = []
        monkeypatch.setattr(
            control,
            "start",
            lambda: control.ControlResult("start", False, "port 8080 is already in use"),
        )
        monkeypatch.setattr(
            first_run,
            "ensure_desktop_shortcut",
            lambda report: attempted.append("x"),
        )
        first_run.first_run(open_browser=False)
        assert attempted == []

    def test_a_created_icon_tells_him_he_never_needs_this_folder_again(
        self, monkeypatch
    ):
        """The sentence is the deliverable, not the shortcut.

        The defect was "I cannot find it". An icon appearing silently fixes today's launch;
        saying what the icon is for fixes every launch after it.
        """
        monkeypatch.setattr(
            first_run, "create_desktop_shortcut", lambda target: (True, r"C:\Users\m\Desktop\Dispatch.lnk")
        )
        report = first_run.FirstRunReport()
        first_run.ensure_desktop_shortcut(report)

        step = report.steps[-1]
        assert step.ok and step.changed and step.fatal is False
        assert "never open this folder again" in step.detail
        assert "Delete the icon if you do not want it" in step.detail

    def test_an_icon_that_is_already_there_is_reported_without_claiming_a_change(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            first_run, "create_desktop_shortcut", lambda target: (False, "already there")
        )
        report = first_run.FirstRunReport()
        first_run.ensure_desktop_shortcut(report)

        step = report.steps[-1]
        assert step.ok is True
        assert step.changed is False, "nothing was changed, so nothing may claim it was"
        assert "already on your Desktop" in step.detail

    def test_desktop_dir_returns_none_when_there_is_no_desktop(self, monkeypatch, tmp_path):
        monkeypatch.setattr(first_run.os.path, "expanduser", lambda _: str(tmp_path))
        assert first_run.desktop_dir() is None

    def test_desktop_dir_finds_a_real_one(self, monkeypatch, tmp_path):
        (tmp_path / "Desktop").mkdir()
        monkeypatch.setattr(first_run.os.path, "expanduser", lambda _: str(tmp_path))
        assert first_run.desktop_dir() == tmp_path / "Desktop"

    def test_it_is_skipped_when_the_desktop_cannot_be_found(self, monkeypatch):
        monkeypatch.delenv(first_run.NO_SHORTCUT_ENV, raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(first_run, "desktop_dir", lambda: None)

        created, detail = first_run.create_desktop_shortcut(Path("x.cmd"))
        assert created is False
        assert "Desktop folder could not be found" in detail

    def test_the_opt_out_env_var_is_honoured(self, monkeypatch):
        monkeypatch.setenv(first_run.NO_SHORTCUT_ENV, "1")
        created, detail = first_run.create_desktop_shortcut(Path("x.cmd"))
        assert created is False
        assert detail == "skipped"


# ── the sign-in PIN ──────────────────────────────────────────────────────────


@pytest.fixture
def _isolated_identity(tmp_path, monkeypatch):
    """Point the identity store at a temp directory so no test touches a real one."""
    from portal.models import identity as identity_model

    store = tmp_path / "identity-store"
    store.mkdir()
    monkeypatch.setattr(identity_model, "get_data_dir", lambda: store)
    return identity_model


class TestSignInPin:
    """A fresh install had no PIN, and no way for a non-developer to make one.

    What shipped before this: Dispatch started, the browser opened on the sign-in page, and
    every PIN was rejected with *"No identity configured yet. Run cin-portal-init-admin on
    the server first."* — a console script that only exists after `pip install -e .`, which
    the launcher does not do. A running server behind a door nobody can open is a worse
    failure than not starting, because it looks like success.
    """

    def test_a_matching_pin_is_accepted(self):
        assert first_run.prompt_for_pin(getpass_fn=lambda _p: "8265") == "8265"

    def test_a_mismatch_is_retried_and_named(self, capsys):
        typed = iter(["8265", "8266", "4417", "4417"])
        assert first_run.prompt_for_pin(getpass_fn=lambda _p: next(typed)) == "4417"
        out = capsys.readouterr().out
        assert "did not match" in out
        assert "Nothing was saved" in out

    def test_too_short_is_named_rather_than_just_refused(self, capsys):
        typed = iter(["12", "12", "4417", "4417"])
        assert first_run.prompt_for_pin(getpass_fn=lambda _p: next(typed)) == "4417"
        assert "at least" in capsys.readouterr().out

    def test_it_gives_up_rather_than_looping_forever(self):
        typed = iter(["1", "1"] * 3)
        assert first_run.prompt_for_pin(getpass_fn=lambda _p: next(typed), attempts=3) is None

    def test_ctrl_c_is_not_a_crash(self):
        def _interrupt(_prompt):
            raise KeyboardInterrupt

        assert first_run.prompt_for_pin(getpass_fn=_interrupt) is None

    def test_the_reset_wording_does_not_claim_this_happens_once(self, capsys):
        first_run.prompt_for_pin(getpass_fn=lambda _p: "4417", first_time=False)
        out = capsys.readouterr().out
        assert "only do this once" not in out
        assert "new PIN" in out

    def test_a_fresh_machine_gets_an_identity_that_authenticates(
        self, _isolated_identity, monkeypatch
    ):
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        assert _isolated_identity.has_any_identity() is False

        typed = iter(["8265", "8265"])
        report = first_run.FirstRunReport()
        first_run.ensure_identity(report, getpass_fn=lambda _p: next(typed))

        assert _isolated_identity.has_any_identity() is True
        user_id = _isolated_identity.get_authority_user_id()
        assert _isolated_identity.verify_pin(user_id, "8265")
        assert _isolated_identity.verify_pin(user_id, "0000") is None
        assert report.steps[-1].ok and report.steps[-1].changed

    def test_the_pin_never_reaches_the_report_or_the_screen(
        self, _isolated_identity, monkeypatch
    ):
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        typed = iter([LEAK_PROBE_PIN, LEAK_PROBE_PIN])
        report = first_run.FirstRunReport()
        first_run.ensure_identity(report, getpass_fn=lambda _p: next(typed))

        blob = first_run.render(report) + repr(report)
        assert LEAK_PROBE_PIN not in blob, "the chosen PIN reached the report or the screen"
        # The step must still be there and still say a PIN was set -- otherwise this
        # test would pass just as well against code that silently did nothing.
        assert report.steps[-1].changed
        assert "Reset PIN" in report.steps[-1].detail

    def test_an_existing_pin_is_left_alone(self, _isolated_identity, monkeypatch):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)

        def _must_not_prompt(_p):
            raise AssertionError("it asked for a PIN when one already existed")

        report = first_run.FirstRunReport()
        first_run.ensure_identity(report, getpass_fn=_must_not_prompt)

        assert report.steps[-1].ok and not report.steps[-1].changed
        assert _isolated_identity.verify_pin("mike", "8265")

    def test_no_keyboard_means_dispatch_still_starts_and_says_why_you_cannot_sign_in(
        self, _isolated_identity, monkeypatch
    ):
        """A scheduled task or a piped run must not hang forever on a prompt."""
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: False)

        report = first_run.FirstRunReport()
        first_run.ensure_identity(report)

        step = report.steps[-1]
        assert step.ok is True and step.fatal is False
        assert "will not be able to sign in" in step.detail
        assert "Reset PIN" in step.detail
        assert _isolated_identity.has_any_identity() is False

    def test_giving_up_at_the_prompt_still_starts_dispatch(
        self, _isolated_identity, monkeypatch
    ):
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)

        def _interrupt(_p):
            raise KeyboardInterrupt

        report = first_run.FirstRunReport()
        first_run.ensure_identity(report, getpass_fn=_interrupt)

        step = report.steps[-1]
        assert step.ok is True and step.fatal is False
        assert "will not let you in" in step.detail

    def test_the_pin_is_set_before_the_server_starts(self, monkeypatch):
        """Order matters. Starting first opens a door nobody can walk through."""
        order: list[str] = []
        monkeypatch.setattr(
            first_run, "ensure_identity", lambda report, **kw: order.append("pin")
        )
        monkeypatch.setattr(
            control,
            "start",
            lambda: (order.append("start"), control.ControlResult("start", True, "up"))[1],
        )
        first_run.first_run(open_browser=False)
        assert order == ["pin", "start"]


class TestResetPin:
    """`[P] Reset PIN`. Before this there was no way back in from a forgotten PIN."""

    def test_it_refuses_when_there_is_nothing_to_reset(
        self, _isolated_identity, monkeypatch
    ):
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        result = first_run.reset_pin()
        assert result.ok is False
        assert "nothing to reset" in result.message
        assert any("DISPATCH_START_HERE" in d for d in result.details)

    def test_it_needs_a_typed_confirmation_not_just_a_menu_letter(
        self, _isolated_identity, monkeypatch
    ):
        """A reset must not be reachable by mis-keying."""
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)

        def _must_not_prompt(_p):
            raise AssertionError("it asked for a new PIN before being confirmed")

        result = first_run.reset_pin(input_fn=lambda _p: "", getpass_fn=_must_not_prompt)
        assert result.ok is True
        assert "not changed" in result.message
        assert _isolated_identity.verify_pin("mike", "8265"), "the old PIN was disturbed"

    def test_a_wrong_confirmation_word_cancels(self, _isolated_identity, monkeypatch):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        result = first_run.reset_pin(input_fn=lambda _p: "yes", getpass_fn=lambda _p: "4417")
        assert "not changed" in result.message
        assert _isolated_identity.verify_pin("mike", "8265")

    def test_the_confirmation_is_case_insensitive(self, _isolated_identity, monkeypatch):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        typed = iter(["4417", "4417"])
        result = first_run.reset_pin(
            input_fn=lambda _p: " reset ", getpass_fn=lambda _p: next(typed)
        )
        assert result.ok is True
        assert _isolated_identity.verify_pin("mike", "4417")

    def test_a_confirmed_reset_replaces_the_pin(self, _isolated_identity, monkeypatch):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        typed = iter(["4417", "4417"])

        result = first_run.reset_pin(
            input_fn=lambda _p: "RESET", getpass_fn=lambda _p: next(typed)
        )

        assert result.ok is True
        assert _isolated_identity.verify_pin("mike", "4417")
        assert _isolated_identity.verify_pin("mike", "8265") is None

    def test_a_reset_clears_a_lockout(self, _isolated_identity, monkeypatch):
        """Somebody locked out and then resetting at the keyboard has proven the only
        thing lockout protects against. Leaving them locked would punish the recovery."""
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        for _ in range(_isolated_identity.MAX_FAILED_ATTEMPTS + 1):
            _isolated_identity.verify_pin("mike", "0000")
        assert _isolated_identity.verify_pin("mike", "8265") is None, "not locked; test is moot"

        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        typed = iter(["4417", "4417"])
        result = first_run.reset_pin(
            input_fn=lambda _p: "RESET", getpass_fn=lambda _p: next(typed)
        )

        assert result.ok is True
        assert _isolated_identity.verify_pin("mike", "4417"), "still locked after a reset"
        assert any("lockout" in d.lower() for d in result.details)

    def test_it_needs_a_keyboard(self, _isolated_identity, monkeypatch):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: False)
        result = first_run.reset_pin()
        assert result.ok is False
        assert "keyboard" in result.message

    def test_no_pin_value_ever_reaches_the_security_log(
        self, _isolated_identity, monkeypatch
    ):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", LEAK_PROBE_PIN)
        monkeypatch.setattr(first_run, "_interactive", lambda stream=None: True)
        typed = iter([LEAK_PROBE_PIN + "-new", LEAK_PROBE_PIN + "-new"])
        first_run.reset_pin(input_fn=lambda _p: "RESET", getpass_fn=lambda _p: next(typed))

        log = _isolated_identity._security_log_path().read_text(encoding="utf-8")
        assert LEAK_PROBE_PIN not in log, "a PIN value reached the security log"
        assert '"reason": "reset"' in log, "the reset was not recorded at all"


class TestSetPin:
    """The model function behind the reset."""

    def test_it_refuses_an_identity_that_does_not_exist(self, _isolated_identity):
        with pytest.raises(_isolated_identity.IdentityError):
            _isolated_identity.set_pin("nobody", "4417")

    def test_it_enforces_the_minimum_length(self, _isolated_identity):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        with pytest.raises(_isolated_identity.IdentityError):
            _isolated_identity.set_pin("mike", "12")
        assert _isolated_identity.verify_pin("mike", "8265"), "the old PIN was disturbed"

    def test_it_stores_a_hash_and_never_the_pin(self, _isolated_identity):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        _isolated_identity.set_pin("mike", LEAK_PROBE_PIN)

        raw = _isolated_identity._identity_path().read_text(encoding="utf-8")
        assert LEAK_PROBE_PIN not in raw, "the PIN was written to disk in plaintext"
        assert "8265" not in raw, "the previous PIN survived the reset"

        # Structural, not just an absence: prove what *is* stored is a real hash that
        # still authenticates. An absence assertion alone would also pass if set_pin
        # had quietly stored nothing at all.
        stored = json.loads(raw)["mike"]["pin_hash"]
        assert stored.startswith("scrypt:")
        assert stored != LEAK_PROBE_PIN
        assert _isolated_identity.verify_pin("mike", LEAK_PROBE_PIN)

    def test_the_returned_record_carries_no_hash(self, _isolated_identity):
        _isolated_identity.bootstrap_authority("mike", "Mike Zachary", "8265")
        record = _isolated_identity.set_pin("mike", "4417")
        assert "pin_hash" not in record
