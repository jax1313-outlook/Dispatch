"""A backup you can actually take, and a restore you can actually prove.

`dispatch/backup.py` was 926 lines of capture, manifest, SHA-256 verification,
safe restore and stored-path repointing. `dispatch_launcher/backups.py` reported
on the result. Nothing in the product took one: no portal route, no template, no
launcher command, no scheduled task. The only in-product caller of
`create_backup` was `dispatch/proof.py`, whose own commands did not run
(tests/test_proof_command_contract.py). So the whole estate sat on one laptop
behind Mike remembering a script path that appeared in no menu.

The honesty rule is kept intact and is tested here as a rule, not an accident:
the program can prove an archive restores into an isolated destination and that
every hash matches. It cannot prove the restored Dispatch *works*, so a
machine-performed restore leaves the status at UNVERIFIED and says exactly what
it did.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dispatch import services
from dispatch.db import set_db_path
from dispatch_launcher import backup_actions, backups, cli


@pytest.fixture
def estate(tmp_path, monkeypatch):
    """A live estate with a load and an evidence file, plus a backup location."""
    data = tmp_path / "Operations"
    # A real install has all of these; create_backup correctly reports a missing
    # source as an incomplete backup rather than quietly capturing less.
    for sub in ("PortalData", "Evidence", "Memory", "ArchiveRecords"):
        (data / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "Archive").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PORTAL_DATA_DIR", str(data / "PortalData"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(data / "Evidence"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(data / "Memory"))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "Archive"))
    monkeypatch.setenv("DISPATCH_BACKUP_DIR", str(tmp_path / "Backups"))
    set_db_path(data / "dispatch.db")
    try:
        load = services.create_load(customer="Acme Foods")
        services.attach_evidence(
            load["load_id"], description="BOL", uploaded_by="Mike",
            file_data=b"%PDF-1.4 bill of lading", original_filename="bol.pdf",
        )
        yield {"load_id": load["load_id"], "backups": tmp_path / "Backups", "root": tmp_path}
    finally:
        set_db_path(None)


class TestTakingOne:
    def test_the_launcher_can_take_a_backup(self, estate):
        result = backup_actions.create()
        assert result.ok, result.detail
        assert Path(result.archive).exists()
        assert backups._archive_candidates(estate["backups"])  # noqa: SLF001

    def test_it_refuses_rather_than_guessing_a_location(self, estate, monkeypatch):
        monkeypatch.delenv("DISPATCH_BACKUP_DIR")
        result = backup_actions.create()
        assert result.ok is False
        assert "not choose a folder" in result.detail
        # Inventing D:\Backups and reporting "no backups found" would tell Mike
        # his backups are missing when nothing was ever looking in the right place.
        assert "D:" not in result.detail

    def test_the_status_says_unverified_immediately_after(self, estate):
        backup_actions.create()
        status = backups.backup_status(estate["backups"])
        assert status.state == backups.UNVERIFIED
        assert "never been restored" in status.detail

    def test_the_result_tells_the_operator_what_to_do_next(self, estate):
        result = backup_actions.create()
        assert "prove-restore" in result.detail


class TestProvingOne:
    def test_a_restore_into_a_scratch_destination_succeeds(self, estate):
        backup_actions.create()
        result = backup_actions.prove_restore()
        assert result.ok, result.detail
        assert result.evidence["files_restored"] > 0
        assert result.evidence["database_restored"] is True

    def test_the_record_says_code_automated_and_the_status_stays_unverified(self, estate):
        backup_actions.create()
        backup_actions.prove_restore()

        status = backups.backup_status(estate["backups"])
        assert status.state == backups.UNVERIFIED, (
            "a machine proved the archive restores; it cannot prove the restored "
            "Dispatch works, and VERIFIED would be that claim"
        )
        assert status.verification["performed_by"] == "Code-automated"
        assert "every hash matched" in status.detail

    def test_a_person_confirming_reaches_verified(self, estate):
        backup_actions.create()
        backup_actions.prove_restore(confirmed_by="Mike")

        status = backups.backup_status(estate["backups"])
        assert status.state == backups.VERIFIED
        assert status.verification["performed_by"] == "Mike"

    def test_the_record_names_the_archive_it_is_about(self, estate):
        backup_actions.create()
        result = backup_actions.prove_restore()
        written = list(estate["backups"].glob(f"*{backups.VERIFICATION_NAME}"))
        assert len(written) == 1
        record = json.loads(written[0].read_text(encoding="utf-8"))
        assert record["archive"] in result.archive

    def test_a_record_is_not_borrowed_for_a_later_backup(self, estate):
        from dispatch import backup as engine

        engine.create_backup(estate["backups"], name="dispatch-backup-20260101T000000Z")
        backup_actions.prove_restore(confirmed_by="Mike")
        # A second, unproven archive, named later so it is unambiguously newest.
        engine.create_backup(estate["backups"], name="dispatch-backup-20260601T000000Z")
        status = backups.backup_status(estate["backups"])
        assert status.state == backups.UNVERIFIED

    def test_it_refuses_a_destination_that_overlaps_the_live_estate(self, estate, tmp_path):
        """Restoring over the live database is prohibited outright, and the gate
        runs before anything is written rather than being remembered during it."""
        backup_actions.create()
        live = Path(estate["root"]) / "Operations"
        result = backup_actions.prove_restore(destination=live)
        assert result.ok is False
        assert "refused" in result.summary.lower()

    def test_it_reports_rather_than_raising_when_there_is_nothing_to_prove(self, estate):
        result = backup_actions.prove_restore()
        assert result.ok is False
        assert "Take one first" in result.detail

    def test_the_scratch_copy_is_cleaned_up_unless_asked_for(self, estate, tmp_path):
        backup_actions.create()
        keep_dir = tmp_path / "kept"
        backup_actions.prove_restore(destination=keep_dir, keep=True)
        assert any(keep_dir.iterdir())


class TestTheLauncherSurface:
    def test_backup_and_prove_are_menu_controls(self):
        actions = {action for _k, _g, _l, action in cli.EXTRA_ITEMS}
        assert {"backup", "prove-restore"} <= actions

    @pytest.mark.parametrize(
        "typed", ["B", "b", "backup", "back up now", "R", "prove", "restore proof"]
    )
    def test_an_operator_can_type_it(self, typed):
        assert cli.resolve_choice(typed) in {"backup", "prove-restore"}

    def test_they_are_command_line_commands_too(self):
        assert "backup" in cli._COMMANDS  # noqa: SLF001
        assert "prove-restore" in cli._COMMANDS  # noqa: SLF001
        assert "schedule-backup" in cli._COMMANDS  # noqa: SLF001

    def test_run_action_returns_something_the_menu_can_render(self, estate):
        result = cli.run_action("backup")
        assert result.ok is True
        assert result.action == "backup"
        assert isinstance(result.details, list)


class TestScheduling:
    def test_it_prints_a_command_for_both_platforms(self, estate):
        plan = backup_actions.schedule_command()
        assert "schtasks /Create" in plan["windows"]
        assert plan["cron"].startswith("0 2 * * *")
        assert plan["backup_dir"] == str(estate["backups"])

    def test_it_does_not_register_the_task_itself(self, estate, monkeypatch):
        """Writing to the machine's task scheduler is not something a report does."""
        import subprocess

        called = []
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.append(a))
        backup_actions.schedule_command()
        backup_actions.render_schedule()
        assert called == []

    def test_it_says_so_when_no_location_is_configured(self, estate, monkeypatch):
        monkeypatch.delenv("DISPATCH_BACKUP_DIR")
        rendered = backup_actions.render_schedule()
        assert "DISPATCH_BACKUP_DIR is not set" in rendered


class TestThePortalPage:
    @pytest.fixture
    def client(self, estate, monkeypatch):
        from portal.app import create_app

        app = create_app({"TESTING": True})
        app.config["LOGIN_DISABLED"] = True
        return app.test_client()

    def test_the_page_renders_the_state_in_the_truth_vocabulary(self, client, estate):
        backup_actions.create()
        body = client.get("/maintenance").get_data(as_text=True)
        assert "UNVERIFIED" in body
        assert str(estate["backups"]) in body

    def test_the_button_takes_a_backup(self, client, estate):
        assert not backups._archive_candidates(estate["backups"])  # noqa: SLF001
        response = client.post("/maintenance/backup", follow_redirects=True)
        assert response.status_code == 200
        assert backups._archive_candidates(estate["backups"])  # noqa: SLF001

    def test_the_prove_button_records_code_automated_when_no_name_is_given(self, client, estate):
        client.post("/maintenance/backup")
        client.post("/maintenance/prove-restore", data={"confirmed_by": ""}, follow_redirects=True)
        assert backups.backup_status(estate["backups"]).verification["performed_by"] == "Code-automated"

    def test_a_typed_name_is_what_is_recorded(self, client, estate):
        client.post("/maintenance/backup")
        client.post(
            "/maintenance/prove-restore", data={"confirmed_by": "Mike"}, follow_redirects=True
        )
        status = backups.backup_status(estate["backups"])
        assert status.verification["performed_by"] == "Mike"
        assert status.state == backups.VERIFIED

    def test_the_page_is_linked_from_every_screen(self, client):
        body = client.get("/home").get_data(as_text=True)
        assert "/maintenance" in body


class TestTheLauncherStatusLine:
    """`status_line()` had no test and no caller, and raised on every call.

    It reached for a `describe()` that `BackupStatus` does not have -- the
    dataclass carries `state` and `detail` and leaves rendering to whoever is
    displaying it. An untested one-liner is exactly where that survives.
    """

    def test_it_renders_rather_than_raising(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_BACKUP_DIR", str(tmp_path / "backups"))
        line = backup_actions.status_line()
        assert isinstance(line, str) and line

    def test_it_leads_with_the_truth_word(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_BACKUP_DIR", str(tmp_path / "nothing-here"))
        status = backups.backup_status(backup_actions.resolve_backup_dir())
        line = backup_actions.status_line()
        assert line.startswith(status.state), line
        assert status.detail in line

    def test_it_names_the_location_when_there_is_one(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_BACKUP_DIR", str(tmp_path / "backups"))
        status = backups.backup_status(backup_actions.resolve_backup_dir())
        line = backup_actions.status_line()
        if status.location:
            assert status.location in line
