"""Tests for the backup/restore capability (Workstream D).

The audits found that Dispatch had no backup at all: a disk failure lost the
database, the JSON stores, and every uploaded proof-of-delivery file with no way
back. What makes that dangerous is not the absence of a copy routine -- it is
that a copy routine is easy to write and easy to believe in without ever proving
it. So these tests refuse to assert that "files were copied".

Every round-trip test below destroys the live estate after taking the backup
(`shutil.rmtree`, the disk failure), restores into a clean directory, repoints
the application's own resolvers at it, and then reads the data back through
`dispatch.services` -- the same functions the portal uses. A backup only counts
as working if the load, its milestone, its evidence row and the evidence file's
bytes all come back through the real read path.

The remaining tests pin the properties that make a backup trustworthy rather
than merely present: it fails loudly when a source is missing, it detects
tampering and refuses to restore from it, it never overwrites a destination by
accident, its dry runs write nothing, and it never carries secrets onto backup
media.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import cin_lite.archive as cin_archive
from dispatch import backup as backup_engine
from dispatch import services as dispatch_svc
from dispatch.db import set_db_path

EVIDENCE_BYTES = b"%PDF-1.4 signed bill of lading \x00\x01\x02 northbound freight"
SECRET_VALUE = "correct-horse-battery-staple-9f3a"


@pytest.fixture()
def estate(tmp_path, monkeypatch):
    """A live estate laid out the way the D-drive ownership structure lays it out.

    Four separate roots, with the evidence directory *nested* inside the memory
    root exactly as portal/config.py's DISPATCH_MEMORY_ROOT fallback nests it.
    The nesting is load-bearing for the archive layout, so the tests exercise it
    rather than the collapsed default where every root is one directory.
    """
    root = tmp_path / "live"
    data_dir = root / "PortalData"
    memory_root = root / "Memory"
    upload_dir = memory_root / "Evidence"
    archive_root = root / "ArchiveRecords"
    cin_root = root / "CIN"
    for directory in (data_dir, memory_root, upload_dir, archive_root, cin_root):
        directory.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(memory_root))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(archive_root))
    # cin_lite.archive resolves its root once at import; conftest's tmp_archive
    # fixture rebinds it, and so does this, to keep the CIN tree inside the
    # estate that gets destroyed.
    monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", cin_root)

    set_db_path(data_dir / "dispatch.db")
    try:
        yield SimpleNamespace(
            root=root, data_dir=data_dir, memory_root=memory_root,
            upload_dir=upload_dir, archive_root=archive_root, cin_root=cin_root,
        )
    finally:
        set_db_path(None)


@pytest.fixture()
def seeded(estate):
    """Real operational data, written through the real service functions."""
    load = dispatch_svc.create_load(
        customer="Northbound Freight",
        broker_shipper="Tidewater Logistics",
        pickup_location="Jacksonville, FL",
        delivery_location="Savannah, GA",
    )
    milestone = dispatch_svc.add_milestone(
        load["load_id"], "dispatched", location="Jacksonville, FL",
        note="Driver departed yard", entered_by="dispatcher-1",
    )
    evidence = dispatch_svc.attach_evidence(
        load["load_id"],
        evidence_type="bol",
        description="Signed BOL",
        related_milestone_id=milestone["milestone_id"],
        uploaded_by="driver-1",
        file_data=EVIDENCE_BYTES,
        original_filename="signed-bol.pdf",
    )

    # One JSON store per root, so the round trip proves each configured source is
    # actually captured and not just the one that happens to be the data dir.
    from portal.models import archive as portal_archive
    from portal.models import conflict as portal_conflict
    from portal.models import library as portal_library

    notice = portal_conflict.create_notice(
        conflict_type="double_booking", severity="high", sandbox_id="SB-0001",
        explanation="Two loads assigned to one driver", recommended_action="Reassign",
    )
    library_record = portal_library.add_record(
        "broker", "Tidewater Logistics", content="Net-30, quick-pay available"
    )
    archive_record = portal_archive.create_record(
        "load", source_id=load["load_id"], title="Jacksonville to Savannah",
        record_data={"customer": "Northbound Freight"},
    )
    (estate.cin_root / "Intelligence").mkdir(parents=True, exist_ok=True)
    (estate.cin_root / "Intelligence" / "CIN-TEST-0001.json").write_text(
        json.dumps({"notice_id": "CIN-TEST-0001"}), encoding="utf-8"
    )

    return SimpleNamespace(
        load=load, milestone=milestone, evidence=evidence, notice=notice,
        library_record=library_record, archive_record=archive_record,
    )


def _repoint(monkeypatch, result: backup_engine.RestoreResult) -> None:
    """Point the application at a restored estate, the way an operator would.

    Nothing here is test-only plumbing: these are the env vars the restore result
    hands the operator, and dispatch.db's path resolution, which is what
    BACKUP_AND_RECOVERY.md tells them to set.
    """
    for var, value in result.env.items():
        monkeypatch.setenv(var, value)
    if var_root := result.env.get("DISPATCH_ARCHIVE_PATH"):
        monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", Path(var_root))
    assert result.database_path is not None
    set_db_path(Path(result.database_path))


def _disaster(estate) -> None:
    """The failure this whole workstream exists for: the live estate is gone."""
    shutil.rmtree(estate.root)
    assert not estate.root.exists()


# ── manifest ───────────────────────────────────────────────────────────


class TestManifest:
    def test_every_file_carries_a_relative_path_size_and_sha256(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        assert result.file_count > 0
        for entry in result.manifest["files"]:
            archived = result.archive_path / entry["path"]
            assert not Path(entry["path"]).is_absolute()
            assert archived.is_file()
            assert entry["size"] == archived.stat().st_size
            assert entry["sha256"] == backup_engine.sha256_file(archived)

    def test_records_tool_version_and_utc_creation_time(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        assert result.manifest["tool_version"] == backup_engine.TOOL_VERSION
        assert result.manifest["created_at"].endswith("Z")

    def test_records_database_schema_and_row_counts(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        database = result.manifest["database"]
        assert database["present"] is True
        assert database["row_counts"]["loads"] == 1
        assert database["row_counts"]["milestones"] == 1
        assert database["row_counts"]["evidence"] == 1
        table_names = {obj["name"] for obj in database["schema"] if obj["type"] == "table"}
        assert {"loads", "milestones", "evidence"} <= table_names

    def test_database_is_snapshotted_not_file_copied(self, tmp_path, seeded):
        """The WAL sidecars must not be in the archive.

        Their presence would mean the database was captured by copying files off
        a live WAL database -- the failure mode that silently loses whatever the
        last commits were still sitting in the -wal file.
        """
        result = backup_engine.create_backup(tmp_path / "backups")
        names = {Path(entry["path"]).name for entry in result.manifest["files"]}
        assert "dispatch.db" in names
        assert not any(name.startswith("dispatch.db-") for name in names)
        assert result.manifest["database"]["archive_path"].endswith("PortalData/dispatch.db")

    def test_nested_source_keeps_its_position_in_the_archive(self, tmp_path, seeded):
        """PORTAL_UPLOAD_DIR sits under DISPATCH_MEMORY_ROOT and must stay there."""
        result = backup_engine.create_backup(tmp_path / "backups")
        by_role = {",".join(s["roles"]): s for s in result.manifest["sources"]}
        assert by_role["uploads"]["archive_path"] == "Memory/Evidence"
        assert by_role["memory"]["archive_path"] == "Memory"

    def test_missing_source_is_reported_not_silently_omitted(self, tmp_path, estate, monkeypatch):
        """Silence is the failure mode being designed against."""
        monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", estate.root / "gone")
        result = backup_engine.create_backup(tmp_path / "backups")

        assert result.ok is False
        absent_paths = {entry["path"] for entry in result.absent_sources}
        assert str(estate.root / "gone") in absent_paths
        recorded = [s for s in result.manifest["sources"] if "cin_archive" in s["roles"]][0]
        assert recorded["present"] is False
        assert recorded["reason"]


# ── the round trip ─────────────────────────────────────────────────────


class TestRoundTrip:
    @pytest.fixture()
    def restored(self, tmp_path, seeded, estate, monkeypatch):
        result = backup_engine.create_backup(tmp_path / "backups")
        _disaster(estate)
        restore_result = backup_engine.restore(result.archive_path, tmp_path / "restored")
        _repoint(monkeypatch, restore_result)
        return SimpleNamespace(backup=result, restore=restore_result, seeded=seeded)

    def test_load_record_comes_back(self, restored):
        load = dispatch_svc.get_load(restored.seeded.load["load_id"])
        assert load is not None
        assert load["customer"] == "Northbound Freight"
        assert load["broker_shipper"] == "Tidewater Logistics"
        assert load["delivery_location"] == "Savannah, GA"

    def test_milestone_record_comes_back(self, restored):
        from dispatch import store as dispatch_store

        milestones = dispatch_store.list_milestones(restored.seeded.load["load_id"])
        assert [m["milestone_id"] for m in milestones] == [
            restored.seeded.milestone["milestone_id"]
        ]
        assert milestones[0]["event_type"] == "dispatched"
        assert milestones[0]["note"] == "Driver departed yard"

    def test_evidence_row_comes_back(self, restored):
        rows = dispatch_svc.list_evidence(restored.seeded.load["load_id"])
        assert len(rows) == 1
        row = rows[0]
        assert row["evidence_id"] == restored.seeded.evidence["evidence_id"]
        assert row["original_filename"] == "signed-bol.pdf"
        assert row["file_size"] == len(EVIDENCE_BYTES)
        assert row["checksum"] == restored.seeded.evidence["checksum"]

    def test_evidence_file_bytes_are_identical(self, restored):
        """Read back through the real download path, not by guessing a filename.

        services.get_evidence_file() resolves the absolute path stored in the
        evidence row. Before restore() repointed those rows at the restored
        files, this returned None -- the database came back and every file link
        in it was dead.
        """
        located = dispatch_svc.get_evidence_file(restored.seeded.evidence["evidence_id"])
        assert located is not None, "restored evidence row does not resolve to a file"
        path, filename = located
        assert filename == "signed-bol.pdf"
        assert path.read_bytes() == EVIDENCE_BYTES
        assert path.is_relative_to(restored.restore.destination)
        assert restored.restore.paths_rehomed >= 1

    def test_portal_json_stores_come_back_from_every_root(self, restored):
        from portal.models import archive as portal_archive
        from portal.models import conflict as portal_conflict
        from portal.models import library as portal_library

        assert [n["id"] for n in portal_conflict.get_all()] == [restored.seeded.notice["id"]]
        broker_records = portal_library.get_section("broker")
        assert [r["name"] for r in broker_records] == ["Tidewater Logistics"]
        assert [r["id"] for r in portal_archive.get_section("load")] == [
            restored.seeded.archive_record["id"]
        ]

    def test_cin_archive_tree_comes_back(self, restored):
        cin_root = Path(restored.restore.env["DISPATCH_ARCHIVE_PATH"])
        assert (cin_root / "Intelligence" / "CIN-TEST-0001.json").is_file()

    def test_restored_row_counts_match_the_manifest(self, restored):
        from dispatch.db import get_connection

        with get_connection() as conn:
            for table, expected in restored.backup.manifest["database"]["row_counts"].items():
                actual = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                assert actual == expected, table

    def test_every_root_gets_an_env_var_pointing_at_it(self, restored):
        env = restored.restore.env
        assert set(env) == {
            "PORTAL_DATA_DIR", "PORTAL_UPLOAD_DIR",
            "DISPATCH_MEMORY_ROOT", "DISPATCH_ARCHIVE_ROOT", "DISPATCH_ARCHIVE_PATH",
        }
        for value in env.values():
            assert Path(value).is_dir()

    def test_a_second_backup_of_the_restored_estate_verifies(self, restored, tmp_path):
        """The restored estate is itself backup-able -- recovery is not one-shot."""
        second = backup_engine.create_backup(tmp_path / "backups-2")
        assert second.ok is True
        assert backup_engine.verify(second.archive_path).ok is True


# ── integrity ──────────────────────────────────────────────────────────


class TestVerification:
    def test_fresh_archive_verifies(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        check = backup_engine.verify(result.archive_path)
        assert check.ok is True
        assert check.checked == result.file_count

    def test_tampered_file_is_detected(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        target = result.archive_path / "PortalData" / "conflicts.json"
        target.write_text(json.dumps([{"id": "CN-9999", "injected": True}]), encoding="utf-8")

        check = backup_engine.verify(result.archive_path)
        assert check.ok is False
        assert "PortalData/conflicts.json" in check.mismatched

    def test_deleted_file_is_detected(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        (result.archive_path / "PortalData" / "conflicts.json").unlink()
        check = backup_engine.verify(result.archive_path)
        assert check.ok is False
        assert "PortalData/conflicts.json" in check.missing

    def test_restore_from_a_tampered_archive_writes_nothing(self, tmp_path, seeded, estate):
        """Fails closed: a bad archive must not leave a half-restored estate.

        A partial restore is worse than a refused one -- it looks like data.
        """
        result = backup_engine.create_backup(tmp_path / "backups")
        (result.archive_path / "PortalData" / "conflicts.json").write_text("[]", encoding="utf-8")
        destination = tmp_path / "restored"

        with pytest.raises(backup_engine.BackupIntegrityError):
            backup_engine.restore(result.archive_path, destination)

        assert not destination.exists() or not any(destination.iterdir())

    def test_restore_from_a_tampered_database_writes_nothing(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        db_copy = result.archive_path / result.manifest["database"]["archive_path"]
        db_copy.write_bytes(db_copy.read_bytes() + b"\x00tampered")
        destination = tmp_path / "restored"

        with pytest.raises(backup_engine.BackupIntegrityError):
            backup_engine.restore(result.archive_path, destination)
        assert not destination.exists() or not any(destination.iterdir())

    def test_manifest_from_an_unknown_format_is_refused(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        manifest_path = result.archive_path / backup_engine.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["manifest_version"] = backup_engine.MANIFEST_VERSION + 99
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with pytest.raises(backup_engine.ManifestError):
            backup_engine.restore(result.archive_path, tmp_path / "restored")


# ── destination safety ─────────────────────────────────────────────────


class TestDestinationSafety:
    def test_restore_refuses_a_non_empty_destination(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        destination = tmp_path / "restored"
        destination.mkdir()
        occupant = destination / "already-here.txt"
        occupant.write_text("someone else's data", encoding="utf-8")

        with pytest.raises(backup_engine.DestinationNotEmptyError):
            backup_engine.restore(result.archive_path, destination)

        assert occupant.read_text(encoding="utf-8") == "someone else's data"
        assert list(destination.iterdir()) == [occupant]

    def test_force_allows_a_non_empty_destination(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        destination = tmp_path / "restored"
        destination.mkdir()
        (destination / "already-here.txt").write_text("stale", encoding="utf-8")

        restored = backup_engine.restore(result.archive_path, destination, force=True)
        assert restored.restored
        assert (destination / "PortalData" / "dispatch.db").is_file()

    def test_an_empty_destination_directory_is_accepted(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        destination = tmp_path / "restored"
        destination.mkdir()
        assert backup_engine.restore(result.archive_path, destination).restored


# ── dry runs ───────────────────────────────────────────────────────────


class TestDryRun:
    def test_backup_dry_run_writes_nothing(self, tmp_path, seeded):
        destination = tmp_path / "backups"
        result = backup_engine.create_backup(destination, dry_run=True)

        assert result.dry_run is True
        assert not destination.exists()
        assert result.file_count > 0
        assert result.total_bytes > 0

    def test_backup_dry_run_reports_what_would_be_captured(self, tmp_path, seeded):
        planned = backup_engine.create_backup(tmp_path / "backups", dry_run=True)
        actual = backup_engine.create_backup(tmp_path / "backups")

        planned_paths = {entry["path"] for entry in planned.manifest["files"]}
        actual_paths = {
            entry["path"] for entry in actual.manifest["files"]
            if entry["source"] != "database"
        }
        assert planned_paths == actual_paths

    def test_restore_dry_run_writes_nothing(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        destination = tmp_path / "restored"

        planned = backup_engine.restore(result.archive_path, destination, dry_run=True)

        assert planned.dry_run is True
        assert planned.restored
        assert planned.env
        assert not destination.exists()


# ── secrets ────────────────────────────────────────────────────────────


class TestSecrets:
    @pytest.fixture(autouse=True)
    def _configured_secrets(self, monkeypatch):
        monkeypatch.setenv("PORTAL_SECRET_KEY", SECRET_VALUE)
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", SECRET_VALUE)
        monkeypatch.setenv("DISPATCH_SAM_API_KEY", SECRET_VALUE)
        monkeypatch.setenv("DISPATCH_SMTP_PASSWORD", SECRET_VALUE)
        monkeypatch.setenv("DISPATCH_EMAIL_REVIEWER", "ops@example.com")

    def test_no_secret_value_appears_anywhere_in_the_archive(self, tmp_path, seeded):
        """Backup media leave the building; live configuration does not."""
        result = backup_engine.create_backup(tmp_path / "backups")
        needle = SECRET_VALUE.encode("utf-8")
        for path in result.archive_path.rglob("*"):
            if path.is_file():
                assert needle not in path.read_bytes(), path

    def test_secret_names_are_recorded_with_a_redaction_placeholder(self, tmp_path, seeded):
        result = backup_engine.create_backup(tmp_path / "backups")
        environment = result.manifest["environment"]
        for name in (
            "PORTAL_SECRET_KEY", "DISPATCH_EMAIL_SECRET",
            "DISPATCH_SAM_API_KEY", "DISPATCH_SMTP_PASSWORD",
        ):
            assert environment[name] == backup_engine.REDACTED

    def test_non_secret_configuration_is_exported_by_value(self, tmp_path, seeded, estate):
        result = backup_engine.create_backup(tmp_path / "backups")
        environment = result.manifest["environment"]
        assert environment["DISPATCH_EMAIL_REVIEWER"] == "ops@example.com"
        assert environment["PORTAL_DATA_DIR"] == str(estate.data_dir)
        assert environment["DISPATCH_MEMORY_ROOT"] == str(estate.memory_root)


# ── tar archives ───────────────────────────────────────────────────────


class TestTarArchive:
    def test_compressed_archive_round_trips(self, tmp_path, seeded, estate, monkeypatch):
        result = backup_engine.create_backup(tmp_path / "backups", compress=True)
        assert result.archive_path.suffixes[-2:] == [".tar", ".gz"]
        assert result.archive_path.is_file()
        assert backup_engine.verify(result.archive_path).ok is True

        _disaster(estate)
        restored = backup_engine.restore(result.archive_path, tmp_path / "restored")
        _repoint(monkeypatch, restored)

        load = dispatch_svc.get_load(seeded.load["load_id"])
        assert load is not None and load["customer"] == "Northbound Freight"
        located = dispatch_svc.get_evidence_file(seeded.evidence["evidence_id"])
        assert located is not None and located[0].read_bytes() == EVIDENCE_BYTES


# ── operator entry point ───────────────────────────────────────────────


class TestCommandLine:
    @pytest.fixture()
    def cli(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "dispatch_backup_cli",
            Path(__file__).resolve().parent.parent / "scripts" / "dispatch_backup.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_backup_then_verify_then_restore(self, cli, tmp_path, seeded, capsys):
        destination = tmp_path / "backups"
        assert cli.main(["backup", str(destination), "--name", "nightly"]) == 0
        archive = destination / "nightly"
        assert cli.main(["verify", str(archive)]) == 0
        assert cli.main(["restore", str(archive), str(tmp_path / "restored")]) == 0
        assert (tmp_path / "restored" / "PortalData" / "dispatch.db").is_file()

    def test_missing_source_is_a_non_zero_exit(self, cli, tmp_path, estate, monkeypatch):
        """A scheduled backup that stopped capturing a root must fail the job."""
        monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", estate.root / "gone")
        assert cli.main(["backup", str(tmp_path / "backups")]) == 2

    def test_restore_over_a_non_empty_destination_is_a_non_zero_exit(self, cli, tmp_path, seeded):
        destination = tmp_path / "backups"
        cli.main(["backup", str(destination), "--name", "nightly"])
        occupied = tmp_path / "restored"
        occupied.mkdir()
        (occupied / "keep.txt").write_text("keep", encoding="utf-8")
        assert cli.main(["restore", str(destination / "nightly"), str(occupied)]) == 3
        assert (occupied / "keep.txt").is_file()

    def test_tampered_archive_is_a_non_zero_exit(self, cli, tmp_path, seeded):
        destination = tmp_path / "backups"
        cli.main(["backup", str(destination), "--name", "nightly"])
        (destination / "nightly" / "PortalData" / "conflicts.json").write_text("[]", encoding="utf-8")
        assert cli.main(["verify", str(destination / "nightly")]) == 1
        assert cli.main(["restore", str(destination / "nightly"), str(tmp_path / "restored")]) == 4


# ── the collapsed default layout ───────────────────────────────────────


class TestCollapsedDefaultLayout:
    """With no D-drive env vars set, four roles resolve to one directory.

    portal.models.get_archive_dir() and get_memory_dir() both fall back to
    get_data_dir(), and the upload directory falls back to a subdirectory of it.
    A backup that walked each role independently would store the same bytes four
    times and, worse, restore them into four divergent copies that then drift
    apart. These tests pin the collapsed case as carefully as the split one,
    because it is what a default install actually runs.
    """

    @pytest.fixture()
    def collapsed(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "live" / "PortalData"
        data_dir.mkdir(parents=True)
        monkeypatch.setenv("PORTAL_DATA_DIR", str(data_dir))
        monkeypatch.delenv("PORTAL_UPLOAD_DIR", raising=False)
        monkeypatch.delenv("DISPATCH_MEMORY_ROOT", raising=False)
        monkeypatch.delenv("DISPATCH_ARCHIVE_ROOT", raising=False)
        monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", tmp_path / "live" / "CIN")
        (tmp_path / "live" / "CIN").mkdir(parents=True)
        set_db_path(data_dir / "dispatch.db")
        try:
            yield SimpleNamespace(root=tmp_path / "live", data_dir=data_dir)
        finally:
            set_db_path(None)

    @pytest.fixture()
    def seeded_collapsed(self, collapsed):
        load = dispatch_svc.create_load(customer="Collapsed Layout Co")
        evidence = dispatch_svc.attach_evidence(
            load["load_id"], file_data=EVIDENCE_BYTES, original_filename="pod.pdf",
        )
        from portal.models import library as portal_library

        portal_library.add_record("broker", "Same-Directory Broker")
        return SimpleNamespace(load=load, evidence=evidence)

    def test_shared_directory_is_stored_once(self, tmp_path, seeded_collapsed):
        result = backup_engine.create_backup(tmp_path / "backups")
        paths = [entry["path"] for entry in result.manifest["files"]]
        assert len(paths) == len(set(paths))
        assert sum(1 for p in paths if p.endswith("library.json")) == 1
        assert result.ok is True

    def test_collapsed_roots_share_one_restored_directory(self, tmp_path, seeded_collapsed):
        result = backup_engine.create_backup(tmp_path / "backups")
        restored = backup_engine.restore(result.archive_path, tmp_path / "restored")
        assert restored.env["PORTAL_DATA_DIR"] == restored.env["DISPATCH_MEMORY_ROOT"]
        assert restored.env["PORTAL_DATA_DIR"] == restored.env["DISPATCH_ARCHIVE_ROOT"]
        assert Path(restored.env["PORTAL_UPLOAD_DIR"]).parent == Path(
            restored.env["PORTAL_DATA_DIR"]
        )

    def test_data_comes_back_from_the_collapsed_layout(
        self, tmp_path, seeded_collapsed, collapsed, monkeypatch
    ):
        result = backup_engine.create_backup(tmp_path / "backups")
        shutil.rmtree(collapsed.root)
        restored = backup_engine.restore(result.archive_path, tmp_path / "restored")
        _repoint(monkeypatch, restored)

        assert dispatch_svc.get_load(seeded_collapsed.load["load_id"])["customer"] == (
            "Collapsed Layout Co"
        )
        located = dispatch_svc.get_evidence_file(seeded_collapsed.evidence["evidence_id"])
        assert located is not None and located[0].read_bytes() == EVIDENCE_BYTES
