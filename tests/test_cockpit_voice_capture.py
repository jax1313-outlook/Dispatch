"""Log a load by voice from the Driver Cockpit (2026-09-15).

Owner direction: the cockpit's own voice channel, through the tablet's own
dictation and his headset, *"used to capture load board information"*; then
*"Start the voice mic button on the cockpit next"*. The need: *"A rapid way to
capture load information for later decision making."*

Only words reach Dispatch. These tests post words the way the drawer's script
does -- JSON, with the CSRF header the cockpit sends -- through a real sign-in
gate (LOGIN_DISABLED False), so the route is reached the way the screen reaches
it (THE TEST REALITY RULE).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dispatch import commitment, opportunity
from dispatch.db import set_db_path
from portal import joe_voice, voice_capture
from portal.models import sandbox

URL = "/portal/voice-capture"


@pytest.fixture(autouse=True)
def _world(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    from dispatch import scheduling

    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False, raising=False)
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app

    app = create_app({"TESTING": True, "LOGIN_DISABLED": False})
    with app.test_client() as c:
        yield c


def as_driver(client):
    with client.session_transaction() as s:
        s["driver_open"] = True
        s["role"] = "Driver"


def as_operations(client):
    with client.session_transaction() as s:
        s["user_id"] = "ops-test"
        s["role"] = "Operations"


def say(client, text, **extra):
    return client.post(URL, json=dict({"text": text}, **extra))


def visible_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


class TestOneLoad:
    def test_one_load_is_logged_carded_and_read_back(self, client):
        as_driver(client)
        resp = say(client, "Jacksonville FL to Savannah GA, dry van, twenty two hundred, pickup Thursday")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True and len(data["loads"]) == 1
        load = data["loads"][0]
        assert load["status"] == "LOGGED" and load["verdict"] == "NEW"
        assert load["say"].startswith("LOGGED. OPPORTUNITY OPP-")
        assert "JACKSONVILLE FL TO SAVANNAH GA" in load["say"] and "$2200" in load["say"]
        assert "OPP-" not in load["speak"]  # the headset is spared the record number
        stored = opportunity.get(load["opportunity_id"])
        assert stored["captured_via"] == "VOICE" and stored["rate"] == 2200.0
        assert load["carded"] is True
        assert sandbox.get(load["card_id"])["card_data"]["origin"] == "Jacksonville FL"

    def test_the_audit_says_voice(self, client):
        from dispatch import audit

        as_driver(client)
        load = say(client, "Tampa to Miami 900").get_json()["loads"][0]
        rows = audit.entries(mission_id=load["opportunity_id"])
        assert rows and rows[-1]["channel"] == audit.CHANNEL_VOICE
        assert rows[-1]["action"] == "opportunity-capture"

    def test_nothing_heard_stores_nothing(self, client):
        as_driver(client)
        resp = say(client, "   ")
        assert resp.status_code == 400 and resp.get_json()["say"] == "NOTHING HEARD."
        assert opportunity.all_open() == []


class TestNextSeparatesLoads:
    def test_several_loads_in_one_breath_are_logged_in_order(self, client):
        as_driver(client)
        data = say(client, "Tampa to Miami 900 next Orlando to Atlanta $1,400 next load "
                           "Dallas to Houston seven fifty").get_json()
        lanes = [(l["fields"]["origin"], l["fields"]["destination"]) for l in data["loads"]]
        assert lanes == [("Tampa", "Miami"), ("Orlando", "Atlanta"), ("Dallas", "Houston")]
        assert [l["status"] for l in data["loads"]] == ["LOGGED"] * 3
        assert len(opportunity.all_open()) == 3

    def test_next_on_its_own_line_when_typed(self):
        assert voice_capture.split_loads("Tampa to Miami 900\nnext\nOrlando to Atlanta 1400\nNext.") == [
            "Tampa to Miami 900", "Orlando to Atlanta 1400"]

    def test_next_tuesday_is_a_date_not_a_new_load(self):
        pieces = voice_capture.split_loads("Tampa to Miami 900 pickup next Tuesday next Orlando to Atlanta 1400")
        assert pieces == ["Tampa to Miami 900 pickup next Tuesday", "Orlando to Atlanta 1400"]


class TestTheOneQuestion:
    def test_a_missing_rate_asks_and_stores_nothing(self, client):
        as_driver(client)
        data = say(client, "Savannah to Atlanta dry van pickup Friday").get_json()
        load = data["loads"][0]
        assert load["status"] == "QUESTION" and load["question"] == "RATE?"
        assert load["say"] == "SAVANNAH TO ATLANTA. RATE?"
        assert load["words"] == "Savannah to Atlanta dry van pickup Friday"
        assert load["opportunity_id"] == "" and opportunity.all_open() == []

    def test_answering_the_question_logs_the_load(self, client):
        as_driver(client)
        words = say(client, "Savannah to Atlanta dry van").get_json()["loads"][0]["words"]
        data = say(client, words, answer="eighteen fifty").get_json()
        load = data["loads"][0]
        assert load["status"] == "LOGGED" and opportunity.get(load["opportunity_id"])["rate"] == 1850.0

    def test_a_skip_leaves_it_unlogged(self, client):
        as_driver(client)
        data = say(client, "Savannah to Atlanta dry van", answer="skip").get_json()
        assert data["loads"][0]["status"] == "NOT LOGGED" and opportunity.all_open() == []

    def test_an_unheard_answer_asks_again(self, client):
        as_driver(client)
        data = say(client, "Savannah to Atlanta dry van", answer="umm").get_json()
        assert data["loads"][0]["question"] == "RATE?" and opportunity.all_open() == []

    def test_only_one_question_is_said_at_a_time(self, client):
        as_driver(client)
        data = say(client, "Savannah to Atlanta next Tampa to Miami 900 next Mobile to Macon").get_json()
        assert [l["status"] for l in data["loads"]] == ["QUESTION", "LOGGED", "QUESTION"]
        assert data["say"].count("RATE?") == 1 and data["say"].endswith("SAVANNAH TO ATLANTA. RATE?")

    def test_no_lane_is_not_logged_and_the_words_are_kept(self, client):
        as_driver(client)
        load = say(client, "twenty two hundred dry van").get_json()["loads"][0]
        assert load["status"] == "NOT LOGGED" and load["words"] == "twenty two hundred dry van"
        assert opportunity.all_open() == []


class TestDuplicates:
    def test_the_same_load_twice_merges_onto_one_card(self, client):
        as_driver(client)
        first = say(client, "Tampa to Miami 900 pickup 9/17").get_json()["loads"][0]
        second = say(client, "Tampa to Miami 900 pickup 9/17 broker is Coastal").get_json()["loads"][0]
        assert second["status"] == "MERGED" and second["verdict"] == "MERGED"
        assert second["opportunity_id"] == first["opportunity_id"]
        assert second["card_id"] == first["card_id"]
        assert second["say"].startswith("MERGED INTO EXISTING.")
        assert len(opportunity.all_open()) == 1

    def test_a_different_rate_on_the_same_lane_is_flagged_not_merged(self, client):
        as_driver(client)
        say(client, "Tampa to Miami 900")
        second = say(client, "Tampa to Miami 2400").get_json()["loads"][0]
        assert second["verdict"] == "AMBIGUOUS" and "POSSIBLE DUPLICATE" in second["say"]


class TestWhoMayUseIt:
    def test_a_driver_sign_in_may(self, client):
        as_driver(client)
        assert say(client, "Tampa to Miami 900").status_code == 200

    def test_operations_may(self, client):
        as_operations(client)
        load = say(client, "Tampa to Miami 900").get_json()["loads"][0]
        assert opportunity.get(load["opportunity_id"])["captured_by"] == "ops-test"

    def test_nobody_signed_in_may_not(self, client):
        resp = say(client, "Tampa to Miami 900")
        assert resp.status_code == 302 and "/login" in resp.headers["Location"]
        assert opportunity.all_open() == []

    @pytest.mark.parametrize("path", ["/booking", "/intake", "/loads"])
    def test_the_driver_still_reaches_no_operations_page(self, client, path):
        as_driver(client)
        resp = client.get(path)
        assert resp.status_code == 302 and "/login" in resp.headers["Location"]

    def test_without_the_token_it_is_refused(self, client):
        as_driver(client)
        resp = client.post(URL, json={"text": "Tampa to Miami 900"}, csrf=False)
        assert resp.status_code == 403 and opportunity.all_open() == []

    def test_a_plain_form_post_says_it_in_the_joe_line(self, client):
        as_driver(client)
        resp = client.post(URL, data={"text": "Tampa to Miami 900"}, follow_redirects=True)
        assert resp.status_code == 200
        assert "LOGGED. OPPORTUNITY OPP-" in resp.get_data(as_text=True)


class TestCaptureOnly:
    def test_the_channel_is_a_ratified_one(self):
        assert voice_capture.CHANNEL in opportunity.CHANNELS

    def test_it_never_commits_passes_or_sends(self):
        source = Path("portal/voice_capture.py").read_text(encoding="utf-8")
        for word in ("commitment", "commit(", "discard(", "reject(", "mail", "send(", "publisher"):
            assert word not in source, word

    def test_the_ratified_contract_is_not_what_the_cockpit_calls(self):
        template = Path("portal/templates/joe_portal.html").read_text(encoding="utf-8")
        assert "/api/joe/opportunity" not in template

    # A voice capture matching a committed load must not change that card. On
    # this branch's base (896689b) it does -- from_capture fills the committed
    # card's gaps -- and the guard belongs to from_capture on another branch.
    # The test is held in VOICE_MIC_NOTES.md for the merge, not xfailed here.


class TestTheDrawer:
    def page(self, client):
        return client.get("/portal", follow_redirects=True).get_data(as_text=True)

    def test_the_talk_card_is_near_the_top_of_mission_actions(self, client):
        as_driver(client)
        html = self.page(client)
        column = html[html.index('aria-label="Mission actions"'):]
        column = column[:column.index("</section>")]
        assert 'id="voice-card"' in column and 'data-drawer="voice"' in column
        assert column.index('id="voice-card"') < column.index("FACILITY MAP")

    def test_the_drawer_has_the_mic_button_and_the_fallback_box(self, client):
        as_driver(client)
        html = self.page(client)
        drawer = html[html.index('id="drawer-voice"'):]
        drawer = drawer[:drawer.index("</aside>")]
        assert "TAP TO TALK" in drawer and 'id="voice-talk"' in drawer
        assert '<textarea id="voice-words"' in drawer and 'name="text"' in drawer
        assert "microphone key" in drawer and "LOG IT" in drawer
        assert 'action="/portal/voice-capture"' in drawer
        assert "READ-BACK" in drawer

    def test_the_script_listens_with_the_browsers_own_recognition_only(self):
        template = Path("portal/templates/joe_portal.html").read_text(encoding="utf-8")
        assert "window.SpeechRecognition || window.webkitSpeechRecognition" in template
        assert "speechSynthesis" in template
        # Words only: no recording, no sound sent anywhere.
        for forbidden in ("getUserMedia", "MediaRecorder", "AudioContext", "Blob("):
            assert forbidden not in template

    def test_no_engineering_word_on_the_glass(self, client):
        as_driver(client)
        found = joe_voice.is_driver_safe(visible_text(self.page(client)))
        assert found == []

    def test_every_line_the_route_says_is_driver_safe(self, client):
        as_driver(client)
        data = say(client, "Tampa to Miami 900 next Savannah to Atlanta next dry van").get_json()
        for load in data["loads"]:
            assert joe_voice.is_driver_safe(load["say"]) == []
