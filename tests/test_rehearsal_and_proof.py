"""Tests for rehearsal mode, the readiness checks, and the proof-report system.

Task 2 of the Operational Readiness Mission. These prove software behaviour and
nothing else -- per mission Section 1.9 they are deliberately NOT operational
proof, and one of the tests below asserts that the report generator refuses to
claim otherwise when it runs anywhere but the target machine.
"""

from __future__ import annotations

import json
import os

import pytest

from dispatch import proof, readiness, rehearsal, services, store
from dispatch.db import get_connection


@pytest.fixture(autouse=True)
def _isolated_estate(tmp_path, monkeypatch):
    """Point the database, evidence store, and destinations at tmp_path.

    ``tests/conftest.py``'s ``tmp_archive`` already redirects PORTAL_DATA_DIR;
    this adds the upload directory and gives every test its own backup and
    restore destinations that overlap none of the live paths.
    """
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "Evidence"))
    (tmp_path / "Evidence").mkdir(parents=True, exist_ok=True)
    monkeypatch.delenv(rehearsal.REHEARSAL_ENV_VAR, raising=False)
    backups = tmp_path / "Backups"
    restore = tmp_path / "RestoreProof"
    backups.mkdir()
    restore.mkdir()
    return {"root": tmp_path, "backups": backups, "restore": restore}


def _open(actor="rehearsal-operator", label="test session"):
    return rehearsal.start_session(label=label, actor_id=actor)


# ─────────────────────────────────────────────────────────── sessions


class TestSessions:
    def test_start_session_records_the_actor(self):
        s = _open(actor="mike-workstation")
        assert s["actor_id"] == "mike-workstation"
        assert s["status"] == "OPEN"
        assert s["session_id"].startswith("REH-")
        assert s["rehearsal_label"] == "REHEARSAL"

    def test_actor_is_never_defaulted(self):
        with pytest.raises(rehearsal.RehearsalError, match="Pass actor_id explicitly"):
            rehearsal.start_session(label="x", actor_id="")
        with pytest.raises(rehearsal.RehearsalError):
            rehearsal.start_session(label="x", actor_id="   ")

    @pytest.mark.parametrize("identity", sorted(rehearsal.RESERVED_SYSTEM_IDENTITIES))
    def test_reserved_system_identities_cannot_rehearse(self, identity):
        with pytest.raises(rehearsal.RehearsalError, match="reserved system identity"):
            rehearsal.start_session(label="x", actor_id=identity)
        with pytest.raises(rehearsal.RehearsalError):
            rehearsal.start_session(label="x", actor_id=identity.lower())

    def test_label_is_required(self):
        with pytest.raises(rehearsal.RehearsalError, match="needs a label"):
            rehearsal.start_session(label="  ", actor_id="someone")

    def test_close_session_records_result_and_actor(self):
        s = _open()
        closed = rehearsal.close_session(
            s["session_id"], result="PASSED", actor_id="someone", note="done"
        )
        assert closed["status"] == "PASSED"
        assert closed["result_note"] == "done"
        assert closed["ended_at"]

    def test_close_rejects_a_status_outside_the_vocabulary(self):
        s = _open()
        with pytest.raises(rehearsal.RehearsalError, match="PASSED, FAILED, ABANDONED"):
            rehearsal.close_session(s["session_id"], result="OK", actor_id="someone")
        with pytest.raises(rehearsal.RehearsalError):
            rehearsal.close_session(s["session_id"], result="OPEN", actor_id="someone")

    def test_close_needs_an_actor_and_an_existing_session(self):
        s = _open()
        with pytest.raises(rehearsal.RehearsalError, match="Pass actor_id"):
            rehearsal.close_session(s["session_id"], result="PASSED", actor_id="")
        with pytest.raises(rehearsal.RehearsalError, match="No rehearsal session"):
            rehearsal.close_session("REH-nope", result="PASSED", actor_id="someone")

    def test_list_sessions_filters_by_status(self):
        a = _open(label="one")
        b = _open(label="two")
        rehearsal.close_session(b["session_id"], result="FAILED", actor_id="someone")
        assert {s["session_id"] for s in rehearsal.list_sessions(status="OPEN")} == {
            a["session_id"]
        }
        assert len(rehearsal.list_sessions()) == 2

    def test_get_session_returns_none_for_an_unknown_id(self):
        assert rehearsal.get_session("REH-nope") is None


# ─────────────────────────────────────────────────────────── activation


class TestActivation:
    def test_no_session_is_active_by_default(self):
        assert rehearsal.active_session_id() == ""
        assert rehearsal.is_active() is False

    def test_context_manager_scopes_the_session(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            assert rehearsal.active_session_id() == s["session_id"]
            assert rehearsal.is_active() is True
        assert rehearsal.active_session_id() == ""

    def test_context_manager_resets_even_when_the_body_raises(self):
        s = _open()
        with pytest.raises(RuntimeError):
            with rehearsal.rehearsal_mode(s["session_id"]):
                raise RuntimeError("boom")
        assert rehearsal.active_session_id() == ""

    def test_environment_variable_activates_the_session(self, monkeypatch):
        s = _open()
        monkeypatch.setenv(rehearsal.REHEARSAL_ENV_VAR, s["session_id"])
        assert rehearsal.active_session_id() == s["session_id"]

    def test_context_var_wins_over_the_environment(self, monkeypatch):
        env_session = _open(label="env")
        scoped = _open(label="scoped")
        monkeypatch.setenv(rehearsal.REHEARSAL_ENV_VAR, env_session["session_id"])
        with rehearsal.rehearsal_mode(scoped["session_id"]):
            assert rehearsal.active_session_id() == scoped["session_id"]

    def test_unknown_session_refuses_rather_than_tagging_an_orphan(self):
        with pytest.raises(rehearsal.RehearsalError, match="No rehearsal session"):
            with rehearsal.rehearsal_mode("REH-nope"):
                pass

    def test_closed_session_refuses_new_records(self):
        s = _open()
        rehearsal.close_session(s["session_id"], result="PASSED", actor_id="someone")
        with pytest.raises(rehearsal.RehearsalError, match="is PASSED, not OPEN"):
            with rehearsal.rehearsal_mode(s["session_id"]):
                pass


# ─────────────────────────────────────────────────────────── tagging


class TestTagging:
    def test_records_created_outside_a_session_are_not_tagged(self):
        load = services.create_load(customer="Live Customer")
        assert rehearsal.is_rehearsal("loads", load["load_id"]) is False
        assert rehearsal.session_of("loads", load["load_id"]) == ""
        assert rehearsal.label_for(store.get_load(load["load_id"])) == ""

    def test_every_named_record_type_is_tagged_in_the_write_path(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            driver = services.create_driver(name="D", license_number="L", phone="555-0000")
            truck = services.create_equipment(unit_number="U1", equipment_type="dry_van")
            load = services.create_load(customer="C")
            milestone = services.add_milestone(load["load_id"], "dispatched")
            evidence = services.attach_evidence(
                load["load_id"], file_data=b"x", original_filename="a.txt"
            )
            exc = services.open_exception(load["load_id"], description="e")

        sid = s["session_id"]
        assert rehearsal.session_of("drivers", driver["driver_id"]) == sid
        assert rehearsal.session_of("equipment", truck["equipment_id"]) == sid
        assert rehearsal.session_of("loads", load["load_id"]) == sid
        assert rehearsal.session_of("milestones", milestone["milestone_id"]) == sid
        assert rehearsal.session_of("evidence", evidence["evidence_id"]) == sid
        assert rehearsal.session_of("exceptions", exc["exception_id"]) == sid

    def test_the_stored_record_carries_the_label_not_just_a_side_table(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            load = services.create_load(customer="C")
        row = store.get_load(load["load_id"])
        assert row["rehearsal_session"] == s["session_id"]
        assert rehearsal.label_for(row) == "REHEARSAL"

    def test_tagging_stops_when_the_session_ends(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            tagged = services.create_load(customer="C")
        untagged = services.create_load(customer="C")
        assert rehearsal.is_rehearsal("loads", tagged["load_id"]) is True
        assert rehearsal.is_rehearsal("loads", untagged["load_id"]) is False

    def test_tag_refuses_an_untagged_table(self):
        with pytest.raises(rehearsal.RehearsalError, match="not a rehearsal-tagged table"):
            rehearsal.tag("settlements", "X", session_id="REH-1")
        with pytest.raises(rehearsal.RehearsalError):
            rehearsal.session_of("settlements", "X")

    def test_tag_requires_a_session_id(self):
        with pytest.raises(rehearsal.RehearsalError, match="needs a session_id"):
            rehearsal.tag("loads", "X", session_id="")

    def test_tag_if_active_is_a_no_op_outside_a_session(self):
        load = services.create_load(customer="C")
        assert rehearsal.tag_if_active("loads", load["load_id"]) == ""
        assert rehearsal.is_rehearsal("loads", load["load_id"]) is False

    def test_tag_if_active_applies_the_session(self):
        s = _open()
        load = services.create_load(customer="C")
        with rehearsal.rehearsal_mode(s["session_id"]):
            assert rehearsal.tag_if_active("loads", load["load_id"]) == s["session_id"]
        assert rehearsal.is_rehearsal("loads", load["load_id"]) is True

    def test_label_for_handles_a_missing_record(self):
        assert rehearsal.label_for(None) == ""
        assert rehearsal.label_for({}) == ""


# ─────────────────────────────────────────────────────────── exclusion


class TestExclusion:
    def test_operational_queries_can_exclude_rehearsal_loads(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            services.create_load(customer="Rehearsal Customer")
        services.create_load(customer="Live Customer")

        everything = store.list_loads()
        operational = store.list_loads(include_rehearsal=False)
        assert len(everything) == 2
        assert len(operational) == 1
        assert operational[0]["customer"] == "Live Customer"

    def test_the_default_still_shows_rehearsal_records(self):
        """Excludable, not invisible -- a reviewer must see the labeled record."""
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            services.create_load(customer="Rehearsal Customer")
        assert len(services.list_loads()) == 1
        assert len(services.list_loads(include_rehearsal=False)) == 0

    def test_sql_fragments_qualify_the_column(self):
        assert rehearsal.operational_only() == "rehearsal_session = ''"
        assert rehearsal.operational_only("loads") == "loads.rehearsal_session = ''"
        assert rehearsal.rehearsal_only("loads") == "loads.rehearsal_session != ''"

    def test_filter_rows_excludes_by_the_stored_column(self):
        rows = [{"id": 1, "rehearsal_session": ""}, {"id": 2, "rehearsal_session": "REH-1"}]
        assert rehearsal.filter_rows(rows, include_rehearsal=True) == rows
        assert rehearsal.filter_rows(rows, include_rehearsal=False) == [rows[0]]


# ─────────────────────────────────────────────────────────── purge


class TestPurge:
    def _populate(self):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            load = services.create_load(customer="C")
            services.add_milestone(load["load_id"], "dispatched")
            services.attach_evidence(
                load["load_id"], file_data=b"bytes", original_filename="a.txt"
            )
        return s, load

    def test_plan_purge_reports_and_deletes_nothing(self):
        s, load = self._populate()
        plan = rehearsal.plan_purge(s["session_id"])
        assert plan.counts["loads"] == 1
        assert plan.counts["milestones"] == 1
        assert plan.counts["evidence"] == 1
        assert plan.total == 3
        assert bool(plan) is True
        assert len(plan.evidence_files) == 1
        # Still there.
        assert store.get_load(load["load_id"]) is not None

    def test_plan_purge_of_an_empty_session_is_falsey(self):
        s = _open()
        assert bool(rehearsal.plan_purge(s["session_id"])) is False

    def test_purge_refuses_without_confirmation(self):
        s, load = self._populate()
        with pytest.raises(rehearsal.RehearsalError, match="confirm=True"):
            rehearsal.purge_session(s["session_id"], actor_id="someone")
        assert store.get_load(load["load_id"]) is not None

    def test_purge_refuses_without_an_actor(self):
        s, _ = self._populate()
        with pytest.raises(rehearsal.RehearsalError, match="Pass actor_id"):
            rehearsal.purge_session(s["session_id"], actor_id="", confirm=True)

    def test_purge_removes_only_the_tagged_session_and_leaves_live_data(self):
        s, rehearsal_load = self._populate()
        live = services.create_load(customer="Live Customer")
        services.add_milestone(live["load_id"], "dispatched")

        other = _open(label="another")
        with rehearsal.rehearsal_mode(other["session_id"]):
            other_load = services.create_load(customer="Other Rehearsal")

        rehearsal.purge_session(s["session_id"], actor_id="someone", confirm=True)

        assert store.get_load(rehearsal_load["load_id"]) is None
        assert store.get_load(live["load_id"]) is not None
        assert store.get_load(other_load["load_id"]) is not None
        assert len(store.list_milestones(live["load_id"])) == 1
        assert rehearsal.get_session(s["session_id"])["status"] == "ABANDONED"

    def test_purge_holds_foreign_keys_throughout(self):
        """No PRAGMA foreign_keys=OFF anywhere -- children go before parents."""
        s, _ = self._populate()
        rehearsal.purge_session(s["session_id"], actor_id="someone", confirm=True)
        with get_connection() as conn:
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []

    def test_purge_can_remove_evidence_files_when_asked(self, tmp_path):
        s, _ = self._populate()
        plan = rehearsal.plan_purge(s["session_id"])
        from pathlib import Path

        path = Path(plan.evidence_files[0])
        assert path.is_file()
        rehearsal.purge_session(
            s["session_id"], actor_id="someone", confirm=True, delete_files=True
        )
        assert not path.exists()

    def test_purge_survives_an_already_missing_evidence_file(self):
        s, _ = self._populate()
        from pathlib import Path

        Path(rehearsal.plan_purge(s["session_id"]).evidence_files[0]).unlink()
        rehearsal.purge_session(
            s["session_id"], actor_id="someone", confirm=True, delete_files=True
        )
        assert rehearsal.plan_purge(s["session_id"]).total == 0


# ─────────────────────────────────────────────────────────── surfaces


class TestSurfaces:
    def test_banner_context_is_off_by_default(self):
        ctx = rehearsal.banner_context()
        assert ctx["rehearsal_active"] is False
        assert ctx["rehearsal_session_id"] == ""

    def test_banner_context_names_the_session(self):
        s = _open(label="first rehearsal")
        with rehearsal.rehearsal_mode(s["session_id"]):
            ctx = rehearsal.banner_context()
        assert ctx["rehearsal_active"] is True
        assert ctx["rehearsal_session_id"] == s["session_id"]
        assert ctx["rehearsal_session_label"] == "first rehearsal"
        assert ctx["rehearsal_label"] == "REHEARSAL"

    def test_banner_context_survives_an_id_with_no_session_row(self, monkeypatch):
        monkeypatch.setenv(rehearsal.REHEARSAL_ENV_VAR, "REH-nope")
        ctx = rehearsal.banner_context()
        assert ctx["rehearsal_active"] is True
        assert ctx["rehearsal_session_label"] == ""

    def test_the_portal_renders_no_banner_when_no_rehearsal_is_running(self):
        from portal.app import create_app

        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get("/login").get_data(as_text=True)
        assert "REHEARSAL MODE" not in body

    def test_the_portal_renders_the_banner_during_a_rehearsal(self, monkeypatch):
        from portal.app import create_app

        s = _open(label="banner check")
        monkeypatch.setenv(rehearsal.REHEARSAL_ENV_VAR, s["session_id"])
        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get("/login").get_data(as_text=True)
        assert "REHEARSAL MODE — THIS IS NOT A LIVE MISSION" in body
        assert s["session_id"] in body

    def test_the_driver_login_carries_the_banner_too(self, monkeypatch):
        from portal.app import create_app

        s = _open(label="driver banner")
        monkeypatch.setenv(rehearsal.REHEARSAL_ENV_VAR, s["session_id"])
        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get("/driver/login").get_data(as_text=True)
        assert "REHEARSAL MODE" in body

    def test_a_rehearsal_load_is_badged_outside_its_session(self, monkeypatch):
        """The badge outlives the session -- a rehearsal load opened later still says so."""
        from portal.app import create_app

        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            load = services.create_load(customer="C")
        assert rehearsal.active_session_id() == ""

        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get(f"/dispatch/{load['load_id']}").get_data(as_text=True)
        assert "rehearsal-badge" in body
        assert "REHEARSAL MODE" not in body  # the banner is off; the badge is not

    def test_the_dispatch_list_badges_a_rehearsal_load(self):
        """The list page is where a reviewer scans. An unlabeled row there would
        be a rehearsal load displaying as a live mission at exactly the moment
        nobody is looking closely."""
        from portal.app import create_app

        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            services.create_load(customer="Rehearsal Customer")
        services.create_load(customer="Live Customer")

        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get("/dispatch").get_data(as_text=True)
        assert body.count("rehearsal-badge") == 1

    def test_a_live_load_carries_no_badge(self):
        from portal.app import create_app

        load = services.create_load(customer="Live Customer")
        app = create_app({"TESTING": True})
        with app.test_client() as client:
            body = client.get(f"/dispatch/{load['load_id']}").get_data(as_text=True)
        assert "rehearsal-badge" not in body


# ─────────────────────────────────────────────────────────── readiness


class TestReadiness:
    def test_check_result_refuses_a_word_outside_the_vocabulary(self):
        with pytest.raises(ValueError, match="Section 1.8 truth words"):
            readiness.CheckResult("x", "OK", "detail")
        with pytest.raises(ValueError):
            readiness.CheckResult("x", "PARTIALLY_CONFIGURED", "detail")

    def test_writability_is_proven_by_writing(self, tmp_path):
        target = tmp_path / "fresh"
        target.mkdir()
        result = readiness.check_writable("D", target)
        assert result.status == "CONFIGURED"
        assert result.evidence["write_probe"] == "succeeded"
        # and the probe cleaned up after itself
        assert list(target.iterdir()) == []

    def test_a_missing_directory_is_unconfigured(self, tmp_path):
        result = readiness.check_writable("D", tmp_path / "nope")
        assert result.status == "UNCONFIGURED"
        assert result.ok is False

    def test_a_file_where_a_directory_belongs_is_unavailable(self, tmp_path):
        f = tmp_path / "file"
        f.write_text("x")
        assert readiness.check_writable("D", f).status == "UNAVAILABLE"

    def test_an_unwritable_directory_is_unavailable(self, tmp_path):
        d = tmp_path / "ro"
        d.mkdir()
        d.chmod(0o500)
        try:
            result = readiness.check_writable("D", d)
        finally:
            d.chmod(0o700)
        # Running as root defeats the mode bits; skip the assertion rather than
        # the test, so this file never reports a skip.
        if os.geteuid() != 0:
            assert result.status == "UNAVAILABLE"

    def test_a_destination_inside_a_live_path_is_refused(self, tmp_path):
        live = tmp_path / "live"
        nested = live / "backups"
        nested.mkdir(parents=True)
        result = readiness.check_separate(
            "Backup destination", nested, against={"evidence store": live}
        )
        assert result.status == "UNAVAILABLE"
        assert "overlaps a live path" in result.detail

    def test_separateness_resolves_dot_dot(self, tmp_path):
        live = tmp_path / "live"
        live.mkdir()
        sneaky = tmp_path / "live" / ".." / "live"
        result = readiness.check_separate(
            "Backup destination", sneaky, against={"evidence store": live}
        )
        assert result.status == "UNAVAILABLE"

    def test_a_separate_destination_passes(self, tmp_path):
        live = tmp_path / "live"
        other = tmp_path / "elsewhere"
        live.mkdir()
        other.mkdir()
        result = readiness.check_separate(
            "Backup destination", other, against={"evidence store": live}
        )
        assert result.status == "CONFIGURED"

    def test_no_destination_supplied_is_unconfigured(self):
        result = readiness.check_separate("Backup destination", None, against={})
        assert result.status == "UNCONFIGURED"
        assert "will not choose a destination" in result.detail

    def test_a_missing_destination_is_unconfigured(self, tmp_path):
        result = readiness.check_separate(
            "Backup destination", tmp_path / "nope", against={}
        )
        assert result.status == "UNCONFIGURED"

    def test_restore_destination_must_be_empty(self, tmp_path):
        d = tmp_path / "restore"
        d.mkdir()
        assert readiness.check_restore_destination(d, against={}).status == "CONFIGURED"
        (d / "leftover.txt").write_text("x")
        result = readiness.check_restore_destination(d, against={})
        assert result.status == "UNAVAILABLE"
        assert "not empty" in result.detail
        assert "will not delete files on your machine" in result.detail

    def test_restore_destination_propagates_a_failed_separateness_check(self, tmp_path):
        live = tmp_path / "live"
        nested = live / "restore"
        nested.mkdir(parents=True)
        result = readiness.check_restore_destination(nested, against={"db": live})
        assert result.status == "UNAVAILABLE"

    def test_restore_destination_none_is_unconfigured(self):
        assert readiness.check_restore_destination(None, against={}).status == "UNCONFIGURED"

    def test_the_secret_check_names_settings_and_never_values(self, monkeypatch):
        monkeypatch.setenv("PORTAL_SECRET_KEY", "a-real-value-nobody-published")
        monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "another-real-value")
        ok = readiness.check_secrets_configured()
        assert ok.status == "CONFIGURED"
        assert "a-real-value-nobody-published" not in json.dumps(ok.to_dict())

        monkeypatch.delenv("PORTAL_SECRET_KEY")
        weak = readiness.check_secrets_configured()
        assert weak.status == "UNCONFIGURED"
        assert "PORTAL_SECRET_KEY" in weak.detail
        assert weak.evidence["weak_settings"] == ["PORTAL_SECRET_KEY"]

    def test_the_secret_check_says_so_in_development_mode(self, monkeypatch):
        monkeypatch.delenv("PORTAL_SECRET_KEY", raising=False)
        monkeypatch.setenv("DISPATCH_MODE", "development")
        result = readiness.check_secrets_configured()
        assert result.status == "UNCONFIGURED"
        assert "DISPATCH_MODE is development" in result.detail
        assert result.evidence["development_mode"] is True

    def test_an_absent_evidence_directory_is_created_and_reported_configured(
        self, tmp_path, monkeypatch
    ):
        """Resolving the path creates it, exactly as a real upload would."""
        target = tmp_path / "not-yet"
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(target))
        result = readiness.check_evidence_path()
        assert result.status == "CONFIGURED"
        assert target.is_dir()

    def test_an_uncreatable_evidence_directory_is_unavailable(self, tmp_path, monkeypatch):
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file, not a directory")
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(blocker / "uploads"))
        result = readiness.check_evidence_path()
        assert result.status == "UNAVAILABLE"
        assert "could not create the evidence directory" in result.detail

    def test_an_unreadable_identity_store_is_unavailable(self, monkeypatch):
        from portal.models import identity as identity_model

        def _boom():
            raise OSError("identity store unreadable")

        monkeypatch.setattr(identity_model, "has_any_identity", _boom)
        result = readiness.check_authority_identity()
        assert result.status == "UNAVAILABLE"
        assert "Could not read the identity store" in result.detail

    def test_render_says_so_when_everything_is_configured(self, _isolated_estate, monkeypatch):
        report = readiness.run_readiness_checks()
        for check in report.checks:
            check.status = "CONFIGURED"
        assert "All readiness conditions are CONFIGURED." in readiness.render_readiness(report)

    def test_authority_identity_reports_the_bootstrap_state(self):
        result = readiness.check_authority_identity()
        assert result.status in ("CONFIGURED", "UNCONFIGURED")
        if result.status == "UNCONFIGURED":
            assert "cin-portal-init-admin" in result.detail

    def test_the_full_run_covers_every_section_4_4_condition(self, _isolated_estate):
        report = readiness.run_readiness_checks(
            backup_destination=_isolated_estate["backups"],
            restore_destination=_isolated_estate["restore"],
        )
        names = [c.name for c in report.checks]
        assert names == [
            "Database path",
            "Evidence storage",
            "Backup destination",
            "Restore destination",
            "Secrets",
            "Authority identity",
        ]
        assert report.identity["version"]
        assert report.identity["commit"]

    def test_ready_is_false_while_anything_is_not_configured(self, _isolated_estate):
        report = readiness.run_readiness_checks()
        assert report.ready is False
        assert report.blocking

    def test_render_is_plain_text_and_disclaims_operational_proof(self, _isolated_estate):
        report = readiness.run_readiness_checks(
            backup_destination=_isolated_estate["backups"],
            restore_destination=_isolated_estate["restore"],
        )
        text = readiness.render_readiness(report)
        assert "Dispatch readiness" in text
        assert "not proof that a load has moved through Dispatch" in text

    def test_live_paths_names_every_root(self):
        paths = readiness.live_paths()
        assert set(paths) == {
            "database directory",
            "evidence store",
            "portal data",
            "memory root",
            "archive root",
        }

    def test_application_identity_never_guesses_a_commit(self, monkeypatch):
        import subprocess as sp

        def _fail(*a, **k):
            raise OSError("no git here")

        monkeypatch.setattr(sp, "run", _fail)
        assert readiness.application_commit() == "UNVERIFIED"


# ─────────────────────────────────────────────────────────── proof reports


class TestProofPath:
    def test_the_path_is_the_twenty_steps_in_order(self):
        assert len(proof.PROOF_PATH) == 20
        assert [s.number for s in proof.PROOF_PATH] == list(range(1, 21))
        assert all(s.command for s in proof.PROOF_PATH)

    def test_every_step_starts_not_performed(self):
        run = proof.blank_run()
        assert all(s.performer == "not performed" for s in run.steps)
        assert all(s.status == "ABSENT" for s in run.steps)
        assert run.all_performed is False

    def test_a_step_refuses_a_performer_outside_the_three(self):
        with pytest.raises(ValueError, match="performer must be one of"):
            proof.StepResult(1, "x", performer="Claude")
        with pytest.raises(ValueError):
            proof.StepResult(1, "x", performer="mike")

    def test_a_step_refuses_a_status_outside_the_vocabulary(self):
        with pytest.raises(ValueError, match="Section 1.8 truth words"):
            proof.StepResult(1, "x", status="PASSED")

    def test_outlook_status_is_restricted_to_four_words(self):
        with pytest.raises(ValueError, match="LIVE, SIMULATED"):
            proof.ProofRun(steps=[], outlook_status="CONFIGURED")
        for word in ("LIVE", "SIMULATED", "MANUAL", "ABSENT"):
            proof.ProofRun(steps=[], outlook_status=word)


class TestHeadline:
    def _full(self, machine="MIKE-PC"):
        run = proof.blank_run(machine=machine)
        for step in run.steps:
            step.performer = "Code-automated"
            step.status = "CONFIGURED"
        return run

    def test_an_unrun_path_says_so(self):
        assert proof.blank_run().headline == proof.HEADLINE_NOT_RUN

    def test_a_complete_run_on_a_named_machine_passes(self):
        assert self._full().headline == proof.HEADLINE_PASSED

    def test_a_complete_run_with_no_named_machine_does_not_pass(self):
        """Section 1.9: nothing is OPERATIONALLY PROVEN off the target machine."""
        assert self._full(machine="UNVERIFIED").headline == proof.HEADLINE_NOT_RUN

    def test_a_failure_names_the_step(self):
        run = self._full()
        run.steps[6].status = "UNAVAILABLE"
        assert run.headline == "REHEARSAL FAILED at step 7"

    def test_an_unattempted_step_is_not_a_failure(self):
        run = self._full()
        run.steps[6].performer = "not performed"
        run.steps[6].status = "ABSENT"
        assert run.headline == proof.HEADLINE_NOT_RUN
        assert run.first_failure is None


class TestComparison:
    def test_matching_hashes_report_identical(self):
        a = {"E1": {"sha256": "aa", "status": "CONFIGURED"}}
        result = proof.compare_hashes(a, a)
        assert result["identical"] is True
        assert result["rows"][0]["match"] is True

    def test_differing_hashes_report_the_difference(self):
        a = {"E1": {"sha256": "aa", "status": "CONFIGURED"}}
        b = {"E1": {"sha256": "bb", "status": "CONFIGURED"}}
        result = proof.compare_hashes(a, b)
        assert result["identical"] is False

    def test_an_empty_comparison_is_not_identical(self):
        """Nothing compared is not the same as everything matching."""
        assert proof.compare_hashes({}, {})["identical"] is False

    def test_a_missing_hash_never_counts_as_a_match(self):
        a = {"E1": {"sha256": "", "status": "ABSENT"}}
        assert proof.compare_hashes(a, a)["identical"] is False

    def test_record_comparison_names_missing_and_unexpected(self):
        result = proof.compare_record_ids(
            {"loads": ["A", "B"]}, {"loads": ["B", "C"]}
        )
        row = result["rows"][0]
        assert row["missing"] == ["A"]
        assert row["unexpected"] == ["C"]
        assert result["identical"] is False


class TestEvidenceCollection:
    def test_hashes_every_evidence_file(self):
        load = services.create_load(customer="C")
        ev = services.attach_evidence(
            load["load_id"], file_data=b"contents", original_filename="a.txt"
        )
        hashes = proof.collect_evidence_hashes(load["load_id"])
        assert set(hashes) == {ev["evidence_id"]}
        assert len(hashes[ev["evidence_id"]]["sha256"]) == 64
        assert hashes[ev["evidence_id"]]["status"] == "CONFIGURED"

    def test_a_missing_file_is_reported_absent_never_skipped(self):
        from pathlib import Path

        load = services.create_load(customer="C")
        ev = services.attach_evidence(
            load["load_id"], file_data=b"contents", original_filename="a.txt"
        )
        Path(store.get_evidence(ev["evidence_id"])["file_path"]).unlink()
        hashes = proof.collect_evidence_hashes(load["load_id"])
        assert hashes[ev["evidence_id"]]["status"] == "ABSENT"
        assert hashes[ev["evidence_id"]]["sha256"] == ""

    def test_record_ids_cover_every_related_table(self):
        load = services.create_load(customer="C")
        ids = proof.collect_record_ids(load["load_id"])
        assert set(ids) == {
            "loads", "drivers", "equipment", "milestones",
            "evidence", "exceptions", "pod_packages",
        }

    def test_record_ids_of_an_unknown_load_are_empty(self):
        assert proof.collect_record_ids("LD-nope")["loads"] == []


class TestReportRendering:
    def test_the_template_headline_is_the_honest_one(self):
        text = proof.render_proof_report(proof.template_run())
        assert text.splitlines()[0] == f"# {proof.HEADLINE_NOT_RUN}"

    def test_the_template_states_that_tests_are_not_operational_proof(self):
        text = proof.render_proof_report(proof.template_run())
        assert "not cited here as operational proof" in text

    def test_the_template_prints_the_command_for_every_step(self):
        text = proof.render_proof_report(proof.template_run())
        for step in proof.PROOF_PATH:
            assert step.command.splitlines()[0] in text
        assert text.count("← not performed") == 20

    def test_the_report_carries_version_and_commit(self):
        text = proof.render_proof_report(proof.template_run())
        assert readiness.application_version() in text
        assert "**Application commit:**" in text

    def test_the_report_never_claims_a_mike_attribution(self):
        text = proof.render_proof_report(proof.template_run())
        for phrase in (
            "Verified by Mike Zachary",
            "Approved by Mike Zachary",
            "Accepted by Mike Zachary",
            "Authorized by Mike Zachary",
            "Confirmed by Mike Zachary",
        ):
            assert phrase not in text

    def test_the_report_includes_the_readiness_table_when_present(self, _isolated_estate):
        run = proof.template_run()
        run.readiness = readiness.run_readiness_checks(
            backup_destination=_isolated_estate["backups"],
            restore_destination=_isolated_estate["restore"],
        )
        text = proof.render_proof_report(run)
        assert "## Readiness checks (Section 4.4)" in text
        assert "Restore destination" in text

    def test_write_produces_markdown_and_json(self, tmp_path):
        path = proof.write_proof_report(proof.template_run(), tmp_path / "p" / "PROOF.md")
        assert path.is_file()
        data = json.loads(path.with_suffix(".json").read_text())
        assert data["headline"] == proof.HEADLINE_NOT_RUN
        assert len(data["steps"]) == 20

    def test_a_completed_run_lists_what_mike_performed(self):
        run = proof.template_run()
        for step in run.steps:
            step.performer = "Mike"
            step.status = "CONFIGURED"
        text = proof.render_proof_report(run)
        assert "no step of this path has been performed by Mike" not in text
        assert "Nothing — every step was performed." in text
        assert "← not performed" not in text

    def test_a_failure_note_reaches_the_report(self):
        run = proof.template_run()
        run.failure_note = "the disk filled up"
        assert "the disk filled up" in proof.render_proof_report(run)

    def test_comparisons_render_when_records_exist(self):
        run = proof.template_run()
        run.original_record_ids = {"loads": ["A"]}
        run.restored_record_ids = {"loads": ["A"]}
        run.evidence_hashes = {"E1": {"sha256": "a" * 64, "status": "CONFIGURED"}}
        run.restored_evidence_hashes = {"E1": {"sha256": "a" * 64, "status": "CONFIGURED"}}
        text = proof.render_proof_report(run)
        assert "**Identical:** yes" in text


class TestAutomatedRehearsal:
    def _run(self, estate, **kw):
        return proof.automated_rehearsal(
            actor_id=kw.pop("actor_id", "rehearsal-operator"),
            label=kw.pop("label", "automated test"),
            backup_destination=estate["backups"],
            restore_destination=estate["restore"],
            **kw,
        )

    def test_it_walks_every_automatable_step(self, _isolated_estate):
        run = self._run(_isolated_estate)
        assert run.failure_note == ""
        automatable = [s for s in run.steps if s.number not in proof.NOT_AUTOMATABLE]
        assert all(s.performer == "Code-automated" for s in automatable)
        assert all(s.status == "CONFIGURED" for s in automatable)

    def test_it_cannot_claim_a_pass(self, _isolated_estate):
        """Six steps need a human. That is why they are the ones that matter."""
        run = self._run(_isolated_estate)
        assert run.headline == proof.HEADLINE_NOT_RUN
        for number in proof.NOT_AUTOMATABLE:
            step = next(s for s in run.steps if s.number == number)
            assert step.performer == "not performed"
            assert step.status == "ABSENT"
            assert step.note

    def test_every_record_it_creates_is_tagged(self, _isolated_estate):
        run = self._run(_isolated_estate)
        sid = run.rehearsal_session_id
        plan = rehearsal.plan_purge(sid)
        assert plan.counts["loads"] == 1
        assert plan.counts["drivers"] == 1
        assert plan.counts["equipment"] == 1
        assert plan.counts["evidence"] == 2
        # >= rather than ==: services.add_milestone's status cascade records
        # its own milestones, and those are rehearsal records too.
        assert plan.counts["milestones"] >= len(proof.REHEARSAL_MILESTONES)
        assert store.list_loads(include_rehearsal=False) == []

    def test_the_backup_restores_with_matching_hashes_and_ids(self, _isolated_estate):
        run = self._run(_isolated_estate)
        step20 = next(s for s in run.steps if s.number == 20)
        assert step20.status == "CONFIGURED"
        assert "record identifiers match" in step20.result
        assert "evidence hashes match" in step20.result
        assert proof.compare_hashes(
            run.evidence_hashes, run.restored_evidence_hashes
        )["identical"] is True

    def test_the_read_back_leaves_the_database_pointer_alone(self, _isolated_estate):
        from dispatch import db as dispatch_db

        before = dispatch_db._db_path_override
        self._run(_isolated_estate)
        assert dispatch_db._db_path_override == before

    def test_no_record_it_creates_bears_a_mike_attribution(self, _isolated_estate):
        run = self._run(_isolated_estate, actor_id="rehearsal-operator")
        blob = json.dumps(run.to_dict())
        for phrase in (
            "Verified by Mike Zachary",
            "Approved by Mike Zachary",
            "Accepted by Mike Zachary",
            "Authorized by Mike Zachary",
            "Confirmed by Mike Zachary",
        ):
            assert phrase not in blob

    def test_the_session_closes_passed(self, _isolated_estate):
        run = self._run(_isolated_estate)
        assert rehearsal.get_session(run.rehearsal_session_id)["status"] == "PASSED"

    def test_a_failure_names_the_step_and_closes_the_session_failed(self, _isolated_estate):
        run = proof.automated_rehearsal(
            actor_id="rehearsal-operator",
            label="deliberate failure",
            backup_destination=_isolated_estate["backups"],
            restore_destination=_isolated_estate["restore"],
            equipment_type="not-a-real-equipment-type",
        )
        assert run.headline == "REHEARSAL FAILED at step 4"
        assert "Invalid equipment_type" in run.failure_note
        assert rehearsal.get_session(run.rehearsal_session_id)["status"] == "FAILED"

    def test_it_refuses_a_reserved_actor(self, _isolated_estate):
        with pytest.raises(rehearsal.RehearsalError):
            self._run(_isolated_estate, actor_id="SYSTEM")

    def test_it_runs_without_a_backup_destination(self, _isolated_estate):
        run = proof.automated_rehearsal(
            actor_id="rehearsal-operator", label="no backup"
        )
        assert run.failure_note == ""
        assert next(s for s in run.steps if s.number == 19).status == "ABSENT"
        assert next(s for s in run.steps if s.number == 20).status == "ABSENT"

    def test_the_generated_report_is_readable(self, _isolated_estate, tmp_path):
        run = self._run(_isolated_estate)
        text = proof.render_proof_report(run)
        assert proof.HEADLINE_NOT_RUN in text
        assert run.rehearsal_session_id in text
        assert "Code-automated" in text


# ─────────────────────────────────────────────────────────── the CLI


class TestCLI:
    def _cli(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "scripts" / "dispatch_proof.py"
        spec = importlib.util.spec_from_file_location("dispatch_proof_cli", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_readiness_exits_non_zero_while_something_is_unconfigured(self, capsys):
        assert self._cli().main(["readiness"]) == 1
        assert "Dispatch readiness" in capsys.readouterr().out

    def test_readiness_json(self, capsys, _isolated_estate):
        self._cli().main(["readiness", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["ready"] is False
        assert len(data["checks"]) == 6

    def test_template_writes_the_report(self, tmp_path, capsys):
        out = tmp_path / "PROOF.md"
        assert self._cli().main(["template", "--output", str(out)]) == 0
        assert proof.HEADLINE_NOT_RUN in out.read_text()
        assert "This is a template, not proof" in capsys.readouterr().out

    def test_template_can_include_readiness(self, tmp_path):
        out = tmp_path / "PROOF.md"
        self._cli().main(["template", "--output", str(out), "--with-readiness"])
        assert "Readiness checks (Section 4.4)" in out.read_text()

    def test_rehearse_refuses_when_readiness_fails(self, tmp_path, capsys):
        code = self._cli().main(
            ["rehearse", "--actor", "someone", "--label", "x",
             "--output", str(tmp_path / "P.md")]
        )
        assert code == 2
        assert "Refusing to rehearse" in capsys.readouterr().err
        assert not (tmp_path / "P.md").exists()

    def test_rehearse_runs_when_told_to_ignore_readiness(self, tmp_path, _isolated_estate):
        out = tmp_path / "P.md"
        code = self._cli().main(
            ["rehearse", "--actor", "someone", "--label", "x",
             "--ignore-readiness", "--output", str(out),
             "--backup-destination", str(_isolated_estate["backups"]),
             "--restore-destination", str(_isolated_estate["restore"]),
             "--outlook", "ABSENT"]
        )
        assert code == 0
        assert proof.HEADLINE_NOT_RUN in out.read_text()

    def test_sessions_lists_what_exists(self, capsys):
        cli = self._cli()
        assert cli.main(["sessions"]) == 0
        assert "No rehearsal sessions" in capsys.readouterr().out
        s = _open(label="listed")
        assert cli.main(["sessions", "--status", "OPEN"]) == 0
        assert s["session_id"] in capsys.readouterr().out

    def test_purge_plan_reports_and_deletes_nothing(self, capsys):
        s = _open()
        with rehearsal.rehearsal_mode(s["session_id"]):
            load = services.create_load(customer="C")
        assert self._cli().main(["purge-plan", s["session_id"]]) == 0
        out = capsys.readouterr().out
        assert "Nothing was deleted" in out
        assert "your decision" in out
        assert store.get_load(load["load_id"]) is not None
