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


#: The ruled one-page layout, 2026-09-15, section by section, in order. Written
#: out here on purpose: this is the one place a second list is the point -- it is
#: the Owner's ruling the template is checked against, not a copy JOE reads.
ONE_PAGE = (
    ("IDENTITY", "load_number", "Load Number"),
    ("IDENTITY", "mission_number", "Mission Number"),
    ("IDENTITY", "service", "Service Type"),
    ("MISSION SOURCE", "customer", "Customer / Shipper / Broker"),
    ("MISSION SOURCE", "customer_poc", "Their contact"),
    ("MISSION SOURCE", "customer_phone", "Their phone"),
    ("MISSION SOURCE", "customer_email", "Their email"),
    ("LOAD CONTROL", "controlled_by", "Load control"),
    ("LOAD CONTROL", "rate", "Rate"),
    ("LOAD CONTROL", "rate_basis", "Rate agreed with"),
    ("LOAD CONTROL", "payment_type", "Payment type"),
    ("LOAD CONTROL", "payor", "Paid by"),
    ("LOAD CONTROL", "amount", "Amount"),
    ("PICKUP", "pickup_location", "Pickup facility and address"),
    ("PICKUP", "pickup_window", "Pickup appointment"),
    ("PICKUP", "pickup_contact", "Pickup contact"),
    ("PICKUP", "pickup_phone", "Pickup phone"),
    ("PICKUP", "pickup_notes", "Pickup access instructions"),
    ("PICKUP", "pickup_special", "Pickup SPECIAL INSTRUCTIONS"),
    ("DELIVERY", "delivery_location", "Delivery facility and address"),
    ("DELIVERY", "delivery_window", "Delivery appointment"),
    ("DELIVERY", "delivery_contact", "Delivery contact"),
    ("DELIVERY", "delivery_phone", "Delivery phone"),
    ("DELIVERY", "delivery_notes", "Delivery access instructions"),
    ("DELIVERY", "delivery_special", "Delivery SPECIAL INSTRUCTIONS"),
    ("CARGO", "commodity", "Description"),
    ("CARGO", "pieces_pallets", "Pieces / Pallets"),
    ("CARGO", "weight_lbs", "Weight (lbs, total)"),
    ("NOTES", "notes", "Notes"),
)


class TestTheOnePageLayout:
    """**Owner direction, 2026-09-15.** He marked up a printed Mission Brief --
    *"this is the idea trying to get this to one page."* -- found it is the New
    Mission document, and answered: *"drop status type is LTL / Courier"*, load
    control *"2) yes either"*, *"cargo: 1) Description 2) Pieces / Pallets/ 3)
    Weight"*, then *"go ahead with the one page template"*."""

    def test_the_template_is_exactly_the_twenty_nine_fields_in_order(self):
        assert len(mt.TEMPLATE) == 29
        assert [(f.section, f.key, f.label) for f in mt.TEMPLATE] == list(ONE_PAGE)

    def test_the_sections_are_his_seven_in_his_order(self):
        assert mt.SECTIONS == ("IDENTITY", "MISSION SOURCE", "LOAD CONTROL",
                               "PICKUP", "DELIVERY", "CARGO", "NOTES")

    def test_service_type_is_ltl_or_courier(self):
        field = next(f for f in mt.TEMPLATE if f.key == "service")
        assert field.choices == ("LTL", "Courier")

    def test_load_control_is_customer_or_level_1(self):
        field = next(f for f in mt.TEMPLATE if f.key == "controlled_by")
        assert field.choices == ("Customer", "Level 1")

    def test_those_are_the_only_two_pick_lists(self):
        assert {f.key: f.choices for f in mt.TEMPLATE if f.choices} == {
            "service": ("LTL", "Courier"),
            "controlled_by": ("Customer", "Level 1")}

    def test_the_mission_number_is_assigned_not_typed(self):
        assigned = [f.key for f in mt.TEMPLATE if f.assigned]
        assert assigned == ["mission_number"]
        assert "mission_number" not in mt.ENTERED_KEYS

    @pytest.mark.parametrize("gone", [
        "control_name", "control_role", "control_phone", "control_email",
        "pickup_shipper", "delivery_control_name", "cargo_lines", "pallets",
        "pieces", "status", "intake_source", "intake_taken_by"])
    def test_a_removed_field_is_not_on_the_template(self, gone):
        assert gone not in mt.TEMPLATE_KEYS

    def test_no_capture_field_became_required(self):
        """Required-ness is unchanged for what remains; nothing new is required."""
        assert mt.REQUIRED_KEYS == ("customer", "pickup_location", "pickup_window",
                                    "delivery_location", "delivery_window",
                                    "commodity")
        assert opportunity.REQUIRED == ()

    def test_stops_no_longer_carry_load_control(self):
        assert mt.STOP_KEYS == ("facility", "window", "poc", "phone", "notes",
                                "special")

    def test_the_published_template_is_the_one_page(self, client):
        published = fetch(client).get_json()
        assert [f["key"] for f in published["fields"]] == [k for _, k, _ in ONE_PAGE]
        assert published["sections"] == list(mt.SECTIONS)


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
        # Owner rulings, 2026-09-15: no capture is refused for want of any one
        # field. The published list says so, rather than a list JOE would enforce.
        assert contract["required"] == []
        assert contract["fields"] == list(opportunity.FIELDS)
        assert contract["fields"][:3] == list(opportunity.KEY_FACTS)
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

    def test_new_mission_renders_exactly_the_twenty_nine(self, client):
        """Through the real /intake route: one named control per template field,
        in template order, and nothing else -- no Taken by, no removed field."""
        import re

        page = client.get("/intake").get_data(as_text=True)
        named = re.findall(r'<(?:input|select|textarea)[^>]*\bname="([^"]+)"', page)
        assert named == [f.key for f in mt.TEMPLATE]
        assert "Taken by" not in page and 'name="taken_by"' not in page

    def test_the_mission_number_is_shown_but_not_typed(self, client):
        import re

        page = client.get("/intake").get_data(as_text=True)
        control = re.search(r'<input[^>]*name="mission_number"[^>]*>', page).group(0)
        assert "readonly" in control
        assert "Assigned by Dispatch" in control

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
