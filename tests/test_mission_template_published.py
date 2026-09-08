"""Dispatch publishes the form; JOE reads it instead of remembering it.

**Owner ruling, 2026-09-08.** He asked the question that produced this:

> *"How can Joe not know the forms that are in the company library? ... the
> level four agent should know all the documents and should be able to follow
> along in a field by field narration. Am I correct?"*

He was correct. JOE held eleven fields with eleven questions written by Code,
while the Mission Card had **thirty-three fields, each already carrying the
question to ask** in `Field.spoken` -- whose own comment reads *"a template read
aloud badly is a template nobody finishes."* The copy was already wrong: it had
no load number, which the card has always had.

He ruled: *"build B, publish the template from Dispatch."*

**These tests are mostly about there being one of it.** Two lists that must agree
will eventually disagree, and the second one is always the one nobody updates.
"""

from __future__ import annotations

import os

import pytest

from dispatch import mission_template as mt
from dispatch import opportunity
from dispatch.db import set_db_path
from portal.app import create_app

TOKEN = "template-test-token"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from portal.routes.joe_api import TOKEN_VAR

    set_db_path(tmp_path / "template.db")
    monkeypatch.setenv(TOKEN_VAR, TOKEN)
    yield create_app({"TESTING": True}).test_client()
    set_db_path(None)


def fetch(client):
    return client.get("/api/joe/mission-template",
                      headers={"Authorization": "Bearer " + TOKEN,
                               "X-Driver": "mike"})


class TestItPublishesTheWholeForm:
    def test_every_field_the_card_has(self, client):
        """Equality, not a selection. A published subset is a copy with extra
        steps, and the missing ones are the ones JOE would never learn to ask."""
        published = fetch(client).get_json()["fields"]
        assert [f["key"] for f in published] == [f.key for f in mt.TEMPLATE]

    def test_each_one_carries_the_question_to_ask(self, client):
        """The reason this endpoint exists. The form already knew what to say."""
        for field in fetch(client).get_json()["fields"]:
            assert field["spoken"], "%s has no spoken question" % field["key"]

    def test_the_order_is_the_card_order(self, client):
        """A form read out of order is a form read wrong. The card decides."""
        published = [f["key"] for f in fetch(client).get_json()["fields"]]
        assert published == [f.key for f in mt.TEMPLATE]

    def test_choices_travel_too(self, client):
        """A field meant to be counted must be picked from, and JOE cannot offer
        a list it was never given."""
        by_key = {f["key"]: f for f in fetch(client).get_json()["fields"]}
        with_choices = [f for f in mt.TEMPLATE if f.choices]
        assert with_choices, "the card has no choice fields -- check this test"
        for field in with_choices:
            assert by_key[field.key]["choices"] == list(field.choices)


class TestItSaysWhichFieldsReachTheContract:
    def test_the_mapping_is_published_not_re_derived(self, client):
        published = fetch(client).get_json()["fields"]
        mapped = {f["key"]: f["opportunity_field"] for f in published
                  if f["opportunity_field"]}
        expected = {card: contract
                    for contract, card in opportunity.ONTO_MISSION_CARD.items()}
        assert mapped == expected

    def test_the_contract_travels_with_it(self, client):
        contract = fetch(client).get_json()["opportunity"]
        assert contract["required"] == list(opportunity.REQUIRED)
        assert contract["fields"] == list(opportunity.FIELDS)
        assert contract["dictation_order"] == list(opportunity.dictation_order())

    def test_a_field_the_contract_cannot_carry_is_still_published(self, client):
        """**The card is bigger than the contract, and that is not a bug.** JOE
        asks for everything and sends what fits; a field left out of the
        publication is a field Mike would never be asked for at all."""
        by_key = {f["key"]: f for f in fetch(client).get_json()["fields"]}
        assert by_key["load_number"]["opportunity_field"] == ""
        assert by_key["load_number"]["spoken"]


class TestItIsAReadOfADefinition:
    """Why an eighth contract needed no new class of thinking: nothing
    operational passes through it."""

    def test_an_empty_node_publishes_the_same_form_as_a_busy_one(self, client):
        first = fetch(client).get_json()
        from dispatch import services

        services.create_driver(name="Mike Zachary")
        assert fetch(client).get_json() == first

    def test_it_is_refused_without_a_token(self, client):
        assert client.get("/api/joe/mission-template").status_code in (401, 403)


class TestThereIsOnlyOneRenderingOfTheFormForPeople:
    """**Owner correction, 2026-09-08:** *"I don't think you need to create a
    form that already exists. the load card and the mission brief are one and
    the same and already exist in dispatch."*

    He was right. `/intake` -- New Mission -- already renders the whole template,
    sectioned, from `mt.fields_in()`, and its own docstring says *"There is no
    courier form and no phone-load form."* A `/capture-sheet` page was built and
    deleted the same hour: it was a **third** rendering of one form, which is the
    thing that screen exists to prevent.

    **The endpoint is not a second rendering.** It publishes the definition in a
    form a machine can read -- keys, choices, the spoken question -- none of
    which a screen provides. One definition, one screen for people, one endpoint
    for JOE.
    """

    def test_the_screen_that_already_exists_shows_every_field(self, client):
        page = client.get("/intake").get_data(as_text=True)
        for field in mt.TEMPLATE:
            assert field.key in page, "%s is missing from New Mission" % field.key

    def test_there_is_no_second_page_for_people(self, client):
        """A page that duplicates New Mission would drift from it the first time
        a field was added to one and not the other."""
        assert client.get("/capture-sheet").status_code == 404

    def test_the_endpoint_carries_what_a_screen_cannot(self, client):
        """Why the endpoint is not the duplicate the page was: a rendered form
        gives JOE labels it would have to scrape. This gives it the question to
        ask and the list to offer."""
        published = fetch(client).get_json()["fields"]
        assert all(f["spoken"] for f in published)
        assert any(f["choices"] for f in published)
