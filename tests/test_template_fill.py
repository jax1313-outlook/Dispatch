"""Filling the Owner's Word templates, to his locked placeholder policy.

The rule that shapes all of it is his rule 7: *"Missing or unverified values
must remain visible or produce a structured validation failure. Publisher must
not invent facts."* A document filled with blanks where the facts were missing
looks finished and is not.

These tests build their own .docx rather than reading `D:\\Memory` -- the shelf
is read-only and a test that depends on a file the Owner is still editing is a
test that fails for the wrong reason.
"""

from __future__ import annotations

import zipfile

import pytest

from dispatch import publisher_values as pv
from dispatch import template_fill as tf

DOC = ("<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
       "<w:document xmlns:w='x'><w:body>%s</w:body></w:document>")


def _run(text: str) -> str:
    return "<w:p><w:r><w:t>%s</w:t></w:r></w:p>" % text


def _docx(tmp_path, paragraphs, *, footer: str = "", name: str = "t.docx"):
    """A minimal but real .docx: a zip with the parts Word expects."""
    path = tmp_path / name
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", DOC % "".join(_run(p) for p in paragraphs))
        if footer:
            z.writestr("word/footer1.xml", DOC % _run(footer))
        z.writestr("word/styles.xml", "<styles/>")
        z.writestr("media/logo.png", b"\x89PNG-not-really")
    return path


def _text(path) -> str:
    with zipfile.ZipFile(str(path)) as z:
        parts = [n for n in z.namelist() if n.startswith("word/")]
        return " ".join(z.read(p).decode("utf-8") for p in parts)


class TestItFillsWhatItWasGiven:
    def test_an_exact_match_is_replaced(self, tmp_path):
        template = _docx(tmp_path, ["Load Number: {{load_number}}"])

        report = tf.fill(template, {"load_number": "Tallahassee-1487"},
                         tmp_path / "out.docx")

        assert "Tallahassee-1487" in _text(tmp_path / "out.docx")
        assert report["filled"] == {"load_number": "Tallahassee-1487"}
        assert report["ok"] is True

    def test_the_same_placeholder_twice_is_filled_twice(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}", "again {{load_number}}"])

        tf.fill(template, {"load_number": "L1-0001"}, tmp_path / "out.docx")

        assert _text(tmp_path / "out.docx").count("L1-0001") == 2

    def test_a_footer_is_filled_too(self, tmp_path):
        """His templates put the load number in a header on every page."""
        template = _docx(tmp_path, ["body"], footer="Load {{load_number}}")

        tf.fill(template, {"load_number": "L1-0002"}, tmp_path / "out.docx")

        assert "L1-0002" in _text(tmp_path / "out.docx")

    def test_everything_that_is_not_text_survives(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}"])

        tf.fill(template, {"load_number": "L1-0003"}, tmp_path / "out.docx")

        with zipfile.ZipFile(str(tmp_path / "out.docx")) as z:
            assert z.read("media/logo.png") == b"\x89PNG-not-really"
            assert z.read("word/styles.xml") == b"<styles/>"

    def test_an_ampersand_does_not_break_the_document(self, tmp_path):
        """"Smith & Sons" written raw makes a file Word refuses to open."""
        template = _docx(tmp_path, ["{{customer}}"])

        tf.fill(template, {"customer": "Smith & Sons"}, tmp_path / "out.docx")

        assert "Smith &amp; Sons" in _text(tmp_path / "out.docx")

    def test_the_template_itself_is_never_written(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}"])
        before = template.read_bytes()

        tf.fill(template, {"load_number": "L1-0004"}, tmp_path / "out.docx")

        assert template.read_bytes() == before


class TestRuleSeven:
    """*"Missing or unverified values must remain visible or produce a
    structured validation failure. Publisher must not invent facts."*"""

    def test_a_missing_value_leaves_the_placeholder_standing(self, tmp_path):
        template = _docx(tmp_path, ["Invoice {{invoice_number}} for {{customer}}"])

        report = tf.fill(template, {"customer": "Penske Logistics"},
                         tmp_path / "out.docx")

        assert "{{invoice_number}}" in _text(tmp_path / "out.docx")
        assert report["left_visible"] == ["invoice_number"]

    def test_an_empty_value_is_not_a_value(self, tmp_path):
        """A blank where a fact should be looks answered. It is not."""
        template = _docx(tmp_path, ["{{consignee}}"])

        report = tf.fill(template, {"consignee": ""}, tmp_path / "out.docx")

        assert "{{consignee}}" in _text(tmp_path / "out.docx")
        assert report["filled"] == {}

    def test_accounting_gaps_are_named_apart_from_mission_gaps(self, tmp_path):
        """*"any money issue it not the problem of this program."* A field the
        accounting software owns is not a hole in the mission record, and
        reporting them together would have somebody chasing the wrong one."""
        template = _docx(tmp_path, ["{{invoice_number}} {{payment_terms}} {{consignee}}"])

        report = tf.fill(template, {}, tmp_path / "out.docx")

        assert set(report["accounting"]) == {"invoice_number", "payment_terms"}
        assert "consignee" in report["left_visible"]
        assert "consignee" not in report["accounting"]

    def test_a_name_the_template_never_asked_for_is_reported(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}"])

        report = tf.fill(template, {"load_number": "L1-0005", "seal_number": "9"},
                         tmp_path / "out.docx")

        assert report["unused"] == ["seal_number"]

    def test_a_split_placeholder_is_a_validation_failure(self, tmp_path):
        """Word stores an edited placeholder as several runs. It reads perfectly
        on screen and will never match. This is the failure that silently ruins
        template filling, so it is named rather than skipped."""
        path = tmp_path / "split.docx"
        with zipfile.ZipFile(str(path), "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", DOC % (
                "<w:p><w:r><w:t>{{load_</w:t></w:r>"
                "<w:r><w:t>number}}</w:t></w:r></w:p>"))

        report = tf.fill(path, {"load_number": "L1-0006"}, tmp_path / "out.docx")

        assert report["split_runs"] == ["load_number"]
        assert report["ok"] is False
        assert "{{load_number}}" not in report["filled"]

    def test_the_document_is_still_written_when_it_is_not_ok(self, tmp_path):
        """A partly filled document he can look at beats a refusal he cannot."""
        path = tmp_path / "split.docx"
        with zipfile.ZipFile(str(path), "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", DOC % (
                "<w:p><w:r><w:t>{{load_</w:t></w:r>"
                "<w:r><w:t>number}}</w:t></w:r></w:p>"))

        report = tf.fill(path, {}, tmp_path / "out.docx")

        assert (tmp_path / "out.docx").exists()
        assert report["ok"] is False


class TestTheBuildInstructionComesOff:
    """**Owner ruling, 2026-09-16:** *"remove the footer."*

    `Production template | Replace exact {{placeholders}} only | Missing facts
    remain visible` is the Owner talking to whoever builds the template. It was
    printing on the bottom of the invoice a customer receives."""

    def test_the_instruction_footer_is_emptied(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}"],
                         footer="Production template | Replace exact "
                                "{{placeholders}} only | Missing facts remain visible")

        report = tf.fill(template, {"load_number": "L1-0007"}, tmp_path / "out.docx")

        assert "Replace exact" not in _text(tmp_path / "out.docx")
        assert "{{placeholders}}" not in _text(tmp_path / "out.docx")
        assert report["stripped"] == ["word/footer1.xml"]

    def test_a_footer_that_is_not_an_instruction_stays(self, tmp_path):
        """His detention policy carries `Onboarding packet policy | Current
        approved detention-rate policy controls` -- a real statement of terms
        that belongs on the page. Stripping "the footer" by position would have
        quietly deleted it."""
        template = _docx(tmp_path, ["{{load_number}}"],
                         footer="Onboarding packet policy | Current approved "
                                "detention-rate policy controls")

        report = tf.fill(template, {"load_number": "L1-0008"}, tmp_path / "out.docx")

        assert "detention-rate policy controls" in _text(tmp_path / "out.docx")
        assert report["stripped"] == []

    def test_the_stripped_instructions_own_words_are_not_reported_as_gaps(self, tmp_path):
        """`{{placeholders}}` in that sentence is prose. Once the sentence is
        gone it is not a hole in the document, and a report that lists it
        teaches a man to ignore the list."""
        template = _docx(tmp_path, ["{{load_number}}"],
                         footer="Replace exact {{placeholders}} only")

        report = tf.fill(template, {}, tmp_path / "out.docx")

        assert "placeholders" not in report["left_visible"]
        assert report["left_visible"] == ["load_number"]

    def test_the_document_body_is_untouched_by_the_stripping(self, tmp_path):
        template = _docx(tmp_path, ["Keep me: {{customer}}"],
                         footer="Replace exact {{placeholders}} only")

        tf.fill(template, {"customer": "Penske Logistics"}, tmp_path / "out.docx")

        assert "Keep me" in _text(tmp_path / "out.docx")
        assert "Penske Logistics" in _text(tmp_path / "out.docx")


class TestTheInventoryCheck:
    """His rule 9, before a revised template is used."""

    def test_it_lists_the_names_in_order(self, tmp_path):
        template = _docx(tmp_path, ["{{load_number}}", "{{customer}} {{load_number}}"])

        assert tf.inventory(template)["names"] == ["load_number", "customer"]

    def test_it_reports_a_typo_rather_than_leaving_it_to_look_unfilled(self, tmp_path):
        template = _docx(tmp_path, ["{{Load_Number}}"])

        found = tf.inventory(template)

        assert found["names"] == []
        assert found["malformed"] == ["{{Load_Number}}"]


class TestACompanyDocumentGoesInUntouched:
    def test_it_is_copied_byte_for_byte(self, tmp_path):
        w9 = tmp_path / "W9.pdf"
        w9.write_bytes(b"%PDF-1.4 not really")

        report = tf.copy_as_is(w9, tmp_path / "packet" / "W9.pdf")

        assert (tmp_path / "packet" / "W9.pdf").read_bytes() == b"%PDF-1.4 not really"
        assert report["ok"] is True


class TestTheMissionRecordInHisWords:
    RECORD = {
        "load_number": "Tallahassee-1487",
        "customer": "Penske Logistics",
        "customer_poc": "Jeff Tissue",
        "customer_email": "J.tissue@penske.com",
        "bol_number": "PNSK-2026-19865",
        "pickup_location": "VW PDC, 184 Picketville Rd, Jacksonville, FL 32256",
        "pickup_window": "2026-09-16 09:00",
        "delivery_location": "Penske Ft. Pierce, 134 Bell St, Ft. Pierce, FL",
        "delivery_window": "2026-09-16 14:00",
        "card_data": {"commodity": "Auto Parts", "weight_lbs": 9214,
                      "rate": "1750.00", "load_id": "Tallahassee-1487"},
        "pieces_pallets": "3 pallets",
    }

    def test_the_two_vocabularies_meet(self):
        values = pv.values_for(self.RECORD, today="2026-09-16")

        assert values["cargo_description"] == "Auto Parts"
        assert values["weight"] == "9214"
        assert values["pickup_appointment"] == "2026-09-16 09:00"
        assert values["delivery_location"].startswith("Penske Ft. Pierce")

    def test_an_appointment_also_answers_the_date_and_the_time(self):
        values = pv.values_for(self.RECORD)

        assert values["pickup_date"] == "2026-09-16"
        assert values["pickup_time"] == "09:00"

    def test_the_customers_own_number_is_the_load_number(self):
        """*"why would system generate a load number when the BOL one is clearly
        provided ... this is how this company actually list load numbers:
        Tallahassee-1487."*"""
        values = pv.values_for(self.RECORD)

        assert values["load_number"] == "Tallahassee-1487"
        assert values["customer_load_number"] == "Tallahassee-1487"

    def test_no_money_field_is_answered(self):
        """*"All money issues are deferred to accounting software."*"""
        values = pv.values_for(self.RECORD)

        assert not (set(values) & tf.ACCOUNTING_FIELDS)

    def test_the_rate_is_a_fact_of_the_mission_and_is_answered(self):
        """He agreed it on the call. That is not accounting's arithmetic."""
        assert pv.values_for(self.RECORD)["rate"] == "1750.00"

    def test_a_fact_the_record_does_not_hold_is_absent_not_blank(self):
        values = pv.values_for(self.RECORD)

        assert "consignee" not in values


class TestWhatDispatchAlreadyKnows:
    """**Owner, 2026-09-16:** *"wire the fields dispatch already knows."*

    Everything here is a fact the program is already holding somewhere and was
    making a man retype onto a document."""

    BASE = dict(TestTheMissionRecordInHisWords.RECORD)

    def test_the_driver_is_who_ran_it_and_who_prepared_the_packet(self):
        values = pv.values_for(self.BASE, driver_name="M. Zachary")

        assert values["driver_name"] == "M. Zachary"
        assert values["prepared_by"] == "M. Zachary"

    def test_no_driver_supplied_is_absent_not_a_guess(self):
        assert "driver_name" not in pv.values_for(self.BASE)

    def test_the_gps_link_is_the_fix_the_tablet_recorded(self):
        record = dict(self.BASE, pickup_gps="30.3322,-81.6557")

        link = pv.values_for(record)["gps_location_link"]

        assert "30.3322,-81.6557" in link
        assert link.startswith("https://")

    def test_no_fix_means_no_link_rather_than_the_address(self):
        """A link built from the facility address would look like evidence the
        truck was there and be nothing of the kind."""
        assert "gps_location_link" not in pv.values_for(self.BASE)

    def test_a_ticked_checklist_answers_the_attached_lines(self):
        record = dict(self.BASE, artifacts_held=["Proof Of Delivery Document",
                                                 "Bill of Lading (BOL)"])

        values = pv.values_for(record)

        assert values["pod_attached"] == pv.HELD
        assert values["signed_bol_attached"] == pv.HELD
        assert values["final_condition_photos_attached"] == pv.NOT_HELD
        # `pod_status` was struck on 2026-09-17: *"delete delivery_status and
        # pod_status, they are software created too."* The tick is the fact;
        # a word printed about the tick is software describing itself.
        assert "pod_status" not in values

    def test_no_two_placeholders_read_the_same_tick(self):
        """Answering two questions from one answer invents the second. This is
        the rule the four-photo pass broke and the reason the Owner cut it."""
        lines = list(pv.ATTACHED_FROM_CHECKLIST.values())
        assert len(lines) == len(set(lines))

    def test_the_three_photo_names_are_the_operators(self):
        """**PUBLISHER HARDENING RULING, 2026-09-16:** *"Publisher, Cockpit,
        Mission Record, and Placeholder Registry must use the same three
        names."* The ticks are what the Mission Record stores, so these strings
        are the vocabulary itself, not a label for it."""
        record = dict(self.BASE, artifacts_held=[
            "Photos - Loaded Vehicle", "Photos - Mid-Route Securement"])

        values = pv.values_for(record)

        assert values["loaded_vehicle_photos_attached"] == pv.HELD
        assert values["securement_photos_attached"] == pv.HELD
        assert values["final_condition_photos_attached"] == pv.NOT_HELD

    def test_freight_condition_is_never_answered(self):
        """Struck from the cockpit, the templates, the registry, the mappings
        and the tests: *"Not a separate operational event."*"""
        record = dict(self.BASE, artifacts_held=["Photos - Loaded Vehicle"])

        assert "freight_condition_photos_attached" not in pv.values_for(record)
        assert "freight_condition_photos_attached" in pv.REMOVED_FIELDS

    def test_every_photo_line_is_one_the_cockpit_offers(self):
        """A placeholder reading a line no driver can tick is a placeholder that
        always says No."""
        from portal import cockpit

        offered = {a.lower() for a in
                   cockpit.PICKUP_ARTIFACTS + cockpit.DELIVERY_ARTIFACTS}
        for placeholder, line in pv.ATTACHED_FROM_CHECKLIST.items():
            assert line.lower() in offered, placeholder



    def test_an_untouched_checklist_says_nothing_at_all(self):
        """Printing "No" against every line would assert an absence nobody
        checked. The placeholders stay visible instead."""
        values = pv.values_for(self.BASE)

        assert "pod_attached" not in values
        assert "signed_bol_attached" not in values
        assert "pod_status" not in values

    def test_an_empty_checklist_is_an_answer(self):
        """He worked the list and ticked nothing. That is a fact."""
        values = pv.values_for(dict(self.BASE, artifacts_held=[]))

        assert values["pod_attached"] == pv.NOT_HELD

    def test_the_delivery_is_the_milestone_and_nothing_prints_a_word_about_it(self):
        """**Struck, and the parameter with it.** Owner ruling, 2026-09-17:
        *"delete delivery_status and pod_status, they are software created
        too."*

        The history is worth keeping because it is the same lesson twice. The
        placeholder first read a `delivered_at` field **nothing has ever
        written**, so it stayed blank on every real run while looking wired --
        found by walking a load through the routes, not by reading the code. It
        was then wired to a `delivered` parameter, which worked. The Owner
        struck the whole idea: the Delivered milestone is the fact, and a word
        printed about it is software describing what it already holds.

        `values_for` no longer takes `delivered` at all. A parameter nothing
        reads is the same untruth in a signature."""
        import inspect

        assert "delivery_status" not in pv.values_for(self.BASE)
        assert "delivery_status" not in pv.values_for(
            dict(self.BASE, delivered_at="2026-09-16T14:22:00Z"))
        assert "delivered" not in inspect.signature(pv.values_for).parameters
        assert {"delivery_status", "pod_status"} <= pv.REMOVED_FIELDS

    #: Every placeholder in the Owner's templates that Dispatch could
    #: conceivably answer from what it already holds. Written down rather than
    #: read from `D:\\Memory`: the shelf is read-only and a test that depends on
    #: a file he is still editing fails for the wrong reason.
    #:
    #: On 2026-09-16 the Owner revised three of them against his own rulings and
    #: took out every struck name: `receiver_name`, `receiver_title`,
    #: `pickup_on_time_status`, `freight_condition_photos_attached`, and
    #: `delivery_photos_attached` -- the fourth photo name, where the approved
    #: workflow has three.
    ASKED_BY_HIS_TEMPLATES = {
        "pod_attached", "signed_bol_attached", "invoice_attached",
        "securement_photos_attached", "loaded_vehicle_photos_attached",
        "final_condition_photos_attached", "driver_name", "prepared_by",
        "gps_location_link", "delivery_status", "pod_status",
    }

    WIRED = set(pv.ATTACHED_FROM_CHECKLIST) | {
        "driver_name", "prepared_by", "gps_location_link",
        "delivery_status", "pod_status"}

    def test_every_wired_name_is_one_a_template_actually_asks_for(self):
        """Producing a value no template wants is dead weight that reads as a
        gap in the report."""
        assert self.WIRED <= self.ASKED_BY_HIS_TEMPLATES

    def test_his_templates_and_this_program_now_ask_the_same_things(self):
        """**Nothing is left over.** Every name his documents ask for that
        Dispatch could answer from what it holds, Dispatch answers -- and every
        name Dispatch produces, a document of his asks for.

        Reached by him revising the templates on 2026-09-16 rather than by this
        program widening to meet them: the struck fields came out of the
        documents, and the photo names on both sides are the three he ruled.
        If this test ever fails, one side moved without the other."""
        assert self.ASKED_BY_HIS_TEMPLATES == self.WIRED

    def test_end_to_end_against_a_template(self, tmp_path):
        template = _docx(tmp_path, [
            "Load: {{load_number}}   BOL: {{bol_number}}",
            "{{customer}} / {{billing_contact}}",
            "{{pickup_location}} on {{pickup_date}} at {{pickup_time}}",
            "Invoice {{invoice_number}} terms {{payment_terms}}",
        ])

        report = tf.fill(template, pv.values_for(self.BASE, today="2026-09-16"),
                         tmp_path / "out.docx")
        written = _text(tmp_path / "out.docx")

        assert "Tallahassee-1487" in written
        assert "PNSK-2026-19865" in written
        assert "Jeff Tissue" in written
        assert "09:00" in written
        # Accounting's, and still visibly unanswered.
        assert "{{invoice_number}}" in written
        assert report["accounting"] == ["invoice_number", "payment_terms"]
        assert report["ok"] is True
class TestRevisionThree:
    """**PUBLISHER TEST RULING - REVISION 3, 2026-09-16.**

    Its governing rule, and the one worth carrying past this file:

        Federal BOL  = controlling freight document.
        Signed POD   = controlling delivery evidence.
        Dispatch stores freight facts.
        Archive preserves freight evidence.
        Publisher creates payment-readiness documents.

        *"Do not duplicate information already preserved inside a controlling
        document."*
    """

    RECORD = dict(TestTheMissionRecordInHisWords.RECORD)

    def test_nothing_publisher_will_never_fill_is_ever_answered(self):
        values = pv.values_for(dict(self.RECORD, artifacts_held=[],
                                    delivered_at="2026-09-16T14:22:00Z"),
                               driver_name="M. Zachary")

        assert not (set(values) & pv.NEVER_FILLED)

    def test_nothing_maps_them(self):
        assert not (set(pv.ATTACHED_FROM_CHECKLIST) & pv.NEVER_FILLED)

    def test_a_struck_field_and_an_evidence_field_are_not_the_same_finding(self, tmp_path):
        """The remedies differ, and a single list would send a man to delete a
        placeholder whose answer he actually needs. `receiver_title` is gone for
        good; `receiver_name` is printed on the POD he already has."""
        template = _docx(tmp_path, [
            "{{receiver_name}} {{receiver_title}} {{pickup_on_time_status}} {{consignee}}"])

        report = tf.fill(template, {"consignee": "Penske Ft. Pierce"},
                         tmp_path / "out.docx")

        assert report["removed"] == ["receiver_title", "pickup_on_time_status"]
        assert report["in_the_pod"] == ["receiver_name"]

    def test_receiver_title_is_struck_outright(self):
        """*"Receiver title has no operational value ... Do not collect. Do not
        store. Do not display. Do not create placeholders."*"""
        assert "receiver_title" in pv.REMOVED_FIELDS
        assert "receiver_title" not in pv.EVIDENCE_IN_POD

    def test_the_receiver_name_and_signature_live_in_the_pod(self):
        """*"The POD image/PDF already preserves printed receiver name and
        receiver signature. No duplicate tracking field is required. When
        delivery proof is needed: Retrieve POD."*"""
        assert pv.EVIDENCE_IN_POD == {"receiver_name", "receiver_signature",
                                      "shipper_signature"}

    def test_each_one_names_the_document_that_holds_it(self):
        """**The remedy is the point of this list.** Owner ruling, 2026-09-17:
        *"shipper_signature should be classified as evidence."* A receiver signs
        at the delivery end and that is the POD; a shipper signs at the pickup
        end and that is the BOL. A report that sent a man to the POD for a
        shipper's signature would be a remedy that fails at the filing
        cabinet."""
        assert pv.EVIDENCE_IN_THE_DOCUMENT["receiver_signature"] == "the signed POD"
        assert pv.EVIDENCE_IN_THE_DOCUMENT["shipper_signature"] == "the signed BOL"

    def test_the_status_twin_is_struck_not_kept(self):
        """*"notice the Status is not used and is software created."* The
        signature is evidence; a field describing whether the evidence exists
        is software talking about itself."""
        assert "shipper_signature_status" in pv.REMOVED_FIELDS
        assert "shipper_signature_status" not in pv.EVIDENCE_IN_POD

    def test_on_time_is_never_calculated(self):
        """*"Derived interpretation ... The underlying facts remain
        authoritative."*"""
        assert "pickup_on_time_status" in pv.REMOVED_FIELDS

    def test_an_unknown_consignee_fails_nothing(self, tmp_path):
        """*"Consignee may be UNKNOWN at Commit. Commit must not fail. Mission
        Record must not fail. Publisher must not fail. If known: Store it. If
        unknown: UNKNOWN is acceptable."*

        Most large corporations put the home office on the BOL rather than the
        dock, so the consignee's real location is usually not known until the
        pickup is effected -- which is why this must never be a hard stop."""
        template = _docx(tmp_path, ["Deliver to {{consignee}} at {{delivery_location}}"])

        report = tf.fill(template, pv.values_for(self.RECORD), tmp_path / "out.docx")

        assert report["ok"] is True
        assert report["left_visible"] == ["consignee"]
        assert "Penske Ft. Pierce" in _text(tmp_path / "out.docx")

    def test_an_unknown_consignee_prints_the_placeholder_not_the_word_unknown(
            self, tmp_path):
        """**Owner ruling, 2026-09-16:** *"Leave {{consignee}} visible. Do NOT
        replace with UNKNOWN."*

            {{consignee}}  =  missing required source data
            UNKNOWN        =  known to be unknown

        Two different conditions, and `UNKNOWN` is a word from the truth
        vocabulary that asserts Dispatch went and determined the fact cannot be
        had. Printing it where nobody has looked yet would be a lie in the
        program's own language."""
        template = _docx(tmp_path, ["Deliver to {{consignee}}"])

        tf.fill(template, pv.values_for(self.RECORD), tmp_path / "out.docx")
        written = _text(tmp_path / "out.docx")

        assert "{{consignee}}" in written
        assert "UNKNOWN" not in written

    def test_the_consignee_is_the_receiving_authority_and_is_filled(self):
        """*"Consignee remains a required Mission Record field and a required
        Publisher field."*"""
        record = dict(self.RECORD, consignee="Penske Ft. Pierce")

        assert pv.values_for(record)["consignee"] == "Penske Ft. Pierce"

    def test_the_consignee_is_not_a_hard_stop_at_capture(self):
        """**His workflow, 2026-09-16:** *"Consignee location is nearly always
        unknow at time of commit and only listed on BOL when pickup is effected
        ... So Consignee should be optional field not hard stop."* Most large
        corporations put the home office on the BOL, not the dock -- which
        confuses drivers when the office is local and the delivery is miles
        away."""
        from dispatch import mission_template as mt

        field = next(f for f in mt.TEMPLATE if f.key == "consignee")
        assert field.required is False
        assert mt.validate(dict(mt.blank_template(), **{
            "customer": "Penske Logistics", "commodity": "Auto Parts",
            "pickup_location": "Jacksonville, FL",
            "pickup_window": "2026-09-16 09:00",
            "delivery_location": "Ft. Pierce, FL",
            "delivery_window": "2026-09-16 14:00"})) == []
