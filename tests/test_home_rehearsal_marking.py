"""The Home screen must mark rehearsal records rather than hide or ignore them.

**Mike's ruling, 2026-09-06:** *"show both with rehearsal records marked."*

The defect these guard against is specific and was real. On 2026-09-06 the two
test loads on Mike's machine were tagged correctly in the database and the Home
screen counted them exactly as before — `rehearsal_session` reached the template
and nothing rendered it. The data said *this is rehearsal* and the screen showed
`$1,775 revenue, 100.0% margin` with no qualification.

**A row can carry a badge. A total cannot.** So there are two kinds of test here:
one that a marked row renders, and one that a mixed aggregate says so in words.
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


def _tagged_load(customer="Acme", label="test session"):
    """A load tagged to a real session, the way the retroactive tag did it."""
    load = services.create_load(customer=customer)
    session = rehearsal.start_session(label=label, actor_id="tester")
    rehearsal.tag("loads", load["load_id"], session_id=session["session_id"])
    return load, session["session_id"]


class TestTheShareIsCountedHonestly:
    def test_no_loads_is_not_a_rehearsal_claim(self):
        share = services.rehearsal_share()
        assert share["any"] is False
        assert share["all"] is False, "an empty board must not report itself as all rehearsal"

    def test_an_untagged_load_is_operational(self):
        services.create_load(customer="Acme")
        share = services.rehearsal_share()
        assert share == {"total": 1, "rehearsal": 0, "operational": 1,
                         "sessions": [], "any": False, "all": False}

    def test_a_tagged_load_is_counted_and_its_session_named(self):
        _, sid = _tagged_load()
        share = services.rehearsal_share()
        assert share["rehearsal"] == 1 and share["operational"] == 0
        assert share["all"] is True
        assert share["sessions"] == [sid]

    def test_a_mixed_board_is_neither_all_nor_none(self):
        _tagged_load(customer="Rehearsal Co")
        services.create_load(customer="Real Co")
        share = services.rehearsal_share()
        assert share["total"] == 2
        assert share["rehearsal"] == 1 and share["operational"] == 1
        assert share["any"] is True
        assert share["all"] is False

    def test_counting_never_removes_a_load(self):
        """`rehearsal_share` reports. It does not filter -- Mike asked to see
        both, and a helper that quietly dropped rows would be the option he
        did not choose."""
        _tagged_load()
        services.create_load(customer="Real Co")
        assert len(services.list_loads()) == 2


class TestTheScreenSaysSo:
    def test_a_clean_board_carries_no_rehearsal_banner(self, client):
        services.create_load(customer="Real Co")
        body = client.get("/home").get_data(as_text=True)
        assert "rehearsal-data-note" not in body

    def test_an_all_rehearsal_board_says_every_load(self, client):
        _tagged_load()
        body = client.get("/home").get_data(as_text=True)
        assert "rehearsal-data-note" in body
        assert "Every load on this screen is rehearsal data" in body

    def test_a_mixed_board_gives_the_count(self, client):
        _tagged_load(customer="Rehearsal Co")
        services.create_load(customer="Real Co")
        body = client.get("/home").get_data(as_text=True)
        assert "1 of 2 loads are rehearsal data" in body

    def test_the_financial_snapshot_is_labelled_when_it_includes_rehearsal(self, client):
        """**The one that matters.**

        A number cannot wear a badge. If the snapshot is computed over rehearsal
        records it must say so in the heading, or it states test revenue with the
        same confidence it would state real revenue.
        """
        load, _ = _tagged_load()
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        body = client.get("/home").get_data(as_text=True)
        assert "Financial Snapshot" in body
        assert "REHEARSAL DATA" in body

    def test_the_snapshot_is_not_labelled_when_the_data_is_real(self, client):
        load = services.create_load(customer="Real Co")
        services.confirm_rate(load["load_id"], rate_amount=1000.0)
        body = client.get("/home").get_data(as_text=True)
        assert "Financial Snapshot" in body
        assert "REHEARSAL DATA" not in body
        assert "INCLUDES REHEARSAL" not in body

    def test_nothing_is_hidden(self, client):
        """Mike chose *show both*, not *show only real*.

        Home does not list every load, so this asserts on the count that does
        include it: a tagged load is still an Active Load. The marking must
        change how a record is *labelled*, never whether it is *counted*.
        """
        _tagged_load(customer="Zebra Freight")
        body = client.get("/home").get_data(as_text=True)
        assert "Active Loads" in body
        assert services.rehearsal_share()["total"] == 1
        # Marked, and still counted -- both halves of the ruling.
        assert "rehearsal-data-note" in body
