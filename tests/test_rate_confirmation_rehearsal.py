"""A rehearsal rate confirmation must never leave the building unmarked.

`rate_confirmation_print` is the only screen in Dispatch whose output is
designed to be printed, signed and handed to a customer. Every other unmarked
screen shows a rehearsal record to Mike; **this one shows it to a broker.**

Doctrine: `docs/DISPATCH_REHEARSAL_DATA_DOCTRINE.md`, rules 2 and 3 —
*visibly marked wherever displayed*, *never represented as live operational
truth*.

The marking is built for paper. These tests check the four places it has to
appear, because a reader who misses one may still act on the page: the browser
title (which becomes the PDF filename), a banner above the document, a watermark
across it, and a refusal at the signature line — which is where a page stops
being information and becomes an agreement.
"""

from __future__ import annotations

import pytest

from dispatch import rehearsal, services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal"))
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _confirmed_load(rehearsal_tag=False):
    load = services.create_load(customer="Acme Freight")
    services.confirm_rate(load["load_id"], rate_amount=1850.0)
    sid = ""
    if rehearsal_tag:
        session = rehearsal.start_session(label="print test", actor_id="tester")
        sid = session["session_id"]
        rehearsal.tag("loads", load["load_id"], session_id=sid)
    return load["load_id"], sid


def _print_page(client, load_id):
    resp = client.get(f"/dispatch/{load_id}/rate-confirmation/print")
    assert resp.status_code == 200, resp.status_code
    return resp.get_data(as_text=True)


class TestARehearsalRateConfirmationIsMarked:
    def test_the_title_says_so(self, client):
        """The title becomes the filename when printed to PDF. A file called
        `Rate Confirmation.pdf` in someone's downloads is the failure this
        prevents."""
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        title = body.split("<title>")[1].split("</title>")[0]
        assert "REHEARSAL" in title and "NOT VALID" in title

    def test_a_banner_sits_above_the_document(self, client):
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        assert "reh-banner" in body
        assert "THIS IS NOT A RATE CONFIRMATION" in body

    def test_the_banner_names_the_session(self, client):
        """So a reader can trace which rehearsal it came from, months later."""
        load_id, sid = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        assert sid in body

    def test_a_watermark_crosses_the_page(self, client):
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        assert "reh-watermark" in body

    def test_the_signature_block_refuses(self, client):
        """**The one that matters most.**

        The signature line is where a page stops being information and becomes
        an agreement. The lines stay visible -- Mike ruled show both, marked,
        not hide -- but nobody may act on them.
        """
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        assert "NOT FOR SIGNATURE" in body
        assert "binds no one" in body
        # Shown, not removed.
        assert "Carrier Signature / Date" in body

    def test_the_terms_paragraph_is_contradicted_in_place(self, client):
        """The terms assert that an agreement exists. On a rehearsal page that
        sentence is false, and it is answered where it is printed rather than
        only at the top."""
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        assert "no agreement exists" in body

    def test_the_marking_survives_printing(self, client):
        """Browsers strip backgrounds when printing unless told not to. A
        watermark that vanishes on paper is worse than none, because the screen
        looked marked."""
        load_id, _ = _confirmed_load(rehearsal_tag=True)
        body = _print_page(client, load_id)
        printing = body.split("@media print")[1]
        assert "reh-watermark" in printing
        assert "print-color-adjust: exact" in printing


class TestARealRateConfirmationIsUntouched:
    def test_no_marking_of_any_kind(self, client):
        """A real rate confirmation must look exactly as it always has. Marking
        that leaks onto live documents would train Mike to ignore it.

        Checked against the rendered document rather than the whole page: the
        stylesheet defines the rehearsal classes unconditionally, which is
        harmless and simpler than emitting CSS conditionally. What must never
        appear is an *element* using them.
        """
        load_id, _ = _confirmed_load(rehearsal_tag=False)
        document = _print_page(client, load_id).split("</style>")[1]
        for probe in ('class="reh-banner"', 'class="reh-watermark"',
                      'class="reh-void"', "REHEARSAL", "NOT FOR SIGNATURE",
                      "no agreement exists"):
            assert probe not in document, f"{probe!r} leaked onto a live document"

    def test_the_title_is_clean(self, client):
        load_id, _ = _confirmed_load(rehearsal_tag=False)
        body = _print_page(client, load_id)
        title = body.split("<title>")[1].split("</title>")[0]
        assert title.startswith("Rate Confirmation")

    def test_the_agreement_still_stands(self, client):
        load_id, _ = _confirmed_load(rehearsal_tag=False)
        body = _print_page(client, load_id)
        assert "serves as an agreement" in body
        assert "Carrier Signature / Date" in body
