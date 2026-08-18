"""Tests for the read-only load detail view reachable from Load Search
(Driver-First Doctrine D6/D9 -- no accidental modification from a lookup
flow). Covers: the new route renders the load's data correctly, contains
no create/modify/delete/archive/complete/dispatch/send affordances, and
that search results now link to it instead of the full editable
/dispatch/<load_id> page.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
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


# ── Renders load data ───────────────────────────────────────────────


class TestLoadReadonlyDetailRenders:
    def test_renders_load_info(self, client):
        load = services.create_load(
            customer="Readonly Detail Co",
            pickup_location="Dallas, TX",
            delivery_location="Houston, TX",
        )
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert "Readonly Detail Co" in html
        assert "Dallas, TX" in html
        assert "Houston, TX" in html
        assert "Load Information" in html
        assert "Evidence" in html
        assert "Exceptions" in html
        assert "POD Packages" in html
        assert "Retention Archive" in html

    def test_renders_milestones(self, client):
        load = services.create_load(customer="RO MS Test")
        services.add_milestone(load["load_id"], "dispatched", location="Yard A")
        resp = client.get(f"/search/loads/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "dispatched" in html
        assert "Yard A" in html

    def test_renders_exceptions(self, client):
        load = services.create_load(customer="RO Exc Test")
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Traffic jam")
        resp = client.get(f"/search/loads/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "Traffic jam" in html

    def test_renders_financials_and_settlement(self, client):
        load = services.create_load(customer="RO Financial Co")
        services.confirm_rate(load["load_id"], rate_amount=1500, distance_miles=400)
        stl = services.create_settlement(load["load_id"])
        resp = client.get(f"/search/loads/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "1,500.00" in html or "1500.00" in html
        assert stl["invoice_number"] in html

    def test_renders_retention(self, client):
        load = services.create_load(customer="RO Retention Co")
        services.archive_load(load["load_id"])
        resp = client.get(f"/search/loads/{load['load_id']}")
        html = resp.data.decode("utf-8")
        assert "archive_id" not in html  # sanity: not dumping raw keys
        assert "archived" in html

    def test_not_found_redirects_to_search(self, client):
        resp = client.get("/search/loads/nonexistent-id")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/search")


# ── Strictly read-only: no action affordances ───────────────────────


class TestLoadReadonlyDetailIsReadOnly:
    def test_no_action_buttons(self, client):
        """Driver-First Doctrine (D6/D9): blocked actions -- create,
        modify, delete, archive, complete, dispatch, send -- must never
        appear as controls on the read-only load lookup page."""
        load = services.create_load(customer="RO No Buttons Co")
        services.add_milestone(load["load_id"], "dispatched")
        services.open_exception(load["load_id"], exception_type="delay", description="Delay")
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert resp.status_code == 200
        # Specific button-label text, not bare verbs -- base.html's shared
        # sitewide JS legitimately mentions actions like "delete" for
        # unrelated pages (e.g. libraryDelete()), which isn't a control
        # on this page.
        for blocked in (
            b">Archive Load<",
            b">Generate POD<",
            b">End Load<",
            b">+ Add Milestone<",
            b">+ Attach Evidence<",
            b">+ Report Exception<",
            b">+ Start Detention<",
            b">+ Add Expense<",
            b">Confirm Rate<",
            b">Create Invoice<",
            b">Record Payment<",
            b">Mark Overdue<",
            b">Dispute<",
            b">Write Off<",
            b">Draft Review Package<",
            b">Submit<",
            b">Save Edits<",
            b">Save Changes<",
            b">Edit<",
            b">Delete Load<",
            b">Duplicate<",
            b">Validate<",
            b">Assign<",
            b">Remove<",
            b">Post<",
        ):
            assert blocked not in resp.data, blocked

    def test_no_forms(self, client):
        """No <form> elements at all -- this page cannot submit anything."""
        load = services.create_load(customer="RO No Forms Co")
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert b"<form" not in resp.data

    def test_no_inline_action_handlers(self, client):
        """No onclick= handlers -- every mutation on the full detail page
        is wired through onclick, so their absence confirms the action
        layer was stripped, not just hidden with CSS."""
        load = services.create_load(customer="RO No Onclick Co")
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert b"onclick=" not in resp.data

    def test_no_editable_inputs(self, client):
        """No <input> or <textarea> edit affordances -- data is rendered
        as plain text, not pre-filled editable fields."""
        load = services.create_load(customer="RO No Inputs Co")
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert b"<input" not in resp.data
        assert b"<textarea" not in resp.data
        assert b"<select" not in resp.data


# ── Search links to the read-only route ─────────────────────────────


class TestSearchLinksToReadonlyDetail:
    def test_search_results_link_to_readonly_route(self, client):
        load = services.create_load(customer="RO Link Check Co")
        resp = client.get("/search?q=RO Link Check")
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        assert f"/search/loads/{load['load_id']}" in html
        assert f"/dispatch/{load['load_id']}" not in html

    def test_readonly_route_reachable(self, client):
        load = services.create_load(customer="RO Reach Co")
        resp = client.get(f"/search/loads/{load['load_id']}")
        assert resp.status_code == 200

    def test_full_editable_page_still_reachable_directly(self, client):
        """dispatch_detail itself is untouched -- only the Search link
        target changed, not the page's own existence or its route."""
        load = services.create_load(customer="RO Full Page Still There Co")
        resp = client.get(f"/dispatch/{load['load_id']}")
        assert resp.status_code == 200
        assert b">Archive Load<" in resp.data
