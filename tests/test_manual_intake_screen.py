"""Every source produces the same Mission Record.

    One Mission Template. Multiple intake methods. One Mission Record.
    One workflow.

A broker calling, a courier run phoned in, a shipper emailing direct, a text
message, an existing customer -- all of them arrive as a Mission Card, not as
special cases. The source is a **label on the record**, never a different kind
of mission: there is no courier form and no phone-load form.

The template itself was already built and already worked; what was missing was
the way in. Intake only ran from a Python prompt, which is not a way for a man
with a phone in his hand to open a load.
"""

from __future__ import annotations

import pytest

from dispatch import commitment, mission_template as mt
from portal.models import sandbox


COMPLETE = {
    "customer": "Baptist Health Logistics",
    "pickup_location": "Jacksonville, FL 32202",
    "pickup_window": "2026-09-08 07:00",
    "delivery_location": "Gainesville, FL 32608",
    "delivery_window": "2026-09-08 11:00",
    "commodity": "Medical specimens",
}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield


@pytest.fixture()
def client():
    from portal.app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _create(client, source="PHONE", taken_by="Mike", **over):
    data = dict(COMPLETE, source=source, taken_by=taken_by, **over)
    return client.post("/intake", data=data, follow_redirects=False)


class TestOneWayInForEverySource:
    @pytest.mark.parametrize("source", ["PHONE", "CUSTOMER", "COURIER",
                                        "EMAIL", "TEXT", "JOE"])
    def test_every_manual_source_produces_a_candidate(self, client, source):
        assert _create(client, source=source).status_code == 302
        records = [r for r in sandbox.get_all().values()
                   if r.get("intake_source") == source]
        assert len(records) == 1
        assert commitment.state_of(records[0]) == commitment.CANDIDATE

    def test_the_records_are_identical_but_for_the_label(self, client):
        """A courier run and a phone load are the same object. If they were
        not, there would be two kinds of load and two sets of rules."""
        _create(client, source="PHONE")
        _create(client, source="COURIER")
        by_source = {r["intake_source"]: r for r in sandbox.get_all().values()
                     if r.get("intake_source")}
        ignore = {"id", "created_at", "updated_at", "events", "source_id",
                  "mission_number", "intake_source", "summary", "load_number",
                  "card_data"}
        phone = {k: v for k, v in by_source["PHONE"].items() if k not in ignore}
        courier = {k: v for k, v in by_source["COURIER"].items() if k not in ignore}
        assert phone == courier

    def test_the_source_is_recorded_because_it_is_a_real_question_later(self, client):
        _create(client, source="TEXT")
        record = [r for r in sandbox.get_all().values()
                  if r.get("intake_source") == "TEXT"][0]
        assert record["card_data"]["source"] == "text"

    def test_a_supplied_load_number_is_kept_exactly(self, client):
        _create(client, load_number="CVS-44912")
        record = [r for r in sandbox.get_all().values()
                  if r.get("intake_source") == "PHONE"][0]
        assert record["load_number"] == "CVS-44912"

    def test_dispatch_numbers_work_nobody_else_numbered(self, client):
        _create(client)
        record = [r for r in sandbox.get_all().values()
                  if r.get("intake_source") == "PHONE"][0]
        assert record["load_number"].startswith("L1-")
        assert record["card_data"]["load_id"] == ""


class TestItRefusesRatherThanLosingTheCall:
    def test_an_incomplete_load_is_not_created(self, client):
        response = client.post("/intake", data={"source": "PHONE",
                                                "taken_by": "Mike",
                                                "customer": "Somebody"})
        assert response.status_code == 400
        assert sandbox.get_all() == {}

    def test_everything_typed_comes_back(self, client):
        """Losing a call's worth of notes to a validation message is how a
        screen stops being used."""
        response = client.post("/intake", data={
            "source": "PHONE", "taken_by": "Mike",
            "customer": "Baptist Health Logistics",
            "notes": "Sally says detention after two hours"})
        html = response.get_data(as_text=True)
        assert "Baptist Health Logistics" in html
        assert "detention after two hours" in html

    def test_it_says_every_problem_not_the_first(self, client):
        html = client.post("/intake", data={"source": "PHONE",
                                            "taken_by": "Mike"}).get_data(as_text=True)
        assert html.count("<li>") >= 4

    def test_it_will_not_create_without_who_took_it(self, client):
        """A mission arrives on somebody's word and the record says whose."""
        response = client.post("/intake", data=dict(COMPLETE, source="PHONE"))
        assert response.status_code == 400
        assert "Who took it" in response.get_data(as_text=True)

    def test_an_unknown_source_is_refused(self, client):
        response = _create(client, source="TELEPATHY")
        assert response.status_code == 400


class TestTheCandidateQueue:
    def test_it_lists_candidates(self, client):
        _create(client)
        html = client.get("/candidates").get_data(as_text=True)
        assert "Baptist Health Logistics" in html
        assert "COMMIT" in html and "REJECT" in html

    def test_a_committed_mission_leaves_the_queue(self, client):
        """It has left Booking and belongs to Dispatch. A queue that keeps
        showing it is a queue he stops trusting to mean 'these need me'."""
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/commit")
        assert "Baptist Health" not in client.get("/candidates").get_data(as_text=True)

    def test_rejecting_records_rather_than_deletes(self, client):
        """The same broker rings back with the same lane, and what he offered
        last time is the useful thing to have."""
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/reject",
                    data={"reason": "Rate too low"})
        record = sandbox.get(record_id)
        assert record is not None
        assert record["rejected_at"]
        assert record["rejected_reason"] == "Rate too low"

    def test_a_rejected_candidate_leaves_the_queue(self, client):
        _create(client)
        record_id = list(sandbox.get_all())[0]
        client.post(f"/brief/mission/{record_id}/reject")
        assert "Baptist Health" not in client.get("/candidates").get_data(as_text=True)

    def test_it_counts_the_gaps_without_scoring_them(self, client):
        _create(client)
        html = client.get("/candidates").get_data(as_text=True)
        assert "with no entry" in html
        assert "%" not in html.split("cand-gaps")[1][:200]

    def test_an_empty_queue_says_so_plainly(self, client):
        html = client.get("/candidates").get_data(as_text=True)
        assert "Nothing waiting" in html


class TestThereIsOnlyOneTemplate:
    def test_the_screen_is_built_from_the_template(self, client):
        """Not a second field list. A form with its own list drifts from the
        record by the second revision."""
        html = client.get("/intake").get_data(as_text=True)
        for field in mt.TEMPLATE:
            assert 'name="%s"' % field.key in html, field.key

    def test_choosing_a_source_does_not_change_the_form(self, client):
        """There is no courier template."""
        phone = client.get("/intake?source=PHONE").get_data(as_text=True)
        courier = client.get("/intake?source=COURIER").get_data(as_text=True)
        assert phone.count('name="') == courier.count('name="')

    def test_sweep_and_api_are_not_offered_to_a_person(self, client):
        """They are how machines bring work in, never chosen on a screen."""
        offered = [key for key, _, _ in mt.MANUAL_SOURCES]
        assert "SWEEP" not in offered and "API" not in offered
