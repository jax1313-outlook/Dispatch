"""Documents in the Library, where Publisher can reach them.

Until this existed a Library record held a name and some text. Every asset the
packet manifest asks for -- W-9, insurance, authority, rate sheets, terms -- is a
document, and typing its name was enough to satisfy the missing-asset check.
"""

from __future__ import annotations

import io

import pytest

from dispatch.db import set_db_path
from portal.models import library as lib_model


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


PDF = b"%PDF-1.4 not really a pdf, but it is bytes"


class TestPlacingADocument:
    def test_a_document_is_stored_and_the_record_points_at_it(self):
        record = lib_model.add_document(
            "company", "W-9", PDF, "w9-2026.pdf")

        assert record["name"] == "W-9"
        assert record["status"] == "approved"
        assert record["metadata"]["original_filename"] == "w9-2026.pdf"
        assert record["metadata"]["size_bytes"] == len(PDF)

        path = lib_model.document_path(record["id"])
        assert path is not None
        assert path.read_bytes() == PDF

    def test_the_stored_name_cannot_escape_the_directory(self):
        """A filename is text somebody else chose. The record id names the file
        and only the extension survives."""
        record = lib_model.add_document(
            "company", "Insurance", PDF, "../../../etc/passwd.pdf")

        path = lib_model.document_path(record["id"])
        assert path.parent == lib_model.documents_dir()
        assert path.name == f"{record['id']}.pdf"

    def test_two_uploads_of_the_same_filename_do_not_collide(self):
        first = lib_model.add_document("company", "W-9", PDF, "scan.pdf")
        second = lib_model.add_document("company", "Authority", PDF, "scan.pdf")

        assert lib_model.document_path(first["id"]) != lib_model.document_path(second["id"])

    def test_an_uploaded_asset_satisfies_the_missing_check(self):
        assert "W-9" in lib_model.get_missing_company_assets()

        lib_model.add_document("company", "W-9", PDF, "w9.pdf")

        assert "W-9" in lib_model.get_available_company_assets()
        assert "W-9" not in lib_model.get_missing_company_assets()

    def test_a_text_record_still_has_no_document(self):
        record = lib_model.add_record("company", "Approved Language",
                                      content="We haul dry van.")
        assert lib_model.document_path(record["id"]) is None


class TestWhatItRefuses:
    def test_a_file_type_that_is_not_allowed(self):
        with pytest.raises(ValueError, match="not allowed"):
            lib_model.add_document("company", "W-9", PDF, "payload.exe")

    def test_an_empty_file(self):
        with pytest.raises(ValueError, match="needs a file"):
            lib_model.add_document("company", "W-9", b"", "w9.pdf")

    def test_a_file_over_the_size_limit(self):
        from dispatch.models import MAX_FILE_SIZE
        with pytest.raises(ValueError, match="limit"):
            lib_model.add_document(
                "company", "W-9", b"x" * (MAX_FILE_SIZE + 1), "w9.pdf")

    def test_a_refused_upload_leaves_no_record_behind(self):
        before = len(lib_model.get_section("company"))
        with pytest.raises(ValueError):
            lib_model.add_document("company", "W-9", PDF, "payload.exe")
        assert len(lib_model.get_section("company")) == before


class TestThroughThePortal:
    def test_upload_and_download(self, client):
        resp = client.post("/api/library/upload", data={
            "section": "company",
            "name": "Insurance",
            "file": (io.BytesIO(PDF), "coi.pdf"),
        }, content_type="multipart/form-data")

        assert resp.status_code == 201
        record = resp.get_json()["record"]
        assert record["metadata"]["document"]

        got = client.get(f"/api/library/document/{record['id']}")
        assert got.status_code == 200
        assert got.data == PDF

    def test_a_record_with_no_document_is_a_404_not_a_crash(self, client):
        record = lib_model.add_record("company", "Just A Note")
        assert client.get(f"/api/library/document/{record['id']}").status_code == 404

    def test_upload_without_a_file_is_refused(self, client):
        resp = client.post("/api/library/upload", data={
            "section": "company", "name": "W-9",
        }, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_the_library_page_offers_the_upload(self, client):
        html = client.get("/library").data.decode()
        assert "libraryUpload" in html
        assert 'type="file"' in html
