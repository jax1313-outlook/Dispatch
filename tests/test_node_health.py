"""CO-11: node health -- temperature only where the machine reports one, never a guess.

Owner direction, 2026-09-14: "... running in a temperature cooled Pelican box vented with Temp
gauge loaded on tablet for monitoring."

No test here runs the real temperature query: the probe's runner is replaced with one that
returns what Windows was observed to print (2026-09-14, this build machine: the thermal-zone
counter answered without administrator rights; the ACPI class said "Access denied"). The backup
facts come from a real run onto a folder standing in for a drive, so the card reads a record the
program wrote.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone

import pytest

import cin_lite.archive as cin_archive
from dispatch import backup_drives, node_health
from dispatch import services as dispatch_svc
from dispatch.db import set_db_path
from portal import joe_voice

OBSERVED_WINDOWS = [
    r"K|\_TZ.PCHZ|273",
    r"K|\_TZ.CHGZ|322",
    r"K|\_TZ.BATZ|302",
    r"K|\_TZ.GFXZ|273",
    r"K|\_TZ.CPUZ|354",
]


def runner_printing(lines, returncode=0):
    def run(command, timeout):
        assert command[0] == "powershell" and timeout <= 30
        return subprocess.CompletedProcess(command, returncode, stdout="\n".join(lines) + "\n", stderr="")
    return run


def runner_that_hangs(command, timeout):
    return None


@pytest.fixture(autouse=True)
def _no_real_probe(monkeypatch):
    """Every path through collect() uses a fake runner; the cache starts empty."""
    monkeypatch.setattr(node_health, "_cache", None)
    monkeypatch.setattr(node_health, "_run", runner_printing(OBSERVED_WINDOWS))
    monkeypatch.setattr(node_health, "_IS_WINDOWS", True)
    monkeypatch.delenv(node_health.HOT_ENV, raising=False)
    monkeypatch.delenv(backup_drives.RECORD_ENV, raising=False)
    monkeypatch.delenv(backup_drives.SWAP_DAYS_ENV, raising=False)


@pytest.fixture()
def estate(tmp_path, monkeypatch):
    data_dir = tmp_path / "live" / "PortalData"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "live" / "Memory" / "Evidence"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "live" / "Memory"))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "live" / "Archive"))
    (tmp_path / "live" / "Memory" / "Evidence").mkdir(parents=True)
    (tmp_path / "live" / "Archive").mkdir(parents=True)
    monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG", raising=False)
    monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", tmp_path / "live" / "Archive")
    set_db_path(data_dir / "dispatch.db")
    dispatch_svc.create_load(customer="Northbound Freight")
    yield data_dir
    set_db_path(None)


# ── temperature ────────────────────────────────────────────────────────

class TestTemperature:
    def test_the_hottest_real_zone_is_reported(self):
        found = node_health.parse_temperature_lines(OBSERVED_WINDOWS)
        assert found["status"] == "LIVE"
        assert found["celsius"] == pytest.approx(80.9, abs=0.1) and found["zone"] == r"\_TZ.CPUZ"

    def test_a_zero_degree_zone_is_unpopulated_not_a_reading(self):
        found = node_health.parse_temperature_lines(OBSERVED_WINDOWS)
        pch = next(z for z in found["zones"] if z["zone"] == r"\_TZ.PCHZ")
        assert pch["reported"] is False

    def test_zones_that_report_nothing_are_unavailable_with_no_number(self):
        found = node_health.parse_temperature_lines([r"K|\_TZ.PCHZ|273", r"K|\_TZ.GFXZ|273"])
        assert found["status"] == "UNAVAILABLE" and found["celsius"] is None
        assert "none reports a reading" in found["detail"]

    def test_a_refused_query_says_why(self):
        found = node_health.parse_temperature_lines(
            ["E|thermal zone counter|Invalid class", "E|acpi thermal zone|Access denied"])
        assert found["status"] == "UNAVAILABLE" and found["celsius"] is None
        assert "Access denied" in found["detail"]

    def test_tenths_of_kelvin_and_implausible_values(self):
        found = node_health.parse_temperature_lines(["DK|TZ0|3232", "K|TZ9|900", "junk", "K|TZ8|hot"])
        assert found["celsius"] == pytest.approx(50.05, abs=0.06)
        assert [z["zone"] for z in found["zones"] if not z["reported"]] == ["TZ9"]

    def test_a_query_that_never_answers_is_unavailable(self):
        found = node_health.read_temperature(runner_that_hangs)
        assert found["status"] == "UNAVAILABLE" and found["celsius"] is None
        assert "did not answer" in found["detail"]

    def test_the_query_is_read_only(self):
        script = node_health._PS_TEMPERATURE
        assert "Get-CimInstance" in script
        for verb in ("Set-", "Invoke-CimMethod", "New-", "Remove-", "Start-", "Stop-", "Restart-"):
            assert verb not in script


# ── the report ─────────────────────────────────────────────────────────

class TestReport:
    def test_disk_space_is_read_from_the_data_drive(self, estate):
        disk = node_health.disk_space()
        assert disk["status"] == "LIVE" and disk["free_bytes"] > 0
        assert disk["path"] == str(estate)

    def test_a_missing_data_folder_reads_its_drive(self, tmp_path):
        disk = node_health.disk_space(tmp_path / "not" / "yet")
        assert disk["status"] == "LIVE"

    def test_joe_is_unverified_never_invented_live_or_down(self, estate):
        from dispatch import audit

        report = node_health.collect(refresh=True)
        assert report["joe"]["status"] == "UNVERIFIED"
        assert report["joe"]["last_audited_action_at"] is None
        audit.record(action="mission-status", driver="driver-1")
        report = node_health.collect(refresh=True)
        assert report["joe"]["status"] == "UNVERIFIED"
        assert report["joe"]["last_audited_action_at"]

    def test_no_backup_recorded_is_called_out(self, estate):
        report = node_health.collect(refresh=True)
        assert report["backup"]["state"] == "ABSENT"
        assert "No checked backup in the last 24 hours." in report["attention"]

    def test_a_real_run_reaches_the_report_and_the_card(self, estate, tmp_path):
        drive_root = tmp_path / "volumes" / "usb1"
        drive_root.mkdir(parents=True)
        backup_drives.prepare_drive(drive_root, "Drive A")
        drive = backup_drives.choose_drive(backup_drives.find_backup_drives([drive_root]))
        run = backup_drives.run_drive_backup(drive)
        assert run.ok

        report = node_health.collect(refresh=True)
        assert report["backup"]["newest_pass_drive"] == "Drive A"
        assert report["backup"]["stale"] is False
        card = node_health.driver_card(report)
        assert "Backup under 1 h ago" in card["lines"]
        assert card["lines"][0] == "Temp 81°C"

    def test_running_hot_is_called_out(self, estate, monkeypatch):
        monkeypatch.setenv(node_health.HOT_ENV, "70")
        report = node_health.collect(refresh=True)
        assert any("running hot" in item for item in report["attention"])
        assert node_health.driver_card(report)["attention"] is True

    def test_the_report_is_cached_so_the_probe_is_not_run_per_request(self, estate, monkeypatch):
        calls = []

        def counting(command, timeout):
            calls.append(1)
            return runner_printing(OBSERVED_WINDOWS)(command, timeout)

        monkeypatch.setattr(node_health, "_run", counting)
        node_health.collect()
        node_health.collect()
        assert len(calls) == 1
        node_health.collect(refresh=True)
        assert len(calls) == 2


# ── the driver's words ─────────────────────────────────────────────────

class TestDriverCard:
    @pytest.mark.parametrize("lines", [OBSERVED_WINDOWS, ["E|acpi thermal zone|Access denied"]])
    def test_every_card_is_driver_safe(self, estate, monkeypatch, lines):
        monkeypatch.setattr(node_health, "_run", runner_printing(lines))
        card = node_health.driver_card(node_health.collect(refresh=True))
        assert card["title"] == "NODE"
        assert joe_voice.is_driver_safe(" ".join(card["lines"])) == []
        for word in ("LIVE", "UNAVAILABLE", "ABSENT", "UNVERIFIED"):
            assert word not in " ".join(card["lines"])

    def test_an_unreported_temperature_is_said_as_not_reported(self, estate, monkeypatch):
        monkeypatch.setattr(node_health, "_run", runner_that_hangs)
        card = node_health.driver_card(node_health.collect(refresh=True))
        assert card["lines"][0] == "Temp not reported"

    def test_stale_and_swap_due_are_said_plainly(self):
        report = {
            "checked_at": "2026-09-14T00:00:00Z",
            "temperature": {"status": "UNAVAILABLE"},
            "backup": {"newest_pass_age_hours": 30.2, "stale": True, "swap_due": True},
            "disk": {"free_bytes": 812_000_000_000},
            "uptime": {"node_seconds": 3 * 86400 + 4 * 3600},
            "attention": ["x"],
        }
        card = node_health.driver_card(report)
        assert card["lines"] == ["Temp not reported", "Backup 30 h old", "Swap backup drive",
                                 "812 GB free", "Up 3 d 4 h"]
        assert joe_voice.is_driver_safe(" ".join(card["lines"])) == []


# ── the screens and their gates ────────────────────────────────────────

@pytest.fixture()
def client(estate):
    from portal.app import create_app

    app = create_app({"TESTING": True, "LOGIN_DISABLED": False})
    with app.test_client() as c:
        yield c


def as_driver(client):
    with client.session_transaction() as s:
        s["driver_open"] = True
        s["role"] = "Driver"


def as_operations(client):
    with client.session_transaction() as s:
        s["user_id"] = "ops-test"
        s["role"] = "Operations"


class TestScreens:
    def test_a_driver_gets_the_card_and_nothing_more(self, client):
        as_driver(client)
        resp = client.get("/portal/node-card")
        assert resp.status_code == 200 and resp.get_json()["title"] == "NODE"
        for path in ("/api/node/health", "/operations/node"):
            refused = client.get(path)
            assert refused.status_code == 302 and "/login" in refused.headers["Location"]

    def test_nobody_signed_in_gets_nothing(self, client):
        for path in ("/portal/node-card", "/api/node/health", "/operations/node"):
            assert client.get(path).status_code == 302

    def test_operations_sees_the_full_report(self, client):
        as_operations(client)
        data = client.get("/api/node/health").get_json()
        assert set(data) >= {"temperature", "disk", "backup", "joe", "uptime", "attention"}
        html = client.get("/operations/node").get_data(as_text=True)
        assert "Temperature" in html and "Backups (rotating drives)" in html
        assert "UNVERIFIED" in html  # Joe, stated rather than invented

    def test_the_card_sits_at_the_end_of_the_mission_actions_column(self, client):
        as_driver(client)
        html = client.get("/portal", follow_redirects=True).get_data(as_text=True)
        column = html[html.index('aria-label="Mission actions"'):]
        column = column[:column.index("</section>")]
        assert 'id="node-card"' in column
        assert column.index("ALL MILESTONES") < column.index('id="node-card"')
        assert 'data-node-url="/portal/node-card"' in column
