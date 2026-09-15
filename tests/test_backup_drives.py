"""CO-12: rotating backup drives, full coverage, self-checking runs, and honest status.

Owner direction, 2026-09-14: "Back up is rotating 4TB Crucial external hard drives."

Every "drive" here is a folder under tmp_path. Nothing probes or writes a real volume.
Runs arrive the way the operator's do -- through run_drive_backup and the command line --
so the rotation record the status reads is one the program wrote, not one a test forged.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import cin_lite.archive as cin_archive
from dispatch import backup as backup_engine
from dispatch import backup_drives as drives
from dispatch import services as dispatch_svc
from dispatch.db import set_db_path

T0 = datetime(2026, 9, 1, 2, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def estate(tmp_path, monkeypatch):
    root = tmp_path / "live"
    data_dir = root / "PortalData"
    memory_root = root / "Memory"
    upload_dir = memory_root / "Evidence"
    archive_root = root / "Archive"
    cin_root = archive_root / "CIN"
    for directory in (data_dir, memory_root, upload_dir, archive_root, cin_root):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
    monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG", raising=False)
    for var in (drives.ROOTS_ENV, drives.RECORD_ENV, drives.SWAP_DAYS_ENV):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", cin_root)
    set_db_path(data_dir / "dispatch.db")
    dispatch_svc.create_load(customer="Northbound Freight")
    try:
        yield SimpleNamespace(root=root, data_dir=data_dir, memory_root=memory_root,
                              archive_root=archive_root, tmp=tmp_path)
    finally:
        set_db_path(None)


def _drive_folder(tmp_path: Path, label: str) -> Path:
    folder = tmp_path / "volumes" / label
    folder.mkdir(parents=True)
    return folder


def _prepared(tmp_path: Path, label: str, name: str) -> drives.FoundDrive:
    root = _drive_folder(tmp_path, label)
    drives.prepare_drive(root, name, now=T0)
    scan = drives.find_backup_drives([root])
    return drives.choose_drive(scan, name)


def _make_link(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


# ── coverage ───────────────────────────────────────────────────────────

class TestCoverage:
    def test_jsonl_logs_and_library_documents_are_captured(self, estate, tmp_path):
        (estate.data_dir / "joe_audit.jsonl").write_text('{"action": "x"}\n', encoding="utf-8")
        (estate.data_dir / "security_events.jsonl").write_text("{}\n", encoding="utf-8")
        docs = estate.data_dir / "LibraryDocuments" / "2026"
        docs.mkdir(parents=True)
        (docs / "w9.pdf").write_bytes(b"%PDF w9")

        result = backup_engine.create_backup(tmp_path / "out")
        paths = {e["path"] for e in result.manifest["files"]}
        assert "PortalData/joe_audit.jsonl" in paths
        assert "PortalData/security_events.jsonl" in paths
        assert "PortalData/LibraryDocuments/2026/w9.pdf" in paths
        assert result.ok, result.absent_sources

    def test_database_archive_and_memory_are_all_present(self, estate, tmp_path):
        (estate.archive_root / "load-1.json").write_text("{}", encoding="utf-8")
        (estate.memory_root / "Evidence" / "pod.pdf").write_bytes(b"pod")
        result = backup_engine.create_backup(tmp_path / "out")
        paths = {e["path"] for e in result.manifest["files"]}
        assert result.manifest["database"]["present"] is True
        assert any(p.endswith("dispatch.db") for p in paths)
        assert "ArchiveRecords/load-1.json" in paths
        assert "Memory/Evidence/pod.pdf" in paths

    def test_nothing_outside_the_configured_roots_is_swept_in(self, estate, tmp_path):
        outside = tmp_path / "not-dispatch"
        outside.mkdir()
        (outside / "private.txt").write_text("not ours", encoding="utf-8")
        result = backup_engine.create_backup(tmp_path / "out")
        roots = [Path(p) for p in backup_engine.configured_source_paths()]
        for entry in result.manifest["files"]:
            origin = Path(entry["origin"])
            assert any(origin == r or origin.is_relative_to(r) for r in roots), origin
        assert not any("private.txt" in e["path"] for e in result.manifest["files"])

    def test_a_link_out_of_a_root_is_not_followed(self, estate, tmp_path):
        outside = tmp_path / "whole-drive"
        outside.mkdir()
        (outside / "someone-elses.txt").write_text("not ours", encoding="utf-8")
        link = estate.data_dir / "shortcut"
        try:
            _make_link(link, outside)
        except OSError as exc:  # pragma: no cover - depends on platform privilege
            pytest.skip(f"this machine cannot create a link: {exc}")

        result = backup_engine.create_backup(tmp_path / "out")
        assert not any("someone-elses" in e["path"] for e in result.manifest["files"])
        assert any("not followed" in n for n in result.notes)


# ── every run checks itself ────────────────────────────────────────────

class TestSelfCheck:
    def test_a_run_rehashes_what_it_wrote(self, estate, tmp_path):
        result = backup_engine.create_backup(tmp_path / "out")
        assert result.hash_check == "PASS"
        assert result.self_check.checked == result.file_count

    def test_a_compressed_run_checks_the_tarball(self, estate, tmp_path):
        result = backup_engine.create_backup(tmp_path / "out", compress=True)
        assert str(result.archive_path).endswith(".tar.gz")
        assert result.hash_check == "PASS"

    def test_a_failed_check_makes_the_run_not_ok(self, estate, tmp_path, monkeypatch):
        real_verify = backup_engine.verify

        def corrupted(archive):
            found = real_verify(archive)
            found.mismatched.append("PortalData/dispatch.db")
            return found

        monkeypatch.setattr(backup_engine, "verify", corrupted)
        result = backup_engine.create_backup(tmp_path / "out")
        assert result.hash_check == "FAIL"
        assert result.ok is False

    def test_a_dry_run_claims_no_check(self, estate, tmp_path):
        result = backup_engine.create_backup(tmp_path / "out", dry_run=True)
        assert result.hash_check is None


# ── identity ───────────────────────────────────────────────────────────

class TestIdentity:
    def test_prepare_writes_an_identity_and_the_backup_folder(self, estate, tmp_path):
        root = _drive_folder(tmp_path, "usb1")
        identity = drives.prepare_drive(root, "  Drive   A ", now=T0)
        assert identity.name == "Drive A"
        data = json.loads((root / drives.IDENTITY_FILE).read_text(encoding="utf-8"))
        assert data["drive_id"] == identity.drive_id and data["schema"] == 1
        assert (root / drives.BACKUP_FOLDER).is_dir()
        assert drives.read_identity(root) == identity

    def test_a_prepared_drive_is_never_re_prepared(self, estate, tmp_path):
        root = _drive_folder(tmp_path, "usb1")
        first = drives.prepare_drive(root, "Drive A")
        before = (root / drives.IDENTITY_FILE).read_bytes()
        with pytest.raises(drives.DriveIdentityError, match="already prepared"):
            drives.prepare_drive(root, "Drive B")
        assert (root / drives.IDENTITY_FILE).read_bytes() == before
        assert drives.read_identity(root).drive_id == first.drive_id

    def test_the_data_drive_cannot_be_prepared_as_a_backup_drive(self, estate):
        with pytest.raises(drives.DriveIdentityError, match="holds Dispatch data"):
            drives.prepare_drive(estate.root, "Drive A")
        assert not (estate.root / drives.IDENTITY_FILE).exists()

    def test_a_name_is_required(self, estate, tmp_path):
        with pytest.raises(drives.DriveIdentityError):
            drives.prepare_drive(_drive_folder(tmp_path, "usb1"), "   ")

    def test_the_drive_is_found_by_identity_wherever_it_is_mounted(self, estate, tmp_path):
        root = _drive_folder(tmp_path, "E")
        identity = drives.prepare_drive(root, "Drive A")
        plain = _drive_folder(tmp_path, "F")
        scan = drives.find_backup_drives([root, plain])
        assert [d.identity.drive_id for d in scan.found] == [identity.drive_id]

        moved = tmp_path / "volumes" / "T"
        root.rename(moved)  # the same drive, given a different letter next time
        scan = drives.find_backup_drives([plain, moved])
        assert [(d.root, d.identity.drive_id) for d in scan.found] == [(moved, identity.drive_id)]

    def test_a_broken_identity_is_reported_not_skipped_silently(self, estate, tmp_path):
        root = _drive_folder(tmp_path, "usb1")
        (root / drives.IDENTITY_FILE).write_text("{not json", encoding="utf-8")
        scan = drives.find_backup_drives([root])
        assert scan.found == []
        assert scan.problems and "not readable" in scan.problems[0]

    def test_a_copied_identity_file_disqualifies_both_drives(self, estate, tmp_path):
        a = _drive_folder(tmp_path, "usb1")
        drives.prepare_drive(a, "Drive A")
        b = _drive_folder(tmp_path, "usb2")
        shutil.copy2(a / drives.IDENTITY_FILE, b / drives.IDENTITY_FILE)
        scan = drives.find_backup_drives([a, b])
        assert scan.found == []
        with pytest.raises(drives.DriveIdentityError):
            drives.choose_drive(scan)

    def test_choose_needs_exactly_one_or_a_name(self, estate, tmp_path):
        a = _drive_folder(tmp_path, "usb1")
        b = _drive_folder(tmp_path, "usb2")
        drives.prepare_drive(a, "Drive A")
        drives.prepare_drive(b, "Drive B")
        scan = drives.find_backup_drives([a, b])
        with pytest.raises(drives.DriveIdentityError, match="more than one"):
            drives.choose_drive(scan)
        assert drives.choose_drive(scan, "drive b").root == b
        with pytest.raises(drives.DriveIdentityError, match="no prepared"):
            drives.choose_drive(drives.find_backup_drives([]))

    def test_roots_can_be_named_explicitly(self, estate, tmp_path, monkeypatch):
        a = _drive_folder(tmp_path, "usb1")
        monkeypatch.setenv(drives.ROOTS_ENV, str(a))
        assert drives.mounted_roots() == [a]

    def test_listing_mounted_volumes_is_read_only_and_does_not_raise(self, estate):
        roots = drives.mounted_roots()
        assert isinstance(roots, list)


# ── runs ───────────────────────────────────────────────────────────────

class TestRuns:
    def test_a_run_writes_checks_and_logs_in_both_places(self, estate, tmp_path):
        drive = _prepared(tmp_path, "usb1", "Drive A")
        run = drives.run_drive_backup(drive, now=T0)

        assert run.ok and run.entry["hash_check"] == "PASS"
        archive = Path(run.entry["archive_path"])
        assert archive.parent == drive.root / drives.BACKUP_FOLDER and archive.is_dir()
        on_drive = drives.read_record(drive.backup_dir / drives.ROTATION_LOG)
        on_node = drives.read_record()
        assert on_drive == on_node == [run.entry]
        assert run.local_record == estate.data_dir / drives.LOCAL_RECORD_NAME
        assert on_node[0]["drive_name"] == "Drive A"

    def test_runs_never_delete_an_earlier_backup(self, estate, tmp_path):
        drive = _prepared(tmp_path, "usb1", "Drive A")
        first = drives.run_drive_backup(drive, now=T0)
        (drive.backup_dir / "dispatch-backup-keep-me").mkdir()
        second = drives.run_drive_backup(drive, now=T0 + timedelta(hours=1))
        assert Path(first.entry["archive_path"]).exists()
        assert Path(second.entry["archive_path"]).exists()
        assert (drive.backup_dir / "dispatch-backup-keep-me").exists()
        assert len(drives.read_record(drive.backup_dir / drives.ROTATION_LOG)) == 2

    def test_a_run_that_breaks_is_still_written_down(self, estate, tmp_path, monkeypatch):
        drive = _prepared(tmp_path, "usb1", "Drive A")

        def disk_full(*args, **kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(backup_engine, "create_backup", disk_full)
        with pytest.raises(OSError):
            drives.run_drive_backup(drive, now=T0)
        [entry] = drives.read_record()
        assert entry["hash_check"] == "FAIL" and "No space left" in entry["error"]
        assert drives.read_record(drive.backup_dir / drives.ROTATION_LOG) == [entry]

    def test_a_run_refuses_a_drive_that_holds_the_data(self, estate, tmp_path):
        identity = drives.DriveIdentity(drive_id="x" * 32, name="Bad", prepared_at="")
        fake = drives.FoundDrive(root=estate.root, identity=identity)
        with pytest.raises(drives.DriveIdentityError, match="refusing"):
            drives.run_drive_backup(fake, now=T0)
        assert not (estate.root / drives.BACKUP_FOLDER).exists()


# ── status ─────────────────────────────────────────────────────────────

class TestRotationStatus:
    def test_nothing_recorded_is_absent_and_stale(self, estate):
        status = drives.rotation_status(now=T0)
        assert status.state == "ABSENT" and status.stale is True
        assert status.swap_due is False

    def test_fresh_backup_is_not_stale_and_ages_into_a_warning(self, estate, tmp_path):
        drive = _prepared(tmp_path, "usb1", "Drive A")
        drives.run_drive_backup(drive, now=T0)
        fresh = drives.rotation_status(now=T0 + timedelta(hours=3))
        assert fresh.stale is False and fresh.newest_pass_age_hours == 3.0
        assert fresh.drives[0].last_pass_age_hours == 3.0

        old = drives.rotation_status(now=T0 + timedelta(hours=25))
        assert old.stale is True
        assert any("older than 24 hours" in w for w in old.warnings)

    def test_time_to_swap_after_seven_days_on_one_drive(self, estate, tmp_path):
        a = _prepared(tmp_path, "usb1", "Drive A")
        for day in (0, 3, 6):
            drives.run_drive_backup(a, now=T0 + timedelta(days=day))
        assert drives.rotation_status(now=T0 + timedelta(days=6, hours=1)).swap_due is False

        drives.run_drive_backup(a, now=T0 + timedelta(days=7))
        due = drives.rotation_status(now=T0 + timedelta(days=7, hours=1))
        assert due.swap_due is True and due.current_drive == "Drive A"
        assert any("Time to swap drives" in w for w in due.warnings)

        b = _prepared(tmp_path, "usb2", "Drive B")
        drives.run_drive_backup(b, now=T0 + timedelta(days=8))
        swapped = drives.rotation_status(now=T0 + timedelta(days=8, hours=1))
        assert swapped.swap_due is False and swapped.current_drive == "Drive B"
        assert {d.name for d in swapped.drives} == {"Drive A", "Drive B"}
        assert not any("rotation needs a second drive" in w for w in swapped.warnings)

    def test_swap_interval_is_configurable(self, estate, tmp_path, monkeypatch):
        a = _prepared(tmp_path, "usb1", "Drive A")
        drives.run_drive_backup(a, now=T0)
        monkeypatch.setenv(drives.SWAP_DAYS_ENV, "3")
        assert drives.rotation_status(now=T0 + timedelta(days=3)).swap_due is True
        monkeypatch.setenv(drives.SWAP_DAYS_ENV, "soon")
        status = drives.rotation_status(now=T0 + timedelta(days=3))
        assert status.swap_days == 7 and status.swap_due is False
        assert any("not a whole number" in w for w in status.warnings)

    def test_a_failed_run_is_never_the_newest_good_backup(self, estate, tmp_path, monkeypatch):
        a = _prepared(tmp_path, "usb1", "Drive A")
        drives.run_drive_backup(a, now=T0)
        monkeypatch.setattr(backup_engine, "create_backup",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("unplugged")))
        with pytest.raises(OSError):
            drives.run_drive_backup(a, now=T0 + timedelta(hours=30))
        status = drives.rotation_status(now=T0 + timedelta(hours=31))
        assert status.newest_pass_at == "2026-09-01T02:00:00Z"
        assert status.stale is True
        assert any("did not pass" in w for w in status.warnings)

    def test_status_says_a_pass_is_not_a_restore_test(self, estate):
        assert "not a restore test" in drives.rotation_status(now=T0).to_dict()["hash_check_meaning"]


# ── command line, the way the operator arrives ─────────────────────────

class TestCommandLine:
    @pytest.fixture()
    def cli(self):
        import importlib.util

        path = Path(__file__).resolve().parent.parent / "scripts" / "dispatch_backup.py"
        spec = importlib.util.spec_from_file_location("dispatch_backup_cli_drives", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_prepare_list_back_up_and_report(self, cli, estate, tmp_path, capsys):
        root = _drive_folder(tmp_path, "usb1")
        assert cli.main(["prepare-drive", str(root), "--name", "Drive A"]) == 0
        assert cli.main(["drives", "--root", str(root)]) == 0
        assert "Drive A" in capsys.readouterr().out

        assert cli.main(["drive-backup", "--root", str(root)]) == 0
        out = capsys.readouterr().out
        assert "hash check: PASS" in out and "not a restore test" in out

        assert cli.main(["rotation-status"]) == 0  # fresh and not due: exit 0, warnings still printed
        out = capsys.readouterr().out
        assert "Drive A" in out and "rotation needs a second drive" in out

    def test_no_drive_plugged_in_is_a_refusal(self, cli, estate, tmp_path, capsys):
        empty = _drive_folder(tmp_path, "usb1")
        assert cli.main(["drive-backup", "--root", str(empty)]) == 3
        assert "no prepared backup drive" in capsys.readouterr().err
