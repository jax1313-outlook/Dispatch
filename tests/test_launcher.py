"""Tests for the Dispatch Launcher (Operational Readiness Mission, Section 3).

What these tests are and are not: they are evidence of *software behaviour* on
this Linux test runner. They are not operational proof. Nothing here says the
launcher works on Mike's Windows machine -- that claim lives in
proof/launcher/LAUNCHER_PROOF.md and is UNVERIFIED until he runs it there.

The process-safety tests deliberately drive real operating-system processes
rather than mocks. A test that asserts "stop() called terminate()" proves nothing
about whether the server is gone, which is the only property that matters. So a
stand-in server process is really spawned, really bound to a real port, really
signalled, and really polled until the operating system stops reporting it. The
stand-in binds a socket and sleeps instead of being a Flask app only because a
real portal start-up would add seconds to every test without changing what is
being proved: the launcher's contract is with the *process*, not with Flask.

Mocks are used for exactly two things: the Windows-only code paths, which cannot
run here at all and are tested through their parsers with recorded output, and
the "the process refuses to die" branch, which cannot be produced reliably from a
test on any platform.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from dispatch_launcher import (
    backups,
    cli,
    control,
    locations,
    pidfile,
    probe,
    processes,
    redaction,
    status as status_module,
)
from dispatch_launcher.pidfile import PidRecord
from dispatch_launcher.probe import RuntimeFacts

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Captured before the sandbox fixture below replaces it. This test runner is a
#: shared container that may hold unrelated processes whose command lines happen
#: to match, so enumeration is neutralised by default and re-enabled only in the
#: one test that is actually about discovery.
_REAL_ENUMERATION = processes.find_portal_processes

#: A stand-in for the portal server: binds the port the launcher is watching,
#: then stays alive until it is signalled. Everything the launcher asserts about
#: a running server -- it exists, it holds the port, it goes away when stopped --
#: is true of this process, which is the whole point.
_STAND_IN_SERVER = textwrap.dedent(
    """
    import socket
    import sys
    import time

    host, port = sys.argv[1], int(sys.argv[2])
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((host, port))
    listener.listen(8)
    while True:
        time.sleep(0.25)
    """
)

#: A stand-in that fails the way a real portal fails when the port is taken.
_FAILING_SERVER = textwrap.dedent(
    """
    import sys

    sys.stderr.write(
        "Traceback (most recent call last):\\n"
        "  File \\"portal/app.py\\", line 1, in <module>\\n"
        "    app.run(host=host, port=port)\\n"
        "OSError: [Errno 98] Address already in use\\n"
    )
    sys.exit(1)
    """
)


# ── fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def launcher_sandbox(tmp_path, monkeypatch):
    """Point every launcher-owned path at tmp_path.

    The launcher's real log directory is the operator's; a test that wrote a PID
    file into it could make a live install believe a server was running.
    """
    log_dir = tmp_path / "launcher-logs"
    monkeypatch.setenv(locations.LOG_DIR_ENV, str(log_dir))
    for name in ("PORTAL_HOST", "PORTAL_PORT", "DISPATCH_MODE", "DISPATCH_BACKUP_DIR"):
        monkeypatch.delenv(name, raising=False)
    # Default to "no unclaimed processes". The real enumeration is a property of
    # whatever else happens to be running on the machine running the tests, which
    # would make every unrelated assertion depend on it.
    monkeypatch.setattr(processes, "find_portal_processes", lambda **kwargs: [])
    return log_dir


@pytest.fixture
def reap():
    """Kill anything a test spawned, however the test ended."""
    spawned: list[int] = []

    def _track(pid: int | None) -> int | None:
        if pid is not None:
            spawned.append(pid)
        return pid

    yield _track

    for pid in spawned:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


@pytest.fixture
def free_port() -> int:
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return int(probe_socket.getsockname()[1])


@pytest.fixture
def stand_in(tmp_path, monkeypatch, free_port):
    """Make control.start() launch the stand-in server instead of the portal."""
    script = tmp_path / "stand_in_server.py"
    script.write_text(_STAND_IN_SERVER, encoding="utf-8")
    monkeypatch.setattr(
        control,
        "_spawn_command",
        lambda: [sys.executable, str(script), "127.0.0.1", str(free_port)],
    )
    return script


@pytest.fixture
def facts(free_port) -> RuntimeFacts:
    """Runtime facts with a real free port, so start() does real port checks."""
    return RuntimeFacts(
        version="0.1.0",
        version_source="portal.__version__",
        commit="0" * 40,
        commit_source="git rev-parse HEAD",
        requested_host="127.0.0.1",
        host="127.0.0.1",
        port=free_port,
        database_path="/nowhere/dispatch.db",
        portal_data_dir="/nowhere",
        mode="operational",
        weak_secret_names=[],
        secrets_block_start=False,
        probe_ok=True,
    )


def _dead_pid() -> int:
    """A PID that is certainly not running: one we watched exit."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=30)
    pid = child.pid
    deadline = time.monotonic() + 5
    while processes.pid_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    return pid


# ── Section 3.3: displays come from the real configuration ─────────────

class TestStatusReadsRealConfiguration:
    def test_probe_reports_the_database_the_application_resolves(self):
        from dispatch.db import get_db_path

        collected = probe.collect()

        assert collected["database_path"] == str(Path(get_db_path()).resolve())

    def test_probe_reports_the_address_the_application_resolves(self):
        from portal.config import Config, development_host

        collected = probe.collect()

        assert collected["port"] == int(Config.PORT)
        assert collected["host"] == development_host(Config.HOST)

    def test_subprocess_probe_sees_a_changed_port(self, monkeypatch):
        """Nothing is cached or hard-coded: change the setting, the reading moves."""
        monkeypatch.setenv("PORTAL_PORT", "8391")

        assert probe.probe_runtime().port == 8391

    def test_subprocess_probe_reports_development_host_pinning(self, monkeypatch):
        monkeypatch.setenv("PORTAL_HOST", "0.0.0.0")
        monkeypatch.setenv("DISPATCH_MODE", "development")

        reading = probe.probe_runtime()

        assert reading.requested_host == "0.0.0.0"
        assert reading.host == "127.0.0.1"
        assert reading.host_pinned is True
        assert reading.mode == "development"

    def test_operational_mode_is_the_default_reading(self, monkeypatch):
        monkeypatch.delenv("DISPATCH_MODE", raising=False)

        assert probe.probe_runtime().mode == "operational"

    def test_version_and_commit_are_read_not_assumed(self):
        import portal

        collected = probe.collect()

        assert collected["version"] == portal.__version__
        assert collected["commit"] == probe.UNVERIFIED or len(collected["commit"]) == 40

    def test_missing_git_degrades_to_unverified(self, monkeypatch):
        monkeypatch.setattr(
            probe.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("git")),
        )

        commit, source = probe._git_commit(REPO_ROOT)

        assert commit == probe.UNVERIFIED
        assert "not available" in source

    def test_probe_failure_degrades_instead_of_raising(self, monkeypatch):
        monkeypatch.setattr(
            probe.subprocess, "run",
            lambda *a, **k: (_ for _ in ()).throw(OSError("no interpreter")),
        )

        reading = probe.probe_runtime()

        assert reading.probe_ok is False
        assert reading.errors
        assert reading.url == probe.UNVERIFIED

    def test_status_renders_every_required_display(self, facts):
        reading = status_module.collect_status(facts=facts)

        rendered = status_module.render(reading)

        for required in (
            "Dispatch", "Version", "Commit", "Portal address", "Mode",
            "Security settings", "Database", "Operations root", "Archive root",
            "Memory root", "Backup", "Logs", "Last start failure",
        ):
            assert required in rendered

    def test_status_shows_the_process_id_when_running(self, facts, stand_in, reap):
        result = control.start(facts=facts)
        reap(result.pid)

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "RUNNING" in rendered
        assert f"process ID {result.pid}" in rendered

    def test_status_output_is_ascii_so_a_windows_console_can_print_it(self, facts):
        rendered = status_module.render(status_module.collect_status(facts=facts))

        rendered.encode("ascii")  # raises UnicodeEncodeError if it is not


# ── Section 3.3: secrets are named, never shown ────────────────────────

class TestSecretsAreNamedNeverShown:
    def test_status_names_the_setting_and_not_its_value(self, facts):
        from portal.config import _PUBLISHED_DEFAULTS

        published_value = _PUBLISHED_DEFAULTS["PORTAL_SECRET_KEY"]
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        facts.secrets_block_start = True

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "PORTAL_SECRET_KEY" in rendered
        assert published_value not in rendered
        assert "refuse to start" in rendered

    def test_development_mode_reports_the_same_names_without_claiming_a_block(self, facts):
        facts.weak_secret_names = ["DISPATCH_EMAIL_SECRET"]
        facts.secrets_block_start = False
        facts.mode = "development"

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "DISPATCH_EMAIL_SECRET" in rendered
        assert "refuse to start" not in rendered

    def test_probe_collects_names_from_the_applications_own_table(self, monkeypatch):
        from portal.config import _PUBLISHED_DEFAULTS

        for name, published in _PUBLISHED_DEFAULTS.items():
            monkeypatch.setenv(name, published)

        collected = probe.collect()

        assert collected["weak_secret_names"] == sorted(_PUBLISHED_DEFAULTS)
        for value in _PUBLISHED_DEFAULTS.values():
            assert value not in json.dumps(collected)

    def test_start_refuses_and_names_the_setting_when_secrets_would_block(self, facts):
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        facts.secrets_block_start = True

        result = control.start(facts=facts)

        assert result.ok is False
        assert "PORTAL_SECRET_KEY" in result.message
        assert "not set" in result.message
        assert pidfile.read_record() is None


class TestRedaction:
    @pytest.mark.parametrize(
        "line, secret",
        [
            ("PORTAL_SECRET_KEY=hunter2-live", "hunter2-live"),
            ("DISPATCH_EMAIL_SECRET: s3cr3t-email", "s3cr3t-email"),
            ('"PORTAL_SECRET_KEY": "abc123xyz"', "abc123xyz"),
            ("http://host/api/decision/1/approve?token=9f8e7d6c", "9f8e7d6c"),
            ("DISPATCH_PIN=481516", "481516"),
            ("SMTP_PASSWORD=correct-horse", "correct-horse"),
        ],
    )
    def test_secret_values_are_removed_and_names_are_kept(self, line, secret):
        redacted = redaction.redact_text(line)

        assert secret not in redacted
        assert redaction.REDACTED in redacted
        assert line.split("=")[0].split(":")[0].strip() in redacted

    def test_ordinary_settings_are_left_alone(self):
        assert redaction.redact_text("PORTAL_PORT=8080") == "PORTAL_PORT=8080"
        assert redaction.redact_text("DISPATCH_MODE=operational") == "DISPATCH_MODE=operational"

    def test_mapping_keeps_names_and_drops_credential_values(self):
        redacted = redaction.redact_mapping({
            "PORTAL_SECRET_KEY": "live-key",
            "DISPATCH_OPERATIONS_ROOT": r"D:\Dispatch Operations",
        })

        assert redacted["PORTAL_SECRET_KEY"] == redaction.REDACTED
        assert redacted["DISPATCH_OPERATIONS_ROOT"] == r"D:\Dispatch Operations"

    def test_the_launcher_log_is_written_redacted(self):
        control.log_action("starting with PORTAL_SECRET_KEY=never-write-this")

        written = locations.launcher_log().read_text(encoding="utf-8")

        assert "never-write-this" not in written
        assert "PORTAL_SECRET_KEY" in written

    def test_a_real_start_does_not_write_a_secret_into_the_launcher_log(
        self, facts, stand_in, reap, monkeypatch,
    ):
        monkeypatch.setenv("PORTAL_SECRET_KEY", "do-not-log-this-value")

        result = control.start(facts=facts)
        reap(result.pid)

        written = locations.launcher_log().read_text(encoding="utf-8")
        assert "do-not-log-this-value" not in written
        assert "PORTAL_SECRET_KEY" in written

    def test_the_server_log_is_redacted_on_the_way_out(self):
        locations.ensure_logs_dir()
        locations.server_log().write_text(
            "DISPATCH_EMAIL_SECRET=leaked-value\nlistening on 8080\n", encoding="utf-8",
        )

        tail = control.read_log_tail()

        assert "leaked-value" not in tail
        assert "listening on 8080" in tail


# ── Section 3.4: the PID file and what it proves ───────────────────────

class TestPidFileLifecycle:
    def test_a_record_round_trips(self):
        record = PidRecord(
            pid=4242, recorded_at=pidfile.utc_now(), command=["python", "app.py"],
            command_line="python app.py", created_token="9911",
            host="127.0.0.1", port=8080, log_path="/logs/x.log",
        )

        pidfile.write_record(record)

        assert pidfile.read_record() == record

    def test_a_missing_file_reads_as_no_record(self):
        assert pidfile.read_record() is None

    def test_an_unreadable_file_reads_as_no_record(self):
        locations.ensure_logs_dir()
        locations.pid_file().write_text("{not json", encoding="utf-8")

        assert pidfile.read_record() is None
        assert control.inspect_pidfile().state == control.NO_RECORD

    def test_a_record_without_a_pid_reads_as_no_record(self):
        locations.ensure_logs_dir()
        locations.pid_file().write_text('{"host": "127.0.0.1"}', encoding="utf-8")

        assert pidfile.read_record() is None

    def test_clearing_reports_whether_anything_was_there(self):
        pidfile.write_record(PidRecord(pid=1, recorded_at="", command=[]))

        assert pidfile.clear_record() is True
        assert pidfile.clear_record() is False

    def test_start_records_the_identity_it_will_later_check(self, facts, stand_in, reap):
        result = control.start(facts=facts)
        reap(result.pid)

        record = pidfile.read_record()
        assert record is not None
        assert record.pid == result.pid
        assert record.port == facts.port
        # The two facts that make the PID checkable later.
        assert record.command_line
        assert record.created_token

    def test_stop_removes_the_record(self, facts, stand_in, reap):
        result = control.start(facts=facts)
        reap(result.pid)

        control.stop()

        assert pidfile.read_record() is None


class TestOwnershipIsProvenNotAssumed:
    def test_a_live_process_with_matching_identity_is_ours(self, reap):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        reap(child.pid)
        observed = processes.process_facts(child.pid)
        pidfile.write_record(PidRecord(
            pid=child.pid, recorded_at=pidfile.utc_now(), command=[],
            command_line=observed.command_line, created_token=observed.created_token,
        ))

        ownership = control.inspect_pidfile()

        assert ownership.state == control.RUNNING
        assert ownership.pid == child.pid

    def test_a_recycled_pid_is_stale_not_ours(self):
        """The PID is alive, but it is a different program than the one recorded."""
        pidfile.write_record(PidRecord(
            pid=os.getpid(), recorded_at=pidfile.utc_now(), command=[],
            command_line="python portal/app.py", created_token="0",
        ))

        ownership = control.inspect_pidfile()

        assert ownership.state == control.STALE_FOREIGN
        assert "reuses process IDs" in ownership.explanation

    def test_a_dead_pid_is_reported_as_a_crash_leftover(self):
        pidfile.write_record(PidRecord(
            pid=_dead_pid(), recorded_at=pidfile.utc_now(), command=[],
            command_line="python portal/app.py", created_token="1",
        ))

        ownership = control.inspect_pidfile()

        assert ownership.state == control.STALE_DEAD
        assert "no longer running" in ownership.explanation

    def test_an_unidentifiable_live_process_is_never_assumed_to_be_ours(self, reap):
        """No recorded identity means no claim -- and no action."""
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        reap(child.pid)
        pidfile.write_record(PidRecord(
            pid=child.pid, recorded_at=pidfile.utc_now(), command=[],
            command_line=None, created_token=None,
        ))

        ownership = control.inspect_pidfile()

        assert ownership.state == control.UNCONFIRMED
        assert ownership.running is False


# ── Section 3.4: start creates exactly one server ──────────────────────

class TestStartCreatesExactlyOneServer:
    def test_start_launches_a_process_and_reports_the_address(self, facts, stand_in, reap):
        result = control.start(facts=facts)
        reap(result.pid)

        assert result.ok is True
        assert result.pid is not None
        assert processes.pid_alive(result.pid)
        assert f"http://127.0.0.1:{facts.port}" in result.message

    def test_a_second_start_does_nothing_but_report(self, facts, stand_in, reap):
        first = control.start(facts=facts)
        reap(first.pid)

        second = control.start(facts=facts)

        assert second.ok is True
        assert second.pid == first.pid
        assert "already running" in second.message
        assert pidfile.read_record().pid == first.pid

    def test_a_second_start_spawns_no_process(self, facts, stand_in, reap, monkeypatch):
        first = control.start(facts=facts)
        reap(first.pid)

        def _forbidden(*args, **kwargs):
            raise AssertionError("start spawned a second server process")

        monkeypatch.setattr(control.subprocess, "Popen", _forbidden)
        control.start(facts=facts)

    def test_start_refuses_when_the_port_is_already_taken(self, facts, stand_in):
        with socket.socket() as squatter:
            squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            squatter.bind(("127.0.0.1", facts.port))
            squatter.listen(1)

            result = control.start(facts=facts)

        assert result.ok is False
        assert f"port {facts.port} is already in use" in result.message
        assert "Traceback" not in result.message

    def test_start_refuses_to_act_on_an_unidentifiable_process(self, facts, stand_in, reap):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        reap(child.pid)
        pidfile.write_record(PidRecord(
            pid=child.pid, recorded_at=pidfile.utc_now(), command=[],
            command_line=None, created_token=None,
        ))

        result = control.start(facts=facts)

        assert result.ok is False
        assert "cannot tell whether it is already running" in result.message
        assert any("Task Manager" in detail for detail in result.details)

    def test_start_clears_a_stale_record_and_says_so(self, facts, stand_in, reap):
        pidfile.write_record(PidRecord(
            pid=_dead_pid(), recorded_at=pidfile.utc_now(), command=[],
            command_line="python portal/app.py", created_token="1",
        ))

        result = control.start(facts=facts)
        reap(result.pid)

        assert result.ok is True
        assert any("stale record was cleared" in detail for detail in result.details)


# ── Section 3.4: stop confirms the process is gone ─────────────────────

class TestStopConfirmsTheProcessIsGone:
    def test_stop_terminates_the_real_process(self, facts, stand_in, reap):
        started = control.start(facts=facts)
        reap(started.pid)

        result = control.stop()

        assert result.ok is True
        assert processes.pid_alive(started.pid) is False
        assert f"Process ID {started.pid} is gone" in result.message

    def test_stop_frees_the_port(self, facts, stand_in, reap):
        started = control.start(facts=facts)
        reap(started.pid)
        assert processes.port_in_use("127.0.0.1", facts.port)

        control.stop()

        assert processes.wait_until_gone(started.pid, 5)
        assert processes.port_in_use("127.0.0.1", facts.port) is False

    def test_an_exited_child_is_not_reported_as_still_running(self, reap):
        """The zombie trap, which is the failure mode of a naive PID check.

        A child that has exited but has not been collected by its parent stays
        in the process table. `os.kill(pid, 0)` succeeds against it and
        `/proc/<pid>` still exists, so a launcher that equates "the PID resolves"
        with "the server is running" tells the operator a stop failed when it
        worked, and refuses to restart. That is a live risk here because the menu
        process is the server's parent and stays open.
        """
        child = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(0)"])
        reap(child.pid)
        deadline = time.monotonic() + 5
        while processes.pid_alive(child.pid) and time.monotonic() < deadline:
            time.sleep(0.05)

        assert processes.pid_alive(child.pid) is False
        assert processes.process_facts(child.pid).alive is False

    def test_stop_when_nothing_is_running_is_not_an_error(self):
        result = control.stop()

        assert result.ok is True
        assert "not running" in result.message

    def test_stop_reports_a_process_that_will_not_die_and_what_to_do(
        self, facts, stand_in, reap, monkeypatch,
    ):
        started = control.start(facts=facts)
        reap(started.pid)
        monkeypatch.setattr(processes, "terminate", lambda pid, force=False: True)
        monkeypatch.setattr(processes, "wait_until_gone", lambda pid, timeout, **k: False)

        result = control.stop()

        assert result.ok is False
        assert "did not stop" in result.message
        assert any("Task Manager" in detail for detail in result.details)
        assert any("can corrupt it" in detail for detail in result.details)
        # The record is deliberately NOT cleared: the server is still running.
        assert pidfile.read_record() is not None

    def test_stop_escalates_once_and_reports_that_it_did(
        self, facts, stand_in, reap, monkeypatch,
    ):
        started = control.start(facts=facts)
        reap(started.pid)
        forced: list[bool] = []
        real_terminate = processes.terminate

        def _record(pid, force=False):
            forced.append(force)
            return real_terminate(pid, force=force) if force else True

        monkeypatch.setattr(processes, "terminate", _record)
        result = control.stop(timeout=0.5, force_timeout=5)

        assert forced == [False, True]
        assert result.ok is True
        assert "had to be forced" in result.message

    def test_stop_leaves_an_unidentifiable_process_alone(self, reap):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        reap(child.pid)
        pidfile.write_record(PidRecord(
            pid=child.pid, recorded_at=pidfile.utc_now(), command=[],
            command_line=None, created_token=None,
        ))

        result = control.stop()

        assert result.ok is False
        assert processes.pid_alive(child.pid) is True

    def test_stop_leaves_a_recycled_pid_alone_and_clears_the_record(self):
        pidfile.write_record(PidRecord(
            pid=os.getpid(), recorded_at=pidfile.utc_now(), command=[],
            command_line="python portal/app.py", created_token="0",
        ))

        result = control.stop()

        assert result.ok is True
        assert "left alone" in result.message
        assert pidfile.read_record() is None


# ── Section 3.4: restart proves the first process died ─────────────────

class TestRestartOrdering:
    def test_restart_kills_the_old_process_before_the_new_one_exists(
        self, facts, stand_in, reap,
    ):
        first = control.start(facts=facts)
        reap(first.pid)

        result = control.restart(facts=facts)
        reap(result.pid)

        assert result.ok is True
        assert processes.pid_alive(first.pid) is False
        assert result.pid != first.pid
        assert processes.pid_alive(result.pid) is True

    def test_restart_starts_nothing_when_stop_fails(self, facts, stand_in, monkeypatch):
        monkeypatch.setattr(
            control, "stop",
            lambda **kwargs: control.ControlResult(
                action="stop", ok=False, message="Dispatch did not stop.", pid=999,
            ),
        )

        def _forbidden(**kwargs):
            raise AssertionError("restart started a second server after a failed stop")

        monkeypatch.setattr(control, "start", _forbidden)

        result = control.restart(facts=facts)

        assert result.ok is False
        assert "Nothing new was started" in result.message

    def test_restart_starts_nothing_when_the_old_process_is_still_alive(
        self, facts, stand_in, reap, monkeypatch,
    ):
        """Even a stop that reports success is re-checked against the OS."""
        first = control.start(facts=facts)
        reap(first.pid)
        monkeypatch.setattr(
            control, "stop",
            lambda **kwargs: control.ControlResult(action="stop", ok=True, message="stopped"),
        )

        def _forbidden(**kwargs):
            raise AssertionError("restart started a second server while the first lived")

        monkeypatch.setattr(control, "start", _forbidden)

        result = control.restart(facts=facts)

        assert result.ok is False
        assert f"process ID {first.pid} is still running" in result.message
        assert processes.pid_alive(first.pid) is True

    def test_restart_from_stopped_just_starts(self, facts, stand_in, reap):
        result = control.restart(facts=facts)
        reap(result.pid)

        assert result.ok is True
        assert "Dispatch was not running." in result.message


# ── Section 3.4: orphans are found, not overwritten ────────────────────

class TestOrphanDetection:
    def test_a_portal_looking_process_is_discovered(self, reap):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)", "portal", "app.py"],
        )
        reap(child.pid)
        time.sleep(0.2)

        found = _REAL_ENUMERATION()

        assert found is not None
        assert child.pid in [facts.pid for facts in found]

    def test_unavailable_enumeration_is_not_reported_as_none_found(self, monkeypatch):
        monkeypatch.setattr(processes, "_posix_portal_processes", lambda exclude: None)

        assert _REAL_ENUMERATION() is None

    def test_start_names_the_orphan_holding_the_port(self, facts, stand_in, monkeypatch):
        orphan = processes.ProcessFacts(
            pid=31337, alive=True, command_line="python portal/app.py", source="proc",
        )
        monkeypatch.setattr(processes, "find_portal_processes", lambda **k: [orphan])

        with socket.socket() as squatter:
            squatter.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            squatter.bind(("127.0.0.1", facts.port))
            squatter.listen(1)

            result = control.start(facts=facts)

        assert result.ok is False
        assert any("process ID 31337" in detail for detail in result.details)
        assert any("previous session" in detail for detail in result.details)

    def test_stop_will_not_kill_an_orphan_it_cannot_prove_it_owns(self, monkeypatch):
        orphan = processes.ProcessFacts(
            pid=31337, alive=True, command_line="python portal/app.py", source="proc",
        )
        monkeypatch.setattr(processes, "find_portal_processes", lambda **k: [orphan])

        result = control.stop()

        assert result.ok is False
        assert "did not start" in result.message
        assert any("will not terminate a process it cannot prove it owns" in d
                   for d in result.details)

    def test_status_reports_an_unclaimed_process(self, facts, monkeypatch):
        orphan = processes.ProcessFacts(
            pid=31337, alive=True, command_line="python portal/app.py", source="proc",
        )
        monkeypatch.setattr(processes, "find_portal_processes", lambda **k: [orphan])
        pidfile.write_record(PidRecord(
            pid=_dead_pid(), recorded_at=pidfile.utc_now(), command=[],
            command_line="python portal/app.py", created_token="1",
        ))

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "Unclaimed process" in rendered
        assert "31337" in rendered


# ── Section 3.3: failures in plain language, traces in the log ─────────

class TestPlainLanguageFailures:
    @pytest.mark.parametrize(
        "log_text, expected",
        [
            ("OSError: [Errno 98] Address already in use", "already in use"),
            ("OSError: [WinError 10048] Only one usage of each socket address", "already in use"),
            ("ModuleNotFoundError: No module named 'flask'", "Flask package is not installed"),
            ("PermissionError: [WinError 5] Access is denied", "refused permission"),
            ("sqlite3.OperationalError: database is locked", "locked by another program"),
        ],
    )
    def test_known_causes_become_a_sentence(self, log_text, expected, facts):
        message = control.describe_failure(log_text, facts, exit_code=1)

        assert expected in message
        assert "Traceback" not in message

    def test_a_missing_secret_names_the_setting_not_the_value(self, facts):
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        log_text = (
            "portal.config.InsecureConfigurationError: Refusing to start: "
            "PORTAL_SECRET_KEY is unset"
        )

        message = control.describe_failure(log_text, facts, exit_code=1)

        assert "PORTAL_SECRET_KEY" in message
        assert "dev-portal-key-change-in-production" not in message

    def test_an_unknown_cause_points_at_the_log_instead_of_guessing(self, facts):
        message = control.describe_failure("ZeroDivisionError: division by zero", facts, exit_code=7)

        assert "does not recognise the reason" in message
        assert str(locations.server_log()) in message
        assert "exited with code 7" in message

    def test_a_real_failed_start_reports_plainly_and_keeps_the_trace_in_the_log(
        self, facts, tmp_path, monkeypatch,
    ):
        script = tmp_path / "failing_server.py"
        script.write_text(_FAILING_SERVER, encoding="utf-8")
        monkeypatch.setattr(control, "_spawn_command", lambda: [sys.executable, str(script)])

        result = control.start(facts=facts)

        assert result.ok is False
        assert f"port {facts.port} is already in use" in result.message
        assert "Traceback" not in result.message
        assert "Traceback" in locations.server_log().read_text(encoding="utf-8")
        assert pidfile.read_record() is None

    def test_the_failure_is_recorded_and_shown_in_status(self, facts, tmp_path, monkeypatch):
        script = tmp_path / "failing_server.py"
        script.write_text(_FAILING_SERVER, encoding="utf-8")
        monkeypatch.setattr(control, "_spawn_command", lambda: [sys.executable, str(script)])
        control.start(facts=facts)

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "Last start failure" in rendered
        assert "already in use" in rendered

    def test_a_successful_start_clears_the_previous_failure(self, facts, stand_in, reap):
        control.write_failure("start", "Dispatch could not start because port 1 is in use.")

        result = control.start(facts=facts)
        reap(result.pid)

        assert control.read_failure() is None

    def test_no_failure_recorded_reads_as_absent(self, facts):
        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "ABSENT - no failure recorded" in rendered


# ── Section 3.3: backup honesty ────────────────────────────────────────

class TestBackupStatusHonesty:
    def test_no_configured_location_is_unconfigured_not_missing(self):
        result = backups.backup_status(None)

        assert result.state == backups.UNCONFIGURED
        assert "DISPATCH_BACKUP_DIR" in result.detail

    def test_a_configured_location_that_does_not_exist_is_absent(self, tmp_path):
        result = backups.backup_status(tmp_path / "nowhere")

        assert result.state == backups.ABSENT

    def test_an_empty_location_is_absent_and_says_how_to_fix_it(self, tmp_path):
        result = backups.backup_status(tmp_path)

        assert result.state == backups.ABSENT
        assert "dispatch_backup.py" in result.detail

    def test_a_backup_with_no_restore_record_is_unverified(self, tmp_path):
        archive = tmp_path / "dispatch-backup-20260820T020000Z"
        archive.mkdir()
        (archive / "manifest.json").write_text(
            json.dumps({"created_at": "2026-08-20T02:00:00Z"}), encoding="utf-8",
        )

        result = backups.backup_status(tmp_path)

        assert result.state == backups.UNVERIFIED
        assert result.created_at == "2026-08-20T02:00:00Z"
        assert result.created_at_source == "manifest"
        assert "never been restored" in result.detail

    def test_a_manifest_alone_is_never_treated_as_proof_of_a_good_backup(self, tmp_path):
        """A manifest proves what was copied, not that it can be restored."""
        archive = tmp_path / "dispatch-backup-20260820T020000Z"
        archive.mkdir()
        (archive / "manifest.json").write_text(
            json.dumps({
                "created_at": "2026-08-20T02:00:00Z",
                "files": [{"path": "a", "sha256": "x"}],
            }),
            encoding="utf-8",
        )

        result = backups.backup_status(tmp_path)

        assert result.state != backups.VERIFIED

    def test_a_restore_verification_record_inside_the_archive_is_accepted(self, tmp_path):
        archive = tmp_path / "dispatch-backup-20260820T020000Z"
        archive.mkdir()
        (archive / backups.VERIFICATION_NAME).write_text(
            json.dumps({"verified_at": "2026-08-21T09:00:00Z"}), encoding="utf-8",
        )

        result = backups.backup_status(tmp_path)

        assert result.state == backups.VERIFIED
        assert result.verification["verified_at"] == "2026-08-21T09:00:00Z"

    def test_a_record_for_a_different_archive_is_not_borrowed(self, tmp_path):
        archive = tmp_path / "dispatch-backup-20260820T020000Z"
        archive.mkdir()
        (tmp_path / f"dispatch-backup-20260820T020000Z.{backups.VERIFICATION_NAME}").write_text(
            json.dumps({
                "archive": "dispatch-backup-20260101T000000Z",
                "verified_at": "2026-01-02T00:00:00Z",
            }),
            encoding="utf-8",
        )

        result = backups.backup_status(tmp_path)

        assert result.state == backups.UNVERIFIED

    def test_a_compressed_archive_is_dated_from_its_name_and_says_so(self, tmp_path):
        (tmp_path / "dispatch-backup-20260820T020000Z.tar.gz").write_bytes(b"not really a tar")

        result = backups.backup_status(tmp_path)

        assert result.state == backups.UNVERIFIED
        assert result.created_at == "2026-08-20T02:00:00Z"
        assert result.created_at_source == "archive name"

    def test_the_newest_archive_is_the_one_reported(self, tmp_path):
        older = tmp_path / "dispatch-backup-20260101T000000Z"
        newer = tmp_path / "dispatch-backup-20260820T020000Z"
        older.mkdir()
        newer.mkdir()
        os.utime(older, (1_000_000, 1_000_000))
        os.utime(newer, (2_000_000, 2_000_000))

        result = backups.backup_status(tmp_path)

        assert result.location == str(newer)

    def test_status_never_calls_an_unverified_backup_good(self, facts, tmp_path, monkeypatch):
        archive = tmp_path / "dispatch-backup-20260820T020000Z"
        archive.mkdir()
        facts.backup_dir = str(tmp_path)

        rendered = status_module.render(status_module.collect_status(facts=facts))

        assert "UNVERIFIED" in rendered
        assert "never been restored" in rendered
        for forbidden in (" LIVE", "CONNECTED", "CURRENT"):
            assert forbidden not in rendered


# ── Section 3.2: the launcher has no path to Current Reality ───────────

class TestNoPathToCurrentReality:
    #: The modules that own the freight record. The launcher observes processes
    #: and configuration; if it can reach these, it is no longer a control.
    FORBIDDEN = ("dispatch.services", "dispatch.store", "dispatch.spine")

    def test_importing_the_whole_package_pulls_in_nothing_operational(self):
        """Checked in a real interpreter, not by reading the source.

        A same-process assertion would pass simply because pytest had already
        imported those modules for another test file.
        """
        program = textwrap.dedent(
            """
            import sys

            import dispatch_launcher
            import dispatch_launcher.backups
            import dispatch_launcher.cli
            import dispatch_launcher.control
            import dispatch_launcher.locations
            import dispatch_launcher.pidfile
            import dispatch_launcher.probe
            import dispatch_launcher.processes
            import dispatch_launcher.redaction
            import dispatch_launcher.status

            leaked = sorted(
                name for name in sys.modules
                if name in ("dispatch.services", "dispatch.store", "dispatch.db")
                or name.startswith("dispatch.spine")
                or name == "flask"
            )
            print(",".join(leaked))
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
        )

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.strip() == ""

    def test_no_module_in_the_package_names_a_forbidden_import(self):
        package = REPO_ROOT / "dispatch_launcher"
        offenders: list[str] = []
        for module in sorted(package.glob("*.py")):
            source = module.read_text(encoding="utf-8")
            for line in source.splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                for forbidden in self.FORBIDDEN:
                    if forbidden in stripped:
                        offenders.append(f"{module.name}: {stripped}")

        assert offenders == []

    def test_the_configuration_probe_reads_and_does_not_write_records(self):
        """The probe touches configuration only; it opens no operational table."""
        source = (REPO_ROOT / "dispatch_launcher" / "probe.py").read_text(encoding="utf-8")

        assert "get_connection" not in source
        assert "import sqlite3" not in source
        assert "INSERT INTO" not in source.upper()
        assert "UPDATE " not in source.upper()

    def test_the_launcher_never_builds_the_flask_application(self):
        source = (REPO_ROOT / "dispatch_launcher" / "control.py").read_text(encoding="utf-8")

        assert "create_app" not in source
        assert "from portal.app" not in source


# ── Windows-only paths, tested through their parsers ───────────────────

class TestWindowsParsers:
    """The Windows branches cannot execute here. Their parsing can, and does.

    That the commands themselves behave as expected on Windows is UNVERIFIED --
    see proof/launcher/LAUNCHER_PROOF.md.
    """

    def test_cim_output_is_parsed_into_identity_facts(self):
        line = (
            r"7412|2026-08-24T06:15:09.1234567-05:00|"
            r'"C:\Python311\python.exe" "D:\Dispatch\portal\app.py"'
        )

        created, command_line = processes.parse_cim_line(line)

        assert created == "2026-08-24T06:15:09.1234567-05:00"
        assert command_line.endswith(r'"D:\Dispatch\portal\app.py"')

    def test_a_command_line_containing_a_pipe_is_not_truncated(self):
        created, command_line = processes.parse_cim_line("7412|2026-08-24T06:15:09|a | b | c")

        assert created == "2026-08-24T06:15:09"
        assert command_line == "a | b | c"

    def test_unparseable_output_yields_nothing_rather_than_a_guess(self):
        assert processes.parse_cim_line("") == (None, None)
        assert processes.parse_cim_line("7412") == (None, None)
        assert processes.parse_cim_line("7412|only-two-fields") == (None, None)

    def test_proc_stat_start_time_survives_a_process_name_with_spaces(self):
        # Fields 3..29 are literally numbered, so field 22 reads "22".
        stat = "42 (my (odd) program) " + " ".join(str(n) for n in range(3, 30))

        assert processes.parse_proc_stat_starttime(stat) == "22"

    def test_proc_stat_that_is_not_a_stat_line_yields_nothing(self):
        assert processes.parse_proc_stat_starttime("nonsense") is None
        assert processes.parse_proc_stat_starttime("42 (short) S 1 2") is None
        assert processes.parse_proc_stat_starttime("no parenthesis here") is None


# ── the operator-facing entry point ────────────────────────────────────

class TestCommandLine:
    def test_status_exits_non_zero_when_dispatch_is_stopped(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)

        exit_code = cli.main(["status"])

        assert exit_code == 1
        assert "DISPATCH - Operations Control" in capsys.readouterr().out

    def test_status_exits_zero_when_dispatch_is_running(
        self, capsys, monkeypatch, facts, stand_in, reap,
    ):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        started = control.start(facts=facts)
        reap(started.pid)

        assert cli.main(["status"]) == 0

    def test_a_failed_action_exits_non_zero(self, capsys, monkeypatch, facts):
        facts.secrets_block_start = True
        facts.weak_secret_names = ["PORTAL_SECRET_KEY"]
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)

        assert cli.main(["start"]) == 1
        assert "PORTAL_SECRET_KEY" in capsys.readouterr().out

    def test_the_menu_runs_an_action_and_quits(self, capsys, monkeypatch, facts):
        """[8] is Stop in Control Center v1. Stop is deliberately last -- it is
        the one control you must not hit by reaching for a neighbour."""
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["8", "q"])

        assert cli.run_menu(input_fn=lambda _prompt: next(answers)) == 0
        out = capsys.readouterr().out
        assert "Nothing to stop" in out
        # A control that changed something is followed by a fresh reading, so
        # the operator never has to ask for the status they just earned.
        assert out.count("DISPATCH - Operations Control") == 2

    def test_the_menu_accepts_the_word_as_well_as_the_number(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["stop", "q"])

        assert cli.run_menu(input_fn=lambda _prompt: next(answers)) == 0
        assert "Nothing to stop" in capsys.readouterr().out

    def test_an_unrecognised_choice_is_explained_not_ignored(self, capsys, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)
        answers = iter(["banana", "q"])

        cli.run_menu(input_fn=lambda _prompt: next(answers))

        assert "is not one of the choices" in capsys.readouterr().out

    def test_closing_the_window_quits_cleanly(self, monkeypatch, facts):
        monkeypatch.setattr(probe, "probe_runtime", lambda **k: facts)

        def _closed(_prompt):
            raise EOFError

        assert cli.run_menu(input_fn=_closed) == 0

    def test_the_logs_flag_prints_the_log_directory(self, capsys, launcher_sandbox):
        assert cli.main(["--logs"]) == 0
        assert str(launcher_sandbox) in capsys.readouterr().out

    def test_open_reports_the_address_even_when_no_browser_opens(self, monkeypatch, facts):
        monkeypatch.setattr(control.webbrowser, "open", lambda url: False)

        result = control.open_portal(facts=facts)

        assert result.ok is False
        assert f"http://127.0.0.1:{facts.port}" in result.message

    def test_open_warns_when_dispatch_is_not_running(self, monkeypatch, facts):
        monkeypatch.setattr(control.webbrowser, "open", lambda url: True)

        result = control.open_portal(facts=facts)

        assert result.ok is True
        assert any("does not appear to be running" in detail for detail in result.details)


# ── the Windows entry points exist and stay thin ───────────────────────

class TestWindowsEntryPoints:
    def test_both_wrappers_exist_at_the_repository_root(self):
        assert (REPO_ROOT / "dispatch.bat").is_file()
        assert (REPO_ROOT / "Dispatch.ps1").is_file()

    def test_the_wrappers_only_delegate(self):
        for name in ("dispatch.bat", "Dispatch.ps1"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            assert "dispatch_launcher" in text
            # No decisions in an untestable file: it must not reach for the
            # portal, the database, or a process table itself.
            assert "portal/app.py" not in text
            assert "taskkill" not in text.lower()

    def test_new_launchers_do_not_carry_the_superseded_program_name(self):
        for name in ("dispatch.bat", "Dispatch.ps1"):
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
            assert "L2-COS" not in text

    def test_the_wrappers_use_crlf_so_windows_can_run_them(self):
        for name in ("dispatch.bat", "Dispatch.ps1"):
            raw = (REPO_ROOT / name).read_bytes()
            assert b"\r\n" in raw
            assert raw.replace(b"\r\n", b"") .count(b"\n") == 0
