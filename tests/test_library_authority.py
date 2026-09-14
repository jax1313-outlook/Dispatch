"""The Portal's Library routes over the authoritative Library catalog, and its backup.

Owner ruling, 2026-09-13: the separate Library repository is the authoritative Library and
`D:\\Memory` its shelf; Dispatch and Portal consume it through bounded interfaces. These tests hold
the Portal to that with the real Library package (DISPATCH_LIBRARY_SRC, or a sibling checkout):

  * every existing Library route still answers, in the shape it always has;
  * nothing is written to library.json, in the data directory or the shelf, in catalog mode;
  * a placement needs a person and an object type, and a refusal becomes a Library notice;
  * a machine record becomes a durable Library candidate the Library validates before approval;
  * edits and deletions are refused, because the Library never does either;
  * the catalog survives a backup, the loss of the live estate, and a restore.

Skipped, loudly, when the Library package is not on this machine.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

import cin_lite.archive as cin_archive
from dispatch import backup as backup_engine
from dispatch import services as dispatch_svc
from dispatch.db import set_db_path

_SRC = os.environ.get("DISPATCH_LIBRARY_SRC") or str(Path(__file__).resolve().parents[2] / "Library" / "src")
if Path(_SRC, "dispatch_library", "catalog").is_dir() and _SRC not in sys.path:
    sys.path.insert(0, _SRC)
dispatch_library = pytest.importorskip("dispatch_library.catalog", reason="the Library repository is not on this machine")

PERSON = "Certification Operator"


@pytest.fixture()
def live(tmp_path, monkeypatch):
    root = tmp_path / "live"
    paths = {name: root / name for name in ("PortalData", "Memory", "ArchiveRecords", "CIN", "Library")}
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PORTAL_DATA_DIR", str(paths["PortalData"]))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(paths["PortalData"] / "uploads"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(paths["Memory"]))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(paths["ArchiveRecords"]))
    monkeypatch.setenv("DISPATCH_LIBRARY_CATALOG", str(paths["Library"] / "catalog.db"))
    monkeypatch.setattr(cin_archive, "ARCHIVE_ROOT", paths["CIN"])
    set_db_path(paths["PortalData"] / "dispatch.db")
    try:
        yield paths
    finally:
        set_db_path(None)


@pytest.fixture()
def client(live):
    from portal.app import create_app

    return create_app({"TESTING": True, "SECRET_KEY": "test"}).test_client()


def _no_projection_files(live):
    for root in (live["PortalData"], live["Memory"]):
        assert not (root / "library.json").exists(), f"library.json written in {root}"
    # Uploaded documents are kept under the portal data directory on this branch; never in the shelf.
    assert not (live["Memory"] / "LibraryDocuments").exists()


class TestTheRoutesOverTheCatalog:
    def test_human_placement_needs_a_type_and_a_person(self, client, live):
        refused = client.post("/api/library/add", json={"section": "company", "name": "W-9", "accepted_by": PERSON})
        assert refused.status_code == 400
        assert "object_type" in refused.get_json()["error"]

        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        notices = lib.notices()
        lib.close()
        assert [(n["notice_type"], n["missing_field"]) for n in notices] == [("MISSING_FIELD", "object_type")]

        nameless = client.post("/api/library/add", json={"section": "company", "name": "W-9",
                                                         "object_type": "COMPANY_CREDENTIAL"})
        assert nameless.status_code == 400

        joe = client.post("/api/library/add", json={"section": "company", "name": "W-9", "accepted_by": "Joe",
                                                    "object_type": "COMPANY_CREDENTIAL"})
        assert joe.status_code == 400 and "system identity" in joe.get_json()["error"]

        placed = client.post("/api/library/add", json={
            "section": "company", "name": "W-9", "content": "W-9 on file", "accepted_by": "Mike Zachary",
            "object_type": "COMPANY_CREDENTIAL", "capture_channel": "JOE"})
        assert placed.status_code == 200, placed.get_json()
        record = placed.get_json()["record"]
        assert (record["status"], record["accepted_by"], record["authority"]) == ("approved", "Mike Zachary", "library_catalog")
        assert record["metadata"]["capture_channel"] == "JOE"
        _no_projection_files(live)

    def test_pages_and_asset_checks_read_the_catalog(self, client, live):
        client.post("/api/library/add", json={"section": "company", "name": "Insurance", "content": "COI",
                                              "accepted_by": PERSON, "object_type": "COMPANY_CREDENTIAL"})
        from portal.models import library as lib_model

        assert "Insurance" in lib_model.get_available_company_assets()
        assert "Insurance" not in lib_model.get_missing_company_assets()
        assert [r["name"] for r in lib_model.get_section("company")] == ["Insurance"]
        assert client.get("/library").status_code in (200, 302)

        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        lib.set_lifecycle("PORTAL-COMPANY-INSURANCE", "REVIEW_DUE")
        lib.close()
        assert "Insurance" in lib_model.get_missing_company_assets(), "a review-due credential is not available"
        _no_projection_files(live)

    def test_intelligence_promotion_is_a_durable_candidate_validated_before_approval(self, client, live):
        from portal.models import intelligence

        intel = intelligence.create_record("broker", "Tidewater Logistics", "Quick pay, net 30")
        candidate = intelligence.promote_to_candidate(intel["id"])
        assert (candidate["status"], candidate["authority"]) == ("pending_review", "library_catalog")

        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        assert [c.candidate_id for c in lib.pending_candidates()] == [candidate["id"]]
        lib.close()

        unvalidated = client.post("/api/library/review", json={"record_id": candidate["id"], "approve": True,
                                                                "reviewed_by": "Mike Zachary"})
        assert unvalidated.status_code == 400
        assert "not validated" in unvalidated.get_json()["error"]

        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        lib.confirm_object_type(candidate["id"], "VALIDATED_INTELLIGENCE_SUMMARY", "Intelligence")
        lib.close()

        system = client.post("/api/library/review", json={"record_id": candidate["id"], "approve": True,
                                                           "reviewed_by": "Email Helper"})
        assert system.status_code == 400

        approved = client.post("/api/library/review", json={"record_id": candidate["id"], "approve": True,
                                                             "reviewed_by": "Mike Zachary"})
        assert approved.status_code == 200, approved.get_json()
        record = approved.get_json()["record"]
        assert (record["status"], record["accepted_by"], record["submitted_by"]) == ("approved", "Mike Zachary", "machine")
        _no_projection_files(live)

    def test_dispatch_machine_records_need_a_mission_record(self, client, live):
        bare = client.post("/api/library/add", json={"section": "location_intelligence", "name": "Dock 7",
                                                     "submitted_by": "machine"})
        assert bare.status_code == 400
        tied = client.post("/api/library/add", json={"section": "location_intelligence", "name": "Dock 7",
                                                     "submitted_by": "machine",
                                                     "metadata": {"mission_record_id": "MR-LOAD-0001"}})
        assert tied.status_code == 200 and tied.get_json()["record"]["status"] == "pending_review"

    def test_edit_and_delete_are_refused_not_silently_done(self, client, live):
        client.post("/api/library/add", json={"section": "broker", "name": "TQL", "content": "net 30",
                                              "accepted_by": PERSON, "object_type": "VALIDATED_INTELLIGENCE_SUMMARY"})
        for route in ("/api/library/update", "/api/library/delete"):
            response = client.post(route, json={"record_id": "PORTAL-BROKER-TQL", "name": "changed"})
            assert response.status_code == 409, route
        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        assert lib.current("PORTAL-BROKER-TQL").body_or_uri == "net 30"
        lib.close()

    def test_the_intelligence_section_has_no_collection_and_says_so(self, client, live):
        response = client.post("/api/library/add", json={"section": "intelligence", "name": "x", "accepted_by": PERSON,
                                                         "object_type": "VALIDATED_INTELLIGENCE_SUMMARY"})
        assert response.status_code == 400 and "no Library collection" in response.get_json()["error"]

    def test_a_configured_catalog_without_the_library_refuses_instead_of_falling_back(self, live, monkeypatch):
        import builtins

        from portal.models import library as lib_model

        real_import = builtins.__import__

        def no_library(name, *args, **kwargs):
            if name.startswith("dispatch_library"):
                raise ImportError("simulated: Library repository not installed")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_library)
        with pytest.raises(lib_model.LibraryAuthorityError, match="second Library"):
            lib_model.get_all()
        _no_projection_files(live)


PDF = b"%PDF-1.4 certificate of insurance, test bytes"


class TestDocumentsOverTheCatalog:
    """joe/capture-to-card's document upload, contained: bytes kept under the portal data
    directory, the placement accepted by the Library with a person and a type."""

    def _upload(self, client, **form):
        import io

        data = {"section": "company", "name": "Insurance", "file": (io.BytesIO(PDF), "coi.pdf")}
        data.update(form)
        return client.post("/api/library/upload", data=data, content_type="multipart/form-data")

    def test_upload_places_in_the_library_and_downloads(self, client, live):
        resp = self._upload(client, accepted_by="Mike Zachary", object_type="COMPANY_CREDENTIAL")
        assert resp.status_code == 201, resp.get_json()
        record = resp.get_json()["record"]
        assert (record["authority"], record["accepted_by"]) == ("library_catalog", "Mike Zachary")
        assert record["metadata"]["document"] and record["metadata"]["sha256"]
        got = client.get(f"/api/library/document/{record['id']}")
        assert (got.status_code, got.data) == (200, PDF)
        assert (live["PortalData"] / "LibraryDocuments" / record["metadata"]["document"]).is_file()
        from portal.models import library as lib_model
        assert "Insurance" in lib_model.get_available_company_assets()
        _no_projection_files(live)

    def test_a_refused_upload_leaves_no_file_and_no_object(self, client, live):
        untyped = self._upload(client, accepted_by="Mike Zachary")
        assert untyped.status_code == 400 and "object_type" in untyped.get_json()["error"]
        nameless = self._upload(client, object_type="COMPANY_CREDENTIAL")
        assert nameless.status_code == 400
        joe = self._upload(client, accepted_by="Joe", object_type="COMPANY_CREDENTIAL")
        assert joe.status_code == 400
        documents = live["PortalData"] / "LibraryDocuments"
        assert not documents.exists() or list(documents.iterdir()) == []
        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"])
        assert lib.list_current() == []
        lib.close()
        _no_projection_files(live)


class TestLegacyDocumentsStayOutOfTheShelf:
    def test_legacy_documents_live_in_the_portal_data_directory(self, live, monkeypatch):
        monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG")
        from portal.models import library as lib_model

        record = lib_model.add_document("company", "W-9", PDF, "w9.pdf")
        path = lib_model.document_path(record["id"])
        assert path.parent == live["PortalData"] / "LibraryDocuments"
        assert (live["PortalData"] / "library.json").is_file()
        assert list(live["Memory"].iterdir()) == []

    def test_legacy_documents_refuse_when_the_data_directory_is_the_shelf(self, live, monkeypatch):
        monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG")
        monkeypatch.setenv("PORTAL_DATA_DIR", str(live["Memory"]))
        from portal.models import library as lib_model

        with pytest.raises(lib_model.LibraryProjectionError):
            lib_model.add_document("company", "W-9", PDF, "w9.pdf")
        assert list(live["Memory"].iterdir()) == []


class TestTheCatalogIsBackedUp:
    def test_round_trip_of_a_live_wal_catalog(self, live, tmp_path):
        dispatch_svc.create_load(customer="Northbound Freight")
        lib = dispatch_library.open_library(os.environ["DISPATCH_LIBRARY_CATALOG"], memory_root=live["Memory"])
        lib.ingest_human_document("w9", "Company", "W-9", "W-9 on file", PERSON, object_type="COMPANY_CREDENTIAL")
        lib.ingest_human_document("w9", "Company", "W-9", "W-9 2026", PERSON)
        lib.catalog.submit_candidate(submitted_by_role="INTELLIGENCE", source_type="finding", collection="Reference",
                                     proposed_object_code="CAND-1", proposed_title="t", proposed_body_or_reference="b",
                                     source_finding_id="f-1")
        catalog_file = Path(os.environ["DISPATCH_LIBRARY_CATALOG"])
        assert Path(str(catalog_file) + "-wal").exists(), "the test must exercise uncheckpointed WAL content"

        result = backup_engine.create_backup(tmp_path / "backups")
        lib.close()
        assert result.ok, result.absent_sources
        meta = result.manifest["library_catalog"]
        assert (meta["present"], meta["schema_version"], meta["integrity_check"]) == (True, 3, "ok")
        assert meta["row_counts"]["library_version"] == 2
        paths = [e["path"] for e in result.manifest["files"]]
        assert meta["archive_path"] in paths
        assert not any(p.endswith(("catalog.db-wal", "catalog.db-shm")) for p in paths)
        assert backup_engine.verify(result.archive_path).ok

        shutil.rmtree(tmp_path / "live")  # the disk failure

        restored = backup_engine.restore(result.archive_path, tmp_path / "restored")
        restored_catalog = restored.env["DISPATCH_LIBRARY_CATALOG"]
        with sqlite3.connect(restored_catalog) as check:
            assert check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        back = dispatch_library.open_library(restored_catalog)
        assert back.current("w9").version == 2
        assert [o.body_or_uri for o in back.history("w9")] == ["W-9 on file", "W-9 2026"]
        assert [c.proposed_object_code for c in back.pending_candidates()] == ["CAND-1"]
        back.close()

    def test_configured_but_missing_is_loud(self, live, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_LIBRARY_CATALOG", str(tmp_path / "nowhere" / "catalog.db"))
        dispatch_svc.create_load(customer="Northbound Freight")
        result = backup_engine.create_backup(tmp_path / "backups", dry_run=True)
        assert not result.ok
        assert any(a["roles"] == "library_catalog" for a in result.absent_sources)

    def test_unconfigured_is_recorded_not_hidden(self, live, tmp_path, monkeypatch):
        monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG")
        dispatch_svc.create_load(customer="Northbound Freight")
        result = backup_engine.create_backup(tmp_path / "backups", dry_run=True)
        assert result.manifest["library_catalog"]["configured"] is False
        assert any("Library catalog not configured" in n for n in result.notes)
