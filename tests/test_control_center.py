"""Dispatch Control Center v1 — the eight controls, the seven displays, and Reset Session.

These prove software behaviour on Linux. They are not operational proof: nothing
here has run on Mike's Windows machine, and `proof/launcher/LAUNCHER_PROOF.md`
keeps every acceptance item at `UNVERIFIED` until it does.
"""

from __future__ import annotations

import io
import os

import pytest

from dispatch_launcher import cli, control, glyphs, locations, pidfile, probe, settings, status


@pytest.fixture(autouse=True)
def _isolated_launcher(tmp_path, monkeypatch):
    """Point the launcher's own four files at tmp_path, never a real install."""
    monkeypatch.setenv(locations.LOG_DIR_ENV, str(tmp_path / "logs"))
    monkeypatch.delenv(control.REHEARSAL_ENV_VAR, raising=False)
    monkeypatch.delenv(glyphs.GLYPH_ENV, raising=False)
    return tmp_path


@pytest.fixture
def facts():
    return probe.RuntimeFacts(
        version="0.1.0",
        version_source="portal.__version__",
        commit="0" * 40,
        commit_source="git rev-parse HEAD",
        requested_host="127.0.0.1",
        host="127.0.0.1",
        port=8080,
        database_path="/x/portal/data/dispatch.db",
        portal_data_dir="/x/portal/data",
        contract_archive_root="/x/cin_lite/Archive",
        mode="operational",
        probe_ok=True,
    )


# ───────────────────────────────────────────────────── the eight controls


class TestTheEightControls:
    """Section 'Requirements' of the Control Center brief, in the stated order."""

    EXPECTED = (
        ("1", "Start", "start"),
        ("2", "Open Dispatch", "open"),
        ("3", "Refresh Status", "status"),
        ("4", "Settings", "settings"),
        ("5", "Version", "version"),
        ("6", "Restart", "restart"),
        ("7", "Reset Session", "reset-session"),
        ("8", "Stop Dispatch", "stop"),
    )

    def test_all_eight_are_present_in_the_specified_order(self):
        assert [(k, label, action) for k, _g, label, action in cli.MENU_ITEMS] == list(self.EXPECTED)

    def test_every_control_has_its_specified_glyph(self):
        assert [g for _k, g, _l, _a in cli.MENU_ITEMS] == [
            "▶", "\U0001f310", "\U0001f504", "⚙", "ℹ", "↻", "⎌", "■",
        ]

    def test_stop_is_last_and_start_is_first(self):
        """Order is load-bearing: Stop must not sit next to anything routine."""
        assert cli.MENU_ITEMS[0][3] == "start"
        assert cli.MENU_ITEMS[-1][3] == "stop"

    @pytest.mark.parametrize("key,label,action", EXPECTED)
    def test_the_number_selects_the_control(self, key, label, action):
        assert cli.resolve_choice(key) == action

    @pytest.mark.parametrize(
        "typed,action",
        [
            ("start", "start"),
            ("Open Dispatch", "open"),
            ("REFRESH", "status"),
            ("settings", "settings"),
            ("about", "version"),
            ("restart", "restart"),
            ("reset session", "reset-session"),
            ("stop", "stop"),
            ("", "status"),
        ],
    )
    def test_the_word_selects_the_control_too(self, typed, action):
        assert cli.resolve_choice(typed) == action

    def test_an_unknown_choice_resolves_to_nothing(self):
        assert cli.resolve_choice("banana") is None
        assert cli.resolve_choice("9") is None

    def test_every_menu_action_is_dispatchable(self):
        """No menu row can point at an action the loop cannot run."""
        runnable = set(cli._ACTIONS) | {"status", "settings", "version"}
        assert {action for _k, _g, _l, action in cli.MENU_ITEMS} <= runnable

    def test_the_command_line_accepts_every_control(self):
        parser = cli.build_parser()
        for _key, _glyph, _label, action in cli.MENU_ITEMS:
            assert parser.parse_args([action]).action == action


# ───────────────────────────────────────────────────── the seven displays


class TestTheSevenDisplays:
    """Status, Version, Portal URL, Database, Operations, Archive, Memory."""

    def _rendered(self, facts):
        reading = status.LauncherStatus(
            runtime=facts,
            ownership=control.Ownership(control.NO_RECORD, "no record"),
            backup=__import__(
                "dispatch_launcher.backups", fromlist=["backup_status"]
            ).backup_status(None),
        )
        return status.render(reading)

    def test_every_required_display_appears(self, facts):
        facts.operations_root = "D:\\Dispatch Operations"
        facts.archive_root = "D:\\Archive"
        facts.memory_root = "D:\\Memory"
        facts.archive_root_from_env = True
        facts.memory_root_from_env = True
        text = self._rendered(facts)

        assert "Dispatch" in text and "STOPPED" in text          # Status
        assert "0.1.0" in text                                    # Version
        assert "http://127.0.0.1:8080" in text                    # Portal URL
        assert "/x/portal/data/dispatch.db" in text               # Database Path
        assert "D:\\Dispatch Operations" in text                  # Operations Path
        assert "D:\\Archive" in text                              # Archive Path
        assert "D:\\Memory" in text                               # Memory Path

    def test_a_configured_root_is_shown_plainly(self, facts):
        facts.archive_root = "D:\\Archive"
        facts.archive_root_from_env = True
        assert "D:\\Archive  (default" not in self._rendered(facts)

    def test_a_defaulted_root_says_nobody_chose_it(self, facts):
        """The resolver answers with a real path either way. Without this the
        screen shows a defaulted root exactly as it shows a configured one."""
        facts.archive_root = "/x/portal/data"
        facts.archive_root_from_env = False
        text = self._rendered(facts)
        assert "/x/portal/data  (default - DISPATCH_ARCHIVE_ROOT is not set)" in text

    def test_an_unresolvable_root_is_unconfigured(self, facts):
        facts.memory_root = None
        facts.memory_root_from_env = False
        assert "UNCONFIGURED - DISPATCH_MEMORY_ROOT is not set" in self._rendered(facts)

    def test_the_status_screen_never_prints_a_secret_value(self, facts, monkeypatch):
        monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-secret-nobody-should-see")
        facts.weak_secret_names = ["DISPATCH_EMAIL_SECRET"]
        facts.secrets_block_start = True
        text = self._rendered(facts)
        assert "DISPATCH_EMAIL_SECRET" in text
        assert "a-real-secret-nobody-should-see" not in text


# ───────────────────────────────────────────────────── glyphs


class TestGlyphs:
    def test_a_utf8_stream_gets_the_icons(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        assert glyphs.stream_supports(stream) is True
        assert glyphs.prefix(glyphs.START, stream=stream) == "▶ "

    def test_a_legacy_code_page_gets_none_of_them(self):
        """cp437 is what a Windows console still uses when nobody changed it."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp437")
        assert glyphs.stream_supports(stream) is False
        assert glyphs.prefix(glyphs.START, stream=stream) == ""

    def test_cp1252_gets_none_of_them_either(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        assert glyphs.stream_supports(stream) is False

    def test_a_stream_with_no_declared_encoding_is_not_gambled_on(self):
        assert glyphs.stream_supports(io.StringIO()) is False

    def test_a_nonsense_encoding_is_not_a_crash(self):
        class Weird:
            encoding = "definitely-not-a-codec"

        assert glyphs.stream_supports(Weird()) is False

    def test_it_is_all_or_none(self):
        """A menu with icons on three rows and not the other five looks broken,
        and looks-broken is indistinguishable from is-broken to an operator."""
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp437")
        assert not any(glyphs.prefix(g, stream=stream) for g in glyphs.ALL)

    def test_the_environment_can_force_them_off(self, monkeypatch):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        monkeypatch.setenv(glyphs.GLYPH_ENV, "0")
        assert glyphs.enabled(stream) is False

    def test_the_environment_can_force_them_on(self, monkeypatch):
        monkeypatch.setenv(glyphs.GLYPH_ENV, "1")
        assert glyphs.enabled(io.StringIO()) is True

    def test_the_menu_renders_without_icons_when_they_are_off(self, monkeypatch):
        monkeypatch.setenv(glyphs.GLYPH_ENV, "0")
        menu = cli.render_menu()
        assert "[1] Start" in menu
        for glyph in glyphs.ALL:
            assert glyph not in menu

    def test_the_menu_renders_with_icons_when_they_are_on(self, monkeypatch):
        monkeypatch.setenv(glyphs.GLYPH_ENV, "1")
        menu = cli.render_menu()
        for glyph in glyphs.ALL:
            assert glyph in menu

    def test_the_menu_is_encodable_on_a_legacy_console(self, monkeypatch):
        """The whole point: this must not raise UnicodeEncodeError on cp437."""
        monkeypatch.setenv(glyphs.GLYPH_ENV, "0")
        cli.render_menu().encode("cp437")

    def test_every_label_is_ascii_so_only_the_icon_can_ever_be_a_problem(self):
        for _key, _glyph, label, _action in cli.MENU_ITEMS:
            label.encode("ascii")


# ───────────────────────────────────────────────────── settings


class TestSettings:
    def test_it_reports_every_setting_dispatch_consults(self, facts):
        view = settings.collect_settings(facts=facts)
        names = {row.name for row in view.rows}
        assert {
            "PORTAL_SECRET_KEY",
            "DISPATCH_EMAIL_SECRET",
            "DISPATCH_OPERATIONS_ROOT",
            "DISPATCH_ARCHIVE_ROOT",
            "DISPATCH_MEMORY_ROOT",
            "DISPATCH_BACKUP_DIR",
            "PORTAL_HOST",
            "PORTAL_PORT",
            "DISPATCH_MODE",
            "DISPATCH_REHEARSAL_SESSION",
        } <= names

    def test_a_secret_is_named_and_never_shown(self, facts, monkeypatch):
        monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-secret-nobody-should-see")
        facts.weak_secret_names = []
        view = settings.collect_settings(facts=facts)
        text = settings.render_settings(view)
        assert "PORTAL_SECRET_KEY" in text
        assert "set (value not shown)" in text
        assert "a-real-secret-nobody-should-see" not in text

    def test_a_published_default_is_not_called_configured(self, facts):
        """Set to the value anyone reading the source already knows is NOT
        configured, and saying otherwise would be the most dangerous lie here."""
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        view = settings.collect_settings(facts=facts)
        row = next(r for r in view.rows if r.name == "PORTAL_SECRET_KEY")
        assert row.status == settings.UNCONFIGURED

    def test_an_unset_setting_shows_the_fallback_as_a_fallback(self, facts):
        view = settings.collect_settings(facts=facts)
        text = settings.render_settings(view)
        row = next(r for r in view.rows if r.name == "PORTAL_PORT")
        assert row.status == settings.UNCONFIGURED
        assert "without it" in text
        # The fallback is described, never printed in the value column.
        assert row.displayed_value == ""

    def test_the_change_command_is_setx_not_set(self, facts):
        """`set` lasts until the window closes, which produces the most
        confusing possible bug: it works this afternoon and is broken tomorrow."""
        view = settings.collect_settings(facts=facts)
        for row in view.rows:
            assert row.change_command().startswith("setx ")
        assert "only reaches" in settings.render_settings(view)

    def test_it_names_what_is_blocking_a_start(self, facts):
        facts.weak_secret_names = ["PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"]
        facts.secrets_block_start = True
        view = settings.collect_settings(facts=facts)
        assert {r.name for r in view.blocking} == {"PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET"}
        assert "refuse to start" in settings.render_settings(view)

    def test_nothing_blocking_says_so(self, facts):
        facts.weak_secret_names = []
        view = settings.collect_settings(facts=facts)
        assert view.blocking == []
        assert "Nothing in this list is preventing" in settings.render_settings(view)

    def test_a_development_mode_warning_is_not_a_blocker(self, facts):
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        facts.secrets_block_start = False
        view = settings.collect_settings(facts=facts)
        assert view.blocking == []
        assert "Never expose this machine" in settings.render_settings(view)

    def test_it_shows_what_dispatch_actually_resolved(self, facts):
        text = settings.render_settings(settings.collect_settings(facts=facts))
        assert "/x/portal/data/dispatch.db" in text
        assert "http://127.0.0.1:8080" in text

    def test_it_writes_nothing(self, facts, _isolated_launcher):
        before = sorted(p.name for p in _isolated_launcher.rglob("*"))
        settings.render_settings(settings.collect_settings(facts=facts))
        assert sorted(p.name for p in _isolated_launcher.rglob("*")) == before

    def test_the_command_line_exits_non_zero_when_a_setting_blocks_a_start(
        self, monkeypatch, facts, capsys
    ):
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        facts.secrets_block_start = True
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        assert cli.main(["settings"]) == 1
        assert "PORTAL_SECRET_KEY" in capsys.readouterr().out

    def test_the_command_line_exits_zero_when_nothing_blocks(self, monkeypatch, facts):
        facts.weak_secret_names = []
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        assert cli.main(["settings"]) == 0


# ───────────────────────────────────────────────────── version


class TestVersion:
    def test_it_reports_version_and_commit(self, facts):
        view = settings.collect_version(facts=facts)
        assert view.version == "0.1.0"
        assert view.commit == "0" * 40
        assert view.commit in settings.render_version(view)

    def test_an_unknown_commit_is_unverified_and_explained(self, facts):
        facts.commit = probe.UNVERIFIED
        facts.commit_source = "git is not installed"
        text = settings.render_version(settings.collect_version(facts=facts))
        assert probe.UNVERIFIED in text
        assert "git is not installed" in text

    def test_it_reports_the_interpreter_actually_running(self, facts):
        import sys

        view = settings.collect_version(facts=facts)
        assert view.python == ".".join(str(n) for n in sys.version_info[:3])

    def test_a_missing_dependency_is_absent_not_guessed(self, facts):
        view = settings.collect_version(facts=facts)
        installed = dict(view.dependencies)
        assert set(installed) == {"flask", "paramiko", "anthropic"}
        for value in installed.values():
            assert value  # never an empty string standing in for unknown

    def test_it_tells_you_why_the_commit_matters(self, facts):
        assert "proves which code is running" in settings.render_version(
            settings.collect_version(facts=facts)
        )

    def test_the_command_line_exits_zero(self, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        assert cli.main(["version"]) == 0


# ───────────────────────────────────────────────────── reset session


class TestResetSession:
    def _stale_record(self, pid=999999):
        pidfile.write_record(
            pidfile.PidRecord(
                pid=pid,
                recorded_at=pidfile.utc_now(),
                command=["python", "portal/app.py"],
                command_line="python portal/app.py",
                created_token="not-a-real-token",
                host="127.0.0.1",
                port=8080,
            )
        )

    def test_a_clean_session_needs_no_reset(self, facts):
        result = control.reset_session(facts=facts)
        assert result.ok is True
        assert "already clean" in result.message

    def test_it_clears_a_stale_process_record(self, facts):
        self._stale_record()
        assert locations.pid_file().exists()

        result = control.reset_session(facts=facts)

        assert result.ok is True
        assert not locations.pid_file().exists()
        assert any("stale process record" in d for d in result.details)

    def test_it_clears_a_recorded_failure(self, facts):
        control.write_failure("start", "port 8080 is already in use")
        assert control.read_failure() is not None

        result = control.reset_session(facts=facts)

        assert control.read_failure() is None
        assert any("last start failure" in d for d in result.details)

    def test_it_clears_the_rehearsal_binding(self, facts, monkeypatch):
        """Otherwise a Start after a rehearsal keeps silently tagging every
        record REHEARSAL because a variable was left set in this window."""
        monkeypatch.setenv(control.REHEARSAL_ENV_VAR, "REH-20260824-ABCDEF01")

        result = control.reset_session(facts=facts)

        assert os.environ.get(control.REHEARSAL_ENV_VAR) is None
        assert any("REH-20260824-ABCDEF01" in d for d in result.details)
        assert any("record live data" in d for d in result.details)

    def test_it_refuses_while_dispatch_is_running(self, facts, monkeypatch):
        """Clearing the record of a live server is exactly how an orphan is
        made: still holding the port, no longer stoppable from here."""
        monkeypatch.setattr(
            control,
            "inspect_pidfile",
            lambda *a, **k: control.Ownership(
                control.RUNNING, "running", record=pidfile.PidRecord(pid=4321, recorded_at="", command=[])
            ),
        )
        self._stale_record()

        result = control.reset_session(facts=facts)

        assert result.ok is False
        assert "4321" in result.message
        assert "Nothing was reset" in result.message
        assert any("orphaned" in d for d in result.details)
        assert locations.pid_file().exists()

    def test_it_refuses_when_a_live_process_cannot_be_identified(self, facts, monkeypatch):
        monkeypatch.setattr(
            control,
            "inspect_pidfile",
            lambda *a, **k: control.Ownership(
                control.UNCONFIRMED,
                "a process is alive but Windows would not confirm what it is",
                record=pidfile.PidRecord(pid=555, recorded_at="", command=[]),
            ),
        )
        self._stale_record()

        result = control.reset_session(facts=facts)

        assert result.ok is False
        assert locations.pid_file().exists()

    def test_it_never_claims_to_have_touched_operational_data(self, facts):
        result = control.reset_session(facts=facts)
        assert any("No load, milestone, driver, evidence file" in d for d in result.details)

    def test_it_has_no_path_to_operational_data(self):
        """A reset must not be able to delete freight even by accident. The
        launcher-wide import boundary is what guarantees it; this pins the
        specific promise the reset screen makes to the operator."""
        import inspect

        source = inspect.getsource(control.reset_session)
        for forbidden in ("dispatch.services", "dispatch.store", "dispatch.spine", "sqlite3"):
            assert forbidden not in source

    def test_the_rehearsal_variable_name_matches_the_application(self):
        """The launcher may not import dispatch.*, so the name is duplicated as
        a literal. This pins the two spellings together so a rename in the
        application cannot silently stop Reset Session from clearing it."""
        from dispatch import rehearsal

        assert control.REHEARSAL_ENV_VAR == rehearsal.REHEARSAL_ENV_VAR

    def test_the_command_line_reports_the_refusal_with_a_non_zero_exit(
        self, facts, monkeypatch, capsys
    ):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        monkeypatch.setattr(
            control,
            "inspect_pidfile",
            lambda *a, **k: control.Ownership(
                control.RUNNING, "running", record=pidfile.PidRecord(pid=4321, recorded_at="", command=[])
            ),
        )
        assert cli.main(["reset-session"]) == 1
        assert "Stop Dispatch first" in capsys.readouterr().out


# ───────────────────────────────────────────────────── the loop


class TestTheMenuLoop:
    def test_settings_is_reachable_from_the_menu(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["4", "q"])
        cli.run_menu(input_fn=lambda _p: next(answers))
        assert "DISPATCH - Settings" in capsys.readouterr().out

    def test_version_is_reachable_from_the_menu(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["5", "q"])
        cli.run_menu(input_fn=lambda _p: next(answers))
        assert "DISPATCH - Version" in capsys.readouterr().out

    def test_reset_session_is_reachable_from_the_menu(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["7", "q"])
        cli.run_menu(input_fn=lambda _p: next(answers))
        assert "session" in capsys.readouterr().out.lower()

    def test_a_read_only_view_does_not_reprint_the_status(self, capsys, monkeypatch, facts):
        """Settings and Version observe; only a control that changed something
        earns a fresh status reading afterwards."""
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["5", "q"])
        cli.run_menu(input_fn=lambda _p: next(answers))
        assert capsys.readouterr().out.count("DISPATCH - Operations Control") == 1

    def test_refresh_status_reprints_the_status(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["3", "q"])
        cli.run_menu(input_fn=lambda _p: next(answers))
        assert capsys.readouterr().out.count("DISPATCH - Operations Control") == 2


# ───────────────────────────────────────────────────── the Windows wrappers


class TestTheWindowsWrappers:
    def _read(self, name):
        return (locations.repo_root() / name).read_bytes().decode("utf-8")

    def test_the_batch_file_asks_for_utf8_so_the_icons_can_render(self):
        assert "chcp 65001" in self._read("dispatch.bat")

    def test_the_batch_file_redirects_the_windows_way(self):
        """`>/dev/null` in cmd redirects to a path that does not exist, prints an
        error, and sets ERRORLEVEL -- so the `||` branch fires every time."""
        text = self._read("dispatch.bat")
        assert "/dev/null" not in text
        assert ">nul" in text

    def test_the_powershell_wrapper_sets_utf8_without_being_able_to_fail(self):
        text = self._read("Dispatch.ps1")
        assert "OutputEncoding" in text
        assert "catch { }" in text

    def test_both_wrappers_still_hold_no_logic(self):
        """A script in this repository cannot be tested, so it is not allowed to
        decide anything. Both must only locate an interpreter and delegate."""
        for name in ("dispatch.bat", "Dispatch.ps1"):
            text = self._read(name).lower()
            for verb in ("taskkill", "stop-process", "get-process", "netstat"):
                assert verb not in text
