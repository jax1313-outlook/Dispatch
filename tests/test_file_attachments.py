"""Tests for document file attachments feature."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from dispatch.db import set_db_path
from dispatch.models import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    EVIDENCE_TYPES,
    EvidenceItem,
)
from dispatch import services, store


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


def _make_load(**kw) -> dict:
    defaults = {"customer": "Test Co", "pickup_location": "A", "delivery_location": "B"}
    defaults.update(kw)
    return services.create_load(**defaults)


# ── Model tests ──────────────────────────────────────────────────────


class TestEvidenceModel:
    def test_new_fields_defaults(self):
        ev = EvidenceItem(load_id="L-1")
        assert ev.original_filename == ""
        assert ev.file_size == 0
        assert ev.mime_type == ""

    def test_new_fields_set(self):
        ev = EvidenceItem(
            load_id="L-1",
            original_filename="test.pdf",
            file_size=1024,
            mime_type="application/pdf",
        )
        assert ev.original_filename == "test.pdf"
        assert ev.file_size == 1024
        assert ev.mime_type == "application/pdf"

    def test_to_dict_includes_new_fields(self):
        ev = EvidenceItem(load_id="L-1", original_filename="doc.xlsx")
        d = ev.to_dict()
        assert "original_filename" in d
        assert "file_size" in d
        assert "mime_type" in d

    def test_compute_checksum(self):
        ev = EvidenceItem(load_id="L-1")
        cs = ev.compute_checksum(b"hello world")
        assert len(cs) == 64
        assert ev.checksum == cs

    def test_allowed_extensions_populated(self):
        assert "pdf" in ALLOWED_EXTENSIONS
        assert "png" in ALLOWED_EXTENSIONS
        assert "docx" in ALLOWED_EXTENSIONS
        assert "exe" not in ALLOWED_EXTENSIONS

    def test_max_file_size(self):
        assert MAX_FILE_SIZE == 25 * 1024 * 1024


# ── Store tests ──────────────────────────────────────────────────────


class TestEvidenceStore:
    def test_create_with_file_metadata(self):
        load = _make_load()
        ev = EvidenceItem(
            load_id=load["load_id"],
            original_filename="bol.pdf",
            file_size=2048,
            mime_type="application/pdf",
        )
        result = store.create_evidence(ev)
        assert result["original_filename"] == "bol.pdf"
        assert result["file_size"] == 2048
        assert result["mime_type"] == "application/pdf"

    def test_get_includes_file_metadata(self):
        load = _make_load()
        ev = EvidenceItem(
            load_id=load["load_id"],
            original_filename="photo.jpg",
            file_size=5000,
            mime_type="image/jpeg",
        )
        store.create_evidence(ev)
        fetched = store.get_evidence(ev.evidence_id)
        assert fetched["original_filename"] == "photo.jpg"
        assert fetched["file_size"] == 5000
        assert fetched["mime_type"] == "image/jpeg"

    def test_update_file_path_allowed(self):
        load = _make_load()
        ev = EvidenceItem(load_id=load["load_id"])
        store.create_evidence(ev)
        updated = store.update_evidence(ev.evidence_id, file_path="/new/path.pdf")
        assert updated["file_path"] == "/new/path.pdf"

    def test_update_original_filename_allowed(self):
        load = _make_load()
        ev = EvidenceItem(load_id=load["load_id"])
        store.create_evidence(ev)
        updated = store.update_evidence(ev.evidence_id, original_filename="renamed.pdf")
        assert updated["original_filename"] == "renamed.pdf"

    def test_update_checksum_allowed(self):
        load = _make_load()
        ev = EvidenceItem(load_id=load["load_id"])
        store.create_evidence(ev)
        updated = store.update_evidence(ev.evidence_id, checksum="abc123")
        assert updated["checksum"] == "abc123"

    def test_list_includes_file_metadata(self):
        load = _make_load()
        ev = EvidenceItem(
            load_id=load["load_id"],
            original_filename="receipt.png",
            file_size=3000,
        )
        store.create_evidence(ev)
        items = store.list_evidence(load["load_id"])
        assert len(items) == 1
        assert items[0]["original_filename"] == "receipt.png"

    def test_delete_evidence(self):
        load = _make_load()
        ev = EvidenceItem(load_id=load["load_id"])
        store.create_evidence(ev)
        assert store.delete_evidence(ev.evidence_id) is True
        assert store.get_evidence(ev.evidence_id) is None


# ── Service tests ────────────────────────────────────────────────────


class TestEvidenceService:
    def test_attach_without_file(self):
        load = _make_load()
        ev = services.attach_evidence(
            load_id=load["load_id"],
            evidence_type="document",
            description="Manual reference",
        )
        assert ev["evidence_id"]
        assert ev["original_filename"] == ""
        assert ev["file_size"] == 0

    def test_attach_with_file_data(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        data = b"fake pdf content here"
        ev = services.attach_evidence(
            load_id=load["load_id"],
            evidence_type="bol",
            description="Bill of lading",
            file_data=data,
            original_filename="bol_scan.pdf",
        )
        assert ev["original_filename"] == "bol_scan.pdf"
        assert ev["file_size"] == len(data)
        assert ev["mime_type"] == "application/pdf"
        assert ev["checksum"]
        assert ev["file_path"]
        assert Path(ev["file_path"]).is_file()

    def test_attach_rejects_bad_extension(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        with pytest.raises(ValueError, match="not allowed"):
            services.attach_evidence(
                load_id=load["load_id"],
                file_data=b"malicious",
                original_filename="evil.exe",
            )

    def test_attach_rejects_oversized(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        with pytest.raises(ValueError, match="exceeds"):
            services.attach_evidence(
                load_id=load["load_id"],
                file_data=b"x" * (MAX_FILE_SIZE + 1),
                original_filename="huge.pdf",
            )

    def test_attach_load_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            services.attach_evidence(load_id="FAKE-ID", file_data=b"data", original_filename="a.pdf")

    def test_get_evidence_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        ev = services.attach_evidence(
            load_id=load["load_id"],
            file_data=b"test content",
            original_filename="report.pdf",
        )
        result = services.get_evidence_file(ev["evidence_id"])
        assert result is not None
        path, name = result
        assert path.is_file()
        assert name == "report.pdf"
        assert path.read_bytes() == b"test content"

    def test_get_evidence_file_not_found(self):
        assert services.get_evidence_file("FAKE-ID") is None

    def test_get_evidence_file_no_file_path(self):
        load = _make_load()
        ev = services.attach_evidence(
            load_id=load["load_id"],
            description="No file",
        )
        assert services.get_evidence_file(ev["evidence_id"]) is None

    def test_delete_removes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        ev = services.attach_evidence(
            load_id=load["load_id"],
            file_data=b"delete me",
            original_filename="temp.pdf",
        )
        file_path = Path(ev["file_path"])
        assert file_path.is_file()
        services.delete_evidence(ev["evidence_id"])
        assert not file_path.is_file()

    def test_delete_without_file(self):
        load = _make_load()
        ev = services.attach_evidence(
            load_id=load["load_id"],
            description="No file attached",
        )
        assert services.delete_evidence(ev["evidence_id"]) is True

    def test_upload_dir_created(self, tmp_path, monkeypatch):
        upload_dir = tmp_path / "new_uploads"
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(upload_dir))
        assert not upload_dir.exists()
        load = _make_load()
        services.attach_evidence(
            load_id=load["load_id"],
            file_data=b"create dir",
            original_filename="doc.pdf",
        )
        assert upload_dir.exists()

    def test_multiple_files_same_load(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
        load = _make_load()
        ev1 = services.attach_evidence(
            load_id=load["load_id"],
            file_data=b"file1",
            original_filename="bol.pdf",
            evidence_type="bol",
        )
        ev2 = services.attach_evidence(
            load_id=load["load_id"],
            file_data=b"file2",
            original_filename="pod.jpg",
            evidence_type="pod",
        )
        items = services.list_evidence(load["load_id"])
        assert len(items) == 2
        assert {i["original_filename"] for i in items} == {"bol.pdf", "pod.jpg"}


# ── API tests ────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    from portal.app import create_app
    app = create_app({"TESTING": True, "UPLOAD_FOLDER": str(tmp_path / "uploads")})
    with app.test_client() as c:
        yield c


class TestEvidenceAPI:
    def _create_load(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "API Co"})
        return resp.get_json()["load"]["load_id"]

    def test_upload_file(self, client):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"pdf content"), "invoice.pdf"),
            "evidence_type": "document",
            "description": "Invoice scan",
        }
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["evidence"]["original_filename"] == "invoice.pdf"
        assert body["evidence"]["file_size"] == len(b"pdf content")
        assert body["evidence"]["mime_type"] == "application/pdf"

    def test_upload_bad_extension(self, client):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"bad"), "virus.exe"),
            "evidence_type": "document",
        }
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "not allowed" in resp.get_json()["error"]

    def test_upload_bad_evidence_type(self, client):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"data"), "doc.pdf"),
            "evidence_type": "invalid_type",
        }
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_json_attach_still_works(self, client):
        load_id = self._create_load(client)
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            json={"evidence_type": "document", "description": "Manual ref"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["evidence"]["description"] == "Manual ref"
        assert resp.get_json()["evidence"]["original_filename"] == ""

    def test_download_file(self, client):
        load_id = self._create_load(client)
        content = b"downloadable content"
        data = {
            "file": (io.BytesIO(content), "report.pdf"),
            "evidence_type": "document",
        }
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        ev_id = resp.get_json()["evidence"]["evidence_id"]
        dl = client.get(f"/api/dispatch/evidence/{ev_id}/download")
        assert dl.status_code == 200
        assert dl.data == content
        assert "report.pdf" in dl.headers.get("Content-Disposition", "")

    def test_download_not_found(self, client):
        resp = client.get("/api/dispatch/evidence/FAKE-ID/download")
        assert resp.status_code == 404

    def test_download_no_file_attached(self, client):
        load_id = self._create_load(client)
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            json={"evidence_type": "document", "description": "No file"},
        )
        ev_id = resp.get_json()["evidence"]["evidence_id"]
        dl = client.get(f"/api/dispatch/evidence/{ev_id}/download")
        assert dl.status_code == 404

    def test_delete_removes_file_via_api(self, client):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"delete me"), "temp.pdf"),
            "evidence_type": "document",
        }
        resp = client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        ev = resp.get_json()["evidence"]
        file_path = Path(ev["file_path"])
        assert file_path.is_file()
        del_resp = client.delete(f"/api/dispatch/evidence/{ev['evidence_id']}")
        assert del_resp.status_code == 200
        assert not file_path.is_file()

    def test_list_evidence_shows_file_metadata(self, client):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"list test"), "sample.png"),
            "evidence_type": "photo",
        }
        client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        resp = client.get(f"/api/dispatch/loads/{load_id}/evidence")
        items = resp.get_json()["evidence"]
        assert len(items) == 1
        assert items[0]["original_filename"] == "sample.png"

    def test_upload_image_types(self, client):
        load_id = self._create_load(client)
        for ext, etype in [("jpg", "photo"), ("png", "photo"), ("gif", "photo")]:
            data = {
                "file": (io.BytesIO(b"img"), f"pic.{ext}"),
                "evidence_type": etype,
            }
            resp = client.post(
                f"/api/dispatch/loads/{load_id}/evidence",
                data=data,
                content_type="multipart/form-data",
            )
            assert resp.status_code == 201


# ── Template tests ───────────────────────────────────────────────────


class TestEvidenceTemplate:
    def _create_load_with_evidence(self, client, tmp_path):
        load_id = self._create_load(client)
        data = {
            "file": (io.BytesIO(b"test file"), "attached.pdf"),
            "evidence_type": "bol",
            "description": "Test BOL",
        }
        client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            data=data,
            content_type="multipart/form-data",
        )
        return load_id

    def _create_load(self, client):
        resp = client.post("/api/dispatch/loads", json={"customer": "Tmpl Co"})
        return resp.get_json()["load"]["load_id"]

    def test_evidence_section_has_file_input(self, client):
        load_id = self._create_load(client)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert 'type="file"' in html
        assert 'enctype="multipart/form-data"' in html
        assert "Max 25 MB" in html

    def test_evidence_table_shows_filename(self, client, tmp_path):
        load_id = self._create_load_with_evidence(client, tmp_path)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert "attached.pdf" in html

    def test_evidence_table_shows_download_link(self, client, tmp_path):
        load_id = self._create_load_with_evidence(client, tmp_path)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert "/download" in html
        assert "Download" in html

    def test_evidence_no_file_shows_dash(self, client):
        load_id = self._create_load(client)
        client.post(
            f"/api/dispatch/loads/{load_id}/evidence",
            json={"evidence_type": "document", "description": "No file"},
        )
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert "Evidence (1)" in html

    def test_accepted_file_types_attribute(self, client):
        load_id = self._create_load(client)
        resp = client.get(f"/dispatch/{load_id}")
        html = resp.data.decode()
        assert ".pdf" in html
        assert ".png" in html
        assert ".docx" in html
