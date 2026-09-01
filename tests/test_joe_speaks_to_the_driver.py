"""The driver never becomes part of the troubleshooting chain.

    MISSION FIRST. TECHNICAL DETAILS SECOND.

Issued by the operator as a design correction after JOE answered "email me a
Mission Template" with an account of why a mail transport was not configured.
That is an engineering message. The driver's intent was *I need a Mission
Template*, and the method was secondary.

These tests hold two lines that are easy to say and easy to lose:

  - No engineering word reaches the glass. Enforced against the *rendered*
    screen, because the rule is about what a driver reads, not about what a
    function returns.

  - JOE never stops at the failure. Anything it reports being unable to do
    carries what happens instead, so the driver is handed a mission rather
    than a problem.

Translating is not lying. A notice that did not go out is still reported as
not gone out -- in words about the notice, not about the transport.
"""

from __future__ import annotations

import re

import pytest

from portal import cockpit, joe_voice


def visible_text(html: str) -> str:
    """What a driver actually reads: no markup, no scripts, no attributes."""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


class TestNoEngineeringWordReachesTheGlass:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    @pytest.mark.parametrize("view", ["PICKUP", "DELIVERY"])
    def test_the_rendered_screen_is_clean(self, client, view):
        html = client.get(f"/portal?view={view}",
                          follow_redirects=True).get_data(as_text=True)
        found = joe_voice.is_driver_safe(visible_text(html))
        assert found == [], f"{view} screen says: {found}"

    def test_the_guard_actually_catches_something(self):
        """A guard that cannot fail is not a guard."""
        assert joe_voice.is_driver_safe("TRANSMISSION: UNCONFIGURED")
        assert joe_voice.is_driver_safe("No SMTP host configured")
        assert joe_voice.is_driver_safe("dispatch.connectors registry missing")
        assert joe_voice.is_driver_safe("Arrival notice sent.") == []


class TestJoeAnswersTheIntentNotTheMethod:
    def test_the_template_is_still_delivered_when_email_is_not(self):
        """The driver asked for a Mission Template. He gets a Mission Template."""
        said = joe_voice.template_ready(delivered_by_email=False)
        assert said["headline"] == "MISSION TEMPLATE READY"
        assert "Here's your Mission Template now." == said["now"]
        assert joe_voice.is_driver_safe(joe_voice.spoken(said)) == []

    def test_it_can_offer_to_fill_it_in_together(self):
        said = joe_voice.template_ready(delivered_by_email=False,
                                        offer_to_fill=True)
        assert said["question"] == "Who is the broker?"
        assert "together" in said["now"]

    def test_the_headline_leads_with_the_objective_met(self):
        """READY, not FAILED. The method missed is the second line, not the first."""
        said = joe_voice.template_ready(delivered_by_email=False)
        assert "READY" in said["headline"]
        assert "couldn't" not in said["headline"].lower()


class TestJoeNeverStopsAtTheFailure:
    def test_every_cannot_send_carries_what_happens_instead(self):
        for status in ("UNCONFIGURED", "UNAVAILABLE", "ABSENT", "WHATEVER"):
            said = joe_voice.sending(status, what="the arrival notice",
                                     instead="The office sends it.")
            assert said["sent"] is False
            assert said["instead"], f"{status} left the driver with nothing to do"
            assert joe_voice.is_driver_safe(said["line"]) == []

    def test_a_working_send_says_so_plainly(self):
        said = joe_voice.sending("CONFIGURED", what="the arrival notice",
                                 instead="unused")
        assert said["sent"] is True
        assert said["line"] == "The arrival notice sent."


class TestTranslatingIsNotLying:
    """Hiding complexity is not claiming success. The driver acts on this."""

    def test_an_unsent_notice_is_never_reported_as_sent(self):
        record = {"card_data": {"load_id": "847261"}, "arrived_at": "2026-09-01T08:00:00"}
        notice = cockpit.arrival_notice_for(record, cockpit.MODE_DELIVERY)
        if not joe_voice.can_send(cockpit.transmission_status()):
            assert notice["delivery"]["sent"] is False
            assert "couldn't" in notice["delivery"]["line"]

    def test_the_precise_condition_stays_available_to_engineering(self):
        """Translated for the driver, not erased. The build still knows."""
        record = {"card_data": {"load_id": "847261"}}
        notice = cockpit.arrival_notice_for(record, cockpit.MODE_DELIVERY)
        assert notice["transmission"] in (
            "LIVE", "CONFIGURED", "UNCONFIGURED", "SIMULATED",
            "UNAVAILABLE", "MANUAL", "ABSENT", "UNVERIFIED")

    def test_the_completion_note_says_what_to_do_with_the_paperwork(self):
        """Not that a subsystem is missing -- that he should hold his paperwork."""
        record = {"card_data": {"load_id": "847261"}}
        effect = cockpit.completion_effect(record, cockpit.MODE_DELIVERY)
        assert joe_voice.is_driver_safe(effect["note"]) == []
