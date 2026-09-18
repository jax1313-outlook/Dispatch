"""The closing packet: one folder, named by the load number.

**Owner ruling, 2026-09-16:** *"POD sent completes the load and triggers the
closing packet."*

And the filing convention, 2026-09-15: *"a duplicate along with all original are
placed in a folder inside of Library according to that number for retervial from
Archive. that is the tracing number. same system used by FedEx/ UPS and
others."*

These tests build their own shelf rather than reading `D:\\Memory` -- it is
read-only, and a test that depends on a file the Owner is still editing fails
for the wrong reason.
"""

from __future__ import annotations

import zipfile

import pytest

from dispatch import closing_packet


DOC = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
       "<w:document xmlns:w='x'><w:body>%s</w:body></w:document>")


def _template(path, text):
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   DOC % ("<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % text))
    return path


@pytest.fixture()
def shelf(tmp_path):
    """His two folders, as they sit on the node.

    In its own directory, not `tmp_path` itself: a packet written beside the
    shelf would look like the shelf had been written to."""
    shelf = tmp_path / "Memory"
    templates = shelf / "Templates"
    library = shelf / "Company Library"
    templates.mkdir(parents=True)
    library.mkdir(parents=True)
    _template(templates / "01_Invoice_Template 1.docx",
              "Load {{load_number}} for {{customer}} -- invoice {{invoice_number}}")
    _template(templates / "02_POD_Cover_Sheet 1.docx",
              "{{load_number}} delivered to {{delivery_location}}: {{delivery_status}}")
    _template(templates / "00_PUBLISHER_PLACEHOLDER_POLICY_v1_LOCKED.docx",
              "This is the policy, not a template. {{field_name}}")
    (templates / "W9.pdf").write_bytes(b"%PDF-1.4 W9")
    (library / "Insurance.pdf").write_bytes(b"%PDF-1.4 COI")
    return shelf


RECORD = {
    "load_number": "Tallahassee-1487",
    "customer": "Penske Logistics",
    "delivery_location": "Penske Ft. Pierce, 134 Bell St, Ft. Pierce, FL",
    "card_data": {"commodity": "Auto Parts", "load_id": "Tallahassee-1487"},
}


class TestTheFolderIsTheLoadNumber:
    def test_it_is_named_by_the_number_exactly_as_given(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

        assert closing_packet.folder_for("Tallahassee-1487").name == "Tallahassee-1487"

    def test_a_number_is_never_tidied_up(self, tmp_path, monkeypatch):
        """*"a number we tidied up is a number that no longer matches theirs on
        an invoice."* Case and dashes stand."""
        monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

        assert closing_packet.folder_for("cvs-44912").name == "cvs-44912"

    def test_characters_a_folder_cannot_hold_are_replaced(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

        assert "/" not in closing_packet.folder_for("AB/12").name

    def test_a_load_with_no_number_still_files_somewhere(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DISPATCH_PACKET_ROOT", str(tmp_path / "packets"))

        assert closing_packet.folder_for("").name == "no-load-number"


class TestWhatGoesInIt:
    def test_his_templates_are_filled(self, shelf, tmp_path):
        out = tmp_path / "out"

        report = closing_packet.build(RECORD, shelf=shelf, out_dir=out,
                                      today="2026-09-16")

        assert report["ok"] is True
        assert len(report["documents"]) == 2
        assert (out / "01_Invoice_Template.docx").exists()

    def test_the_policy_document_is_not_a_template(self, shelf, tmp_path):
        report = closing_packet.build(RECORD, shelf=shelf, out_dir=tmp_path / "out")

        assert not any("POLICY" in d["template"].upper() for d in report["documents"])

    def test_the_fixed_documents_are_copied_byte_for_byte(self, shelf, tmp_path):
        out = tmp_path / "out"

        closing_packet.build(RECORD, shelf=shelf, out_dir=out)

        assert (out / "W9.pdf").read_bytes() == b"%PDF-1.4 W9"
        assert (out / "Insurance.pdf").read_bytes() == b"%PDF-1.4 COI"

    def test_the_shelf_is_never_written(self, shelf, tmp_path):
        before = {p.name: p.read_bytes() for p in shelf.rglob("*") if p.is_file()}

        closing_packet.build(RECORD, shelf=shelf, out_dir=tmp_path / "out")

        assert {p.name: p.read_bytes()
                for p in shelf.rglob("*") if p.is_file()} == before


class TestItTellsTheTruthAboutWhatIsMissing:
    def test_an_unanswered_fact_is_reported_and_is_not_a_failure(self, shelf, tmp_path):
        """Rule 7. A document still saying {{invoice_number}} is telling the
        truth about what nobody supplied."""
        report = closing_packet.build(RECORD, shelf=shelf, out_dir=tmp_path / "out")

        assert report["ok"] is True
        assert "invoice_number" in report["accounting"]

    def test_money_is_named_apart_from_mission_gaps(self, shelf, tmp_path):
        """*"All money issues are deferred to accounting software."*"""
        report = closing_packet.build(RECORD, shelf=shelf, out_dir=tmp_path / "out")

        assert "invoice_number" not in report["missing"]

    def test_no_shelf_says_so_plainly(self, tmp_path):
        report = closing_packet.build(RECORD, shelf=tmp_path / "nowhere",
                                      out_dir=tmp_path / "out")

        assert report["ok"] is False
        assert "DISPATCH_MEMORY_ROOT" in report["note"]

    def test_a_struck_placeholder_is_left_standing_and_reported(self, shelf, tmp_path):
        """**`{{delivery_status}}` is struck.** Owner ruling, 2026-09-17:
        *"delete delivery_status and pod_status, they are software created
        too."*

        This used to assert the document printed "Delivered". Nothing prints it
        now -- the placeholder stays visible, which is rule 7, and the report
        says *why* it will never be filled so the remedy is to revise the
        template rather than hunt a missing fact."""
        out = tmp_path / "out"

        report = closing_packet.build(RECORD, shelf=shelf, out_dir=out)

        with zipfile.ZipFile(str(out / "02_POD_Cover_Sheet.docx")) as z:
            body = z.read("word/document.xml").decode("utf-8")
        assert "Delivered" not in body
        assert "{{delivery_status}}" in body
        assert "delivery_status" in report["removed"]
