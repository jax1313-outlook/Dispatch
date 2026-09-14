"""The three portals ask the Library PIN Service (portal/models/pin_service.py).

Mike Zachary, 2026-09-13:
  * Operations Portal -> PIN Service; Driver Portal -> PIN Service; Customer
    Portal -> PIN Service. The answer is Authenticated with a role, or Denied.
  * "Driver PINS should be no more that 4 digits/characters long and
    unassigned, created by a driver." Then: "the PIN window opens ... Driver
    enters 4 characters ... repeat the entry ... No other information or
    verification is needed." Any 4 characters; no identity.
  * "Customer Load Number from Load card will be the Customer PIN and auto sent
    to the email on file at the time of the load commital as a separate email
    template explaining the use of the Portal and it's entry system. This is
    part of the On-boarding Packet."
  * "Operations PIN will be Authorized by Mike Zachary through voice or dialog
    box entry with Joe."
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

_SRC = os.environ.get("DISPATCH_LIBRARY_SRC") or str(Path(__file__).resolve().parents[2] / "Library" / "src")
if Path(_SRC, "dispatch_library", "catalog").is_dir() and _SRC not in sys.path:
    sys.path.insert(0, _SRC)
dispatch_library = pytest.importorskip("dispatch_library.catalog", reason="the Library repository is not on this machine")

from dispatch import notifications, services  # noqa: E402
from dispatch.db import set_db_path  # noqa: E402

MIKE = "Mike Zachary"
REMOTE = {"REMOTE_ADDR": "192.168.8.21"}


@pytest.fixture(autouse=True)
def _world(tmp_path, monkeypatch):
    set_db_path(tmp_path / "dispatch.db")
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
    monkeypatch.setenv("DISPATCH_LIBRARY_CATALOG", str(tmp_path / "catalog.db"))
    from dispatch import scheduling
    monkeypatch.setattr(scheduling, "_outlook_is_running", lambda: False)
    yield
    set_db_path(None)


@pytest.fixture
def pins():
    service = dispatch_library.open_pin_service()
    yield service
    service.db.close()


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app({"TESTING": True, "LOGIN_DISABLED": False})
    with app.test_client() as c:
        yield c


def sign_in_operations(client, pins, name=MIKE, pin="7301"):
    if not pins.identity("Operations", name):
        pins.create_pin("Operations", name, pin, requested_by=MIKE, channel="DIALOG")
    assert client.post("/login", data={"pin": pin}).status_code == 302


def test_the_library_checkout_is_found_from_dispatch_library_src(monkeypatch, tmp_path):
    from portal.models import ensure_library_importable
    (tmp_path / "dispatch_library").mkdir()
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("DISPATCH_LIBRARY_SRC", str(tmp_path))
    ensure_library_importable()
    ensure_library_importable()
    assert sys.path.count(str(tmp_path)) == 1 and sys.path[0] == str(tmp_path)


# ── Operations ───────────────────────────────────────────────────────

class TestOperations:
    def test_signs_in_with_a_library_pin(self, client, pins):
        pins.create_pin("operations", MIKE, "7301", requested_by=MIKE, channel="DIALOG")
        assert client.get("/home").status_code == 302  # gate still closed

        resp = client.post("/login", data={"pin": "7301"})
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/home")
        with client.session_transaction() as s:
            assert (s["role"], s["display_name"]) == ("Operations", MIKE)
        assert client.get("/home").status_code == 200

    def test_denied_for_a_wrong_pin(self, client, pins):
        pins.create_pin("operations", MIKE, "7301", requested_by=MIKE, channel="DIALOG")
        resp = client.post("/login", data={"pin": "0000"})
        assert resp.status_code == 401 and b"Denied" in resp.data
        with client.session_transaction() as s:
            assert "user_id" not in s

    def test_a_denied_pin_is_not_retried_against_identity_json(self, client):
        from portal.models import identity
        identity.bootstrap_authority("authority", MIKE, "5555")
        assert client.post("/login", data={"pin": "5555"}).status_code == 401

    def test_login_says_so_when_the_library_is_missing(self, client, monkeypatch):
        monkeypatch.setitem(sys.modules, "dispatch_library.catalog", None)
        resp = client.post("/login", data={"pin": "7301"})
        assert resp.status_code == 503 and b"cannot be imported" in resp.data


class TestJoeDialogForOperationsPins:
    def _authorize(self, client, **form):
        data = {"name": "Dana Cole", "pin": "7301", "pin_again": "7301", "action": "create"}
        data.update(form)
        return client.post("/joe/operations-pin", data=data)

    def test_mike_authorizes_the_first_pin_at_the_server(self, client, pins):
        page = client.get("/joe/operations-pin")
        assert page.status_code == 200 and b"Authorized by" in page.data
        resp = self._authorize(client, authorized_by=MIKE, name=MIKE)
        assert resp.status_code == 200 and b"can now sign in to Operations" in resp.data
        created = next(e for e in pins.events() if e["action"] == "CREATE_PIN")
        assert (created["actor"], created["channel"]) == (MIKE, "DIALOG")
        assert client.post("/login", data={"pin": "7301"}).status_code == 302

    def test_nobody_else_authorizes_the_first_pin(self, client, pins):
        resp = self._authorize(client, authorized_by="Dana Cole")
        assert resp.status_code == 400 and b"authorized by Mike Zachary" in resp.data
        assert not pins.identities("Operations")

    def test_the_first_pin_is_not_offered_away_from_the_server(self, client, pins):
        resp = client.post("/joe/operations-pin", data={"authorized_by": MIKE, "name": MIKE, "pin": "7301",
                                                        "pin_again": "7301"}, environ_base=REMOTE)
        assert resp.status_code == 403
        assert not pins.identities("Operations")

    def test_after_that_only_mike_signed_in_authorizes(self, client, pins):
        pins.create_pin("Operations", MIKE, "7301", requested_by=MIKE, channel="DIALOG")
        # Not signed in: even at the server, the form cannot name Mike any more.
        assert self._authorize(client, authorized_by=MIKE).status_code == 403

        sign_in_operations(client, pins)
        resp = self._authorize(client, authorized_by="ignored", pin="8800", pin_again="8800")
        assert resp.status_code == 200 and b"as authorized by Mike Zachary" in resp.data
        assert pins.identity("Operations", "Dana Cole")

        client.post("/logout")
        sign_in_operations(client, pins, name="Dana Cole", pin="8800")
        assert self._authorize(client, name="Lee Park", pin="8800", pin_again="8800").status_code == 403
        assert pins.identity("Operations", "Lee Park") is None

    def test_mike_changes_a_pin(self, client, pins):
        sign_in_operations(client, pins)
        assert self._authorize(client, pin="8800", pin_again="8800").status_code == 200
        resp = self._authorize(client, pin="9926", pin_again="9926", action="reset")
        assert resp.status_code == 200 and b"PIN is changed" in resp.data
        assert not pins.validate("Operations", "8800", client_key="x").authenticated
        assert pins.validate("Operations", "9926", client_key="x").display_name == "Dana Cole"

    def test_two_people_cannot_share_a_pin(self, client, pins):
        sign_in_operations(client, pins)
        resp = self._authorize(client)  # 7301 is already Mike's
        assert resp.status_code == 400 and b"already belongs" in resp.data

    def test_mismatched_pins_are_asked_again(self, client, pins):
        resp = self._authorize(client, authorized_by=MIKE, pin_again="7302")
        assert resp.status_code == 400 and b"not the same" in resp.data


# ── Driver ───────────────────────────────────────────────────────────

class TestDrivers:
    """1) the PIN window opens 2) four characters 3) repeat 4) saved. Nothing else."""

    def window(self, client, pin, again=None):
        return client.post("/driver/choose-pin", data={"pin": pin, "pin_again": pin if again is None else again})

    def test_the_pin_window_saves_four_characters_and_opens_the_portal(self, client):
        page = client.get("/driver/login")
        assert b'name="phone"' not in page.data and b"Set up a PIN" in page.data
        window = client.get("/driver/choose-pin")
        assert window.status_code == 200 and b'name="driver_id"' not in window.data
        resp = self.window(client, "q7z4")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/driver/home")
        assert client.get("/driver/home").status_code == 200
        assert client.get("/home").status_code == 302  # a Driver session is not an Operations session

        client.post("/driver/logout")
        assert client.get("/driver/home").status_code == 302
        resp = client.post("/driver/login", data={"pin": "Q7Z4"})
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/driver/home")

    @pytest.mark.parametrize("pin", ["12345", "123"])
    def test_a_driver_pin_is_four_characters(self, client, pin):
        assert self.window(client, pin).status_code == 400
        with client.session_transaction() as s:
            assert not s.get("driver_open")

    def test_the_two_entries_must_match(self, client):
        assert self.window(client, "4418", "4481").status_code == 400

    def test_it_does_not_matter_who_holds_which(self, client):
        self.window(client, "4418")
        client.post("/driver/logout")
        assert self.window(client, "4418").status_code == 302  # the same four characters again
        client.post("/driver/logout")
        assert client.post("/driver/login", data={"pin": "4418"}).status_code == 302

    def test_a_pin_never_entered_is_denied(self, client):
        assert client.post("/driver/login", data={"pin": "9999"}).status_code == 401

    def test_the_cockpit_shows_the_fleets_active_loads(self, client):
        ray = services.create_driver(name="Ray Vasquez", phone="904-555-0101")
        dana = services.create_driver(name="Dana Cole", phone="904-555-0202")
        rays = services.create_load(customer="XPO Logistics")
        danas = services.create_load(customer="Werner")
        services.assign_driver(rays["load_id"], ray["driver_id"])
        services.assign_driver(danas["load_id"], dana["driver_id"])
        self.window(client, "4418")
        home = client.get("/driver/home").data.decode()
        assert "XPO Logistics" in home and "Werner" in home

    def test_a_fuel_receipt_asks_for_no_driver(self, client):
        # The Driver Portal is a workspace entry control, not identity verification (2026-09-13).
        truck = services.create_equipment(unit_number="T-1", equipment_type="other")
        self.window(client, "4418")
        assert b'name="driver_id"' not in client.get("/driver/home").data
        resp = client.post("/driver/fuel-receipt", data={"equipment_id": truck["equipment_id"]},
                           follow_redirects=True)
        assert b"A photo of the receipt is required" in resp.data

    def test_forgot_pin_points_to_the_pin_window(self, client):
        resp = client.post("/driver/forgot-pin", data={"phone": "904", "recovery_word": "x", "new_pin": "1234"})
        assert resp.status_code == 400 and b"Set up a PIN" in resp.data


# ── Customer ─────────────────────────────────────────────────────────

class FakeMail:
    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    def send(self, to, subject, body, **kwargs):
        self.sent.append({"to": to, "subject": subject, "body": body})
        return {"ok": self.ok, "blocker": "" if self.ok else "Outlook is not open"}


@pytest.fixture
def mail(monkeypatch):
    fake = FakeMail()
    from portal.routes import joe_portal
    monkeypatch.setattr(joe_portal, "_mail_connector", lambda: fake)
    return fake


def committed_mission(client, *, customer="XPO Logistics", load_number="8842193", email="loads@xpo.example",
                      origin="Jacksonville, FL", destination="Atlanta, GA", phone=""):
    from portal.models import sandbox
    entry = sandbox.create_entry(source_type="dispatch", source_id=load_number, title="Portal probe",
                                 card_data={"origin": origin, "destination": destination}, summary="")
    data = sandbox._load()
    data[entry["id"]].update({"customer": customer, "load_number": load_number, "customer_email": email,
                              "customer_phone": phone})
    sandbox._save(data)
    resp = client.post(f"/brief/mission/{entry['id']}/commit")
    assert resp.status_code == 302
    return sandbox.get(entry["id"])


class TestCustomerPortalAccessAtCommit:
    def test_commit_makes_the_load_number_a_pin_and_sends_the_portal_email(self, client, pins, mail):
        sign_in_operations(client, pins)
        record = committed_mission(client)

        access = record["portal_access"]
        assert (access["pin"], access["sent"], access["to"]) == ("CREATED", True, ["loads@xpo.example"])
        assert len(mail.sent) == 1
        email = mail.sent[0]
        assert email["to"] == ["loads@xpo.example"] and "8842193" in email["subject"]
        assert "8842193" in email["body"] and "/portal/login" in email["body"]
        assert "XPO Logistics" in email["body"]
        created = next(e for e in pins.events() if e["action"] == "CREATE_PIN")
        assert (created["actor"], created["channel"]) == (MIKE, "LOAD_COMMIT")

        # The Mission Visibility Communication Flow, step by step (playbook Section 4A).
        flow = access["flow"]
        assert flow["joe"] == {"mission_visibility": "OPENED", "communication_required": True}
        assert any(e["action"] == "mission_visibility_opened" and e["via"] == "JOE" for e in record["events"])
        from portal.models import publisher
        card = next(a for a in publisher.get_queue() if a["id"] == flow["publisher"]["action_id"])
        assert (card["action_type"], card["status"], card["requested_for"]) == ("Customer Portal Access", "ARCHIVED", MIKE)
        assert card["communication"]["to"] == "loads@xpo.example" and card["communication"]["body"] == email["body"]
        assert flow["comi"]["channel"] == "customer_email" and flow["comi"]["status"] == "routed"
        assert flow["comi"]["communication_event_id"].startswith("comi-")
        assert flow["email_helper"] == {"transport": "mail_connector", "sent": True}
        assert card["communication_result"]["sent_by"] == MIKE

        client.post("/logout")
        assert client.post("/portal/login", data={"pin": "8842193"}).status_code == 302
        resp = client.get("/portal/mission")
        assert b"8842193" in resp.data and b"Jacksonville, FL" in resp.data

    def test_the_portal_address_comes_from_the_setting_when_there_is_one(self, client, pins, mail, monkeypatch):
        monkeypatch.setenv("DISPATCH_PORTAL_URL", "https://portal.l1truck.example/")
        sign_in_operations(client, pins)
        committed_mission(client)
        assert "https://portal.l1truck.example/portal/login" in mail.sent[0]["body"]

    def test_nobody_signed_in_by_name_means_no_pin_and_no_email(self, pins, mail):
        from portal.app import create_app
        app = create_app()
        app.config["TESTING"] = True  # the open application: no sign-in
        with app.test_client() as open_client:
            record = committed_mission(open_client)
        assert record["portal_access"]["pin"] == "NOT_CREATED" and not mail.sent
        assert "Nobody was signed in" in record["portal_access"]["note"]

    def test_a_load_number_held_by_another_customer_sends_nothing(self, client, pins, mail):
        pins.add_customer_load("Werner", "8842193", requested_by=MIKE)
        sign_in_operations(client, pins)
        record = committed_mission(client, customer="XPO Logistics")
        assert (record["portal_access"]["pin"], record["portal_access"]["sent"]) == ("NOT_CREATED", False)
        assert not mail.sent
        assert pins.validate("Customer", "8842193", client_key="c").display_name == "Werner"

    def test_no_email_or_phone_on_file_makes_the_pin_and_says_nothing_was_sent(self, client, pins, mail):
        sign_in_operations(client, pins)
        record = committed_mission(client, email="")
        assert (record["portal_access"]["pin"], record["portal_access"]["sent"]) == ("CREATED", False)
        assert "no customer email or phone number on file" in record["portal_access"]["note"] and not mail.sent

    def test_no_email_uses_the_customer_phone_number(self, client, pins, mail):
        # Mike Zachary, 2026-09-14: "if no address then use customer Phone Number. Example: 888-745-1234".
        from portal.models import publisher
        sign_in_operations(client, pins)
        record = committed_mission(client, email="", phone="888-745-1234")
        access = record["portal_access"]
        assert access["pin"] == "CREATED" and access["to"] == ["888-745-1234"] and not mail.sent
        assert access["flow"]["comi"] == dict(access["flow"]["comi"], channel="customer_text", status="routed")
        assert access["sent"] is False and "no text-message sender" in access["note"]
        card = next(a for a in publisher.get_queue() if a["id"] == access["flow"]["publisher"]["action_id"])
        assert card["status"] == "READY" and card["communication"]["channel"] == "text"
        assert "8842193" in card["communication"]["body"] and "/portal/login" in card["communication"]["body"]

    def test_email_wins_over_phone(self, client, pins, mail):
        sign_in_operations(client, pins)
        record = committed_mission(client, phone="888-745-1234")
        assert record["portal_access"]["to"] == ["loads@xpo.example"] and record["portal_access"]["sent"] is True

    def test_a_failed_send_is_recorded_as_not_sent_and_stays_in_front_of_operations(self, client, pins, monkeypatch):
        from portal.models import publisher
        from portal.routes import joe_portal
        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: FakeMail(ok=False))
        sign_in_operations(client, pins)
        record = committed_mission(client)
        assert record["portal_access"]["sent"] is False
        assert "Outlook is not open" in record["portal_access"]["note"]
        card = next(a for a in publisher.get_queue() if a["id"] == record["portal_access"]["flow"]["publisher"]["action_id"])
        assert card["status"] == "READY"  # not ARCHIVED: Operations still sees it

    def test_without_a_mail_connector_email_helper_writes_the_outbox_and_says_it_was_not_sent(
            self, client, pins, monkeypatch, tmp_path):
        from dispatch import mail as dispatch_mail
        from portal.routes import joe_portal
        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: None)
        sign_in_operations(client, pins)
        record = committed_mission(client)
        access = record["portal_access"]
        assert access["sent"] is False and access["flow"]["email_helper"]["transport"] == "dispatch_mail"
        assert "not sent (SMTP not configured)" in access["note"]
        written = list(Path(dispatch_mail._OUTBOX).glob("portal-access-comi-*.eml"))
        assert len(written) == 1 and b"8842193" in written[0].read_bytes()

    def test_comi_routes_only_what_it_should(self):
        from dispatch import comi_routing
        evaluation = comi_routing.evaluate_comi_routing("R-1", comi_routing.MISSION_VISIBILITY_OPENED)
        assert evaluation["recommended_channel"] == "customer_email" and "customer" in evaluation["recipient_roles"]
        card = {"id": "PUB-1", "status": "READY", "human_approval_required": False,
                "communication": {"recipient_role": "customer", "to": "a@b.example", "subject": "s", "body": "b"}}
        assert comi_routing.route_communication(evaluation, card)["status"] == "routed"
        assert comi_routing.route_communication(evaluation, dict(card, status="PENDING"))["status"] == "not_routed"
        milestone = comi_routing.evaluate_comi_routing("R-1", "milestone_update")
        assert comi_routing.route_communication(milestone, card)["status"] == "not_routed"

    def test_email_helper_sends_for_a_person_never_a_system(self):
        from portal.models import email_helper
        route = {"status": "routed", "to": ["a@b.example"], "subject": "s", "body": "b"}
        for who in ("", None, "SYSTEM", "publisher"):
            assert email_helper.send_communication(route, sent_by=who, mail_connector=lambda: FakeMail())["sent"] is False

    def test_the_template_is_part_of_the_onboarding_packet(self):
        from portal import portal_access
        assert "customer_portal_access" in portal_access.ONBOARDING_PACKET
        assert (Path(portal_access.__file__).parent / "templates" / portal_access.TEMPLATE).is_file()


class TestMissionVisibilityKey:
    """Playbook Section 4A: the Customer Load Number is a Mission Visibility Key, and it is
    mission-scoped -- it opens the one mission whose Mission Record carries it, nothing else."""

    def open_load_for(self, record, **load_fields):
        """Dispatch opens the committed mission as a load (engine_load_id)."""
        from portal.models import sandbox
        load = services.create_load(**load_fields)
        data = sandbox._load()
        data[record["id"]]["engine_load_id"] = load["load_id"]
        sandbox._save(data)
        return load

    def world(self, client, pins):
        sign_in_operations(client, pins)
        xpo = committed_mission(client, customer="XPO Logistics", load_number="8842193")
        xpo_sister = committed_mission(client, customer="XPO Logistics", load_number="8842204",
                                       origin="Savannah, GA")
        werner = committed_mission(client, customer="Werner", load_number="5500211", origin="Omaha, NE")
        loads = (self.open_load_for(xpo, customer="XPO Logistics", pickup_location="Jacksonville, FL"),
                 self.open_load_for(xpo_sister, customer="XPO Logistics", pickup_location="Savannah, GA"),
                 self.open_load_for(werner, customer="Werner", pickup_location="Omaha, NE"))
        client.post("/logout")
        return loads

    def test_the_key_opens_its_one_mission_and_nothing_else(self, client, pins, mail):
        xpo, xpo_sister, werner = self.world(client, pins)

        resp = client.post("/portal/login", data={"pin": "8842193"})
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/portal/mission")
        view = client.get("/portal/mission").data.decode()
        assert xpo["load_id"] in view and "Jacksonville, FL" in view
        assert xpo_sister["load_id"] not in view and "Savannah" not in view  # same customer, other mission
        assert werner["load_id"] not in view and "Omaha" not in view

        assert client.get(f"/portal/loads/{xpo['load_id']}").status_code == 200
        assert client.get(f"/portal/loads/{xpo_sister['load_id']}").status_code == 403
        assert client.get(f"/portal/loads/{werner['load_id']}?format=json").status_code == 403
        assert client.get(f"/portal/loads/{xpo_sister['load_id']}/evidence/EV-1").status_code == 403
        assert client.get("/home").status_code == 302  # not an Operations session

    def test_a_committed_mission_not_yet_opened_shows_its_summary(self, client, pins, mail):
        sign_in_operations(client, pins)
        committed_mission(client, customer="XPO Logistics", load_number="8842193")
        committed_mission(client, customer="XPO Logistics", load_number="8842204", origin="Savannah, GA")
        client.post("/logout")
        client.post("/portal/login", data={"pin": "88 42 193"})
        view = client.get("/portal/mission").data.decode()
        assert "8842193" in view and "Jacksonville, FL" in view
        assert "8842204" not in view and "Savannah" not in view

    def test_the_old_list_address_shows_the_mission(self, client, pins, mail):
        self.world(client, pins)
        client.post("/portal/login", data={"pin": "8842193"})
        assert client.get("/portal/loads").headers["Location"].endswith("/portal/mission")

    def test_a_key_with_no_mission_record_opens_nothing(self, client, pins):
        pins.add_customer_load("XPO Logistics", "7700001", requested_by=MIKE)
        other = services.create_load(customer="XPO Logistics")
        assert client.post("/portal/login", data={"pin": "7700001"}).status_code == 302
        view = client.get("/portal/mission").data.decode()
        assert "not available" in view and other["load_id"] not in view
        assert client.get(f"/portal/loads/{other['load_id']}").status_code == 403

    def test_a_record_for_another_customer_is_never_opened(self, client, pins, mail):
        sign_in_operations(client, pins)
        committed_mission(client, customer="Werner", load_number="5500211", origin="Omaha, NE")
        client.post("/logout")
        pins.add_customer_load("XPO Logistics", "55 00 211x", requested_by=MIKE)  # not the same key
        client.post("/portal/login", data={"pin": "5500211X"})
        assert "Omaha" not in client.get("/portal/mission").data.decode()

    def test_denied_for_an_unknown_key(self, client, pins, mail):
        self.world(client, pins)
        assert client.post("/portal/login", data={"pin": "1111111"}).status_code == 401
        assert client.get("/portal/mission").status_code == 302

    def test_signing_out_ends_the_view(self, client, pins, mail):
        xpo, *_ = self.world(client, pins)
        client.post("/portal/login", data={"pin": "8842193"})
        client.post("/portal/logout")
        assert client.get(f"/portal/loads/{xpo['load_id']}").status_code == 403
        assert client.get("/portal/mission").status_code == 302

    def test_token_links_still_work_without_a_key(self, client, pins, mail):
        *_, werner = self.world(client, pins)
        token = notifications.make_stakeholder_token(werner["load_id"])
        assert client.get(f"/portal/loads/{werner['load_id']}?token={token}").status_code == 200

    def test_repeated_misses_lock_the_device_out_of_that_portal(self, client, pins, mail):
        self.world(client, pins)
        for _ in range(5):
            client.post("/portal/login", data={"pin": "0000000"})
        assert client.post("/portal/login", data={"pin": "8842193"}).status_code == 401

    def test_without_the_catalog_the_customer_login_says_it_is_not_set_up(self, client, monkeypatch):
        monkeypatch.delenv("DISPATCH_LIBRARY_CATALOG")
        assert client.get("/portal/login").status_code == 503


# ── Mission evidence: load securement and freight condition photos ───────────

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class TestMissionEvidence:
    """Mike Zachary, 2026-09-13: "Load securement photos are a customer-facing Mission Visibility
    artifact." They become part of Mission Visibility, Customer Alerts, Mission Record history and
    the final mission package."""

    def mission_with_open_load(self, client, pins, **kw):
        from portal.models import sandbox
        sign_in_operations(client, pins)
        record = committed_mission(client, **kw)
        load = services.create_load(customer=kw.get("customer", "XPO Logistics"), pickup_location="Jacksonville, FL")
        data = sandbox._load()
        data[record["id"]]["engine_load_id"] = load["load_id"]
        sandbox._save(data)
        client.post("/logout")
        return record, load

    def upload(self, client, load_id, photo_type="securement_photo", count=2):
        client.post("/driver/choose-pin", data={"pin": "4418", "pin_again": "4418"})
        files = [(io.BytesIO(PNG), f"strap{i}.png") for i in range(count)]
        resp = client.post(f"/driver/loads/{load_id}/mission-photos",
                           data={"photo_type": photo_type, "photos": files},
                           content_type="multipart/form-data", follow_redirects=True)
        client.post("/driver/logout")
        return resp

    def test_securement_photos_reach_every_mission_visibility_surface(self, client, pins, mail):
        from portal.models import publisher, sandbox
        record, load = self.mission_with_open_load(client, pins)
        resp = self.upload(client, load["load_id"])
        assert b"added to Mission Visibility" in resp.data and b"Customer Alert" in resp.data

        # Evidence on the load, and the final mission package.
        photos = services.customer_facing_photos(load["load_id"])
        assert [p["evidence_type"] for p in photos] == ["securement_photo", "securement_photo"]
        from portal.models.email_helper import _closeout_summary_lines
        assert "Load securement photos: 2 on file" in _closeout_summary_lines(
            {"load": {}, "mission_photos": photos})

        # Mission Record history.
        stored = sandbox.get(record["id"])
        event = next(e for e in stored["events"] if e["action"] == "mission_evidence_added")
        assert event["via"] == "JOE" and len(event["evidence"]) == 2

        # Customer Alert: Joe -> Publisher -> COMI -> Email Helper.
        alert = stored["customer_alerts"][-1]
        assert alert["sent"] is True and alert["flow"]["comi"]["channel"] == "customer_email"
        card = next(a for a in publisher.get_queue() if a["id"] == alert["flow"]["publisher"]["action_id"])
        assert (card["action_type"], card["status"], card["requested_for"]) == \
            ("Customer Mission Evidence Alert", "ARCHIVED", MIKE)
        assert len(mail.sent) == 2 and "Load securement photo" in mail.sent[1]["subject"]
        assert "8842193" in mail.sent[1]["body"]

        # Mission Visibility View: shown to the key holder, inline.
        client.post("/portal/login", data={"pin": "8842193"})
        view = client.get("/portal/mission").data.decode()
        assert "Load Securement" in view and photos[0]["evidence_id"] in view
        shown = client.get(f"/portal/loads/{load['load_id']}/evidence/{photos[0]['evidence_id']}")
        assert shown.status_code == 200 and "attachment" not in shown.headers.get("Content-Disposition", "")

    def test_another_customer_never_sees_the_photos(self, client, pins, mail):
        _, load = self.mission_with_open_load(client, pins)
        self.upload(client, load["load_id"], count=1)
        photo = services.customer_facing_photos(load["load_id"])[0]
        self.mission_with_open_load(client, pins, customer="Werner", load_number="5500211")
        client.post("/portal/login", data={"pin": "5500211"})
        assert photo["evidence_id"] not in client.get("/portal/mission").data.decode()
        assert client.get(f"/portal/loads/{load['load_id']}/evidence/{photo['evidence_id']}").status_code == 403

    def test_freight_condition_photos_are_customer_facing_too(self, client, pins, mail):
        _, load = self.mission_with_open_load(client, pins)
        self.upload(client, load["load_id"], photo_type="freight_condition_photo", count=1)
        assert services.customer_facing_photos(load["load_id"])[0]["label"] == "Freight condition photo"
        assert "Freight condition photo" in mail.sent[-1]["subject"]

    def test_token_links_show_the_photos(self, client, pins, mail):
        _, load = self.mission_with_open_load(client, pins)
        self.upload(client, load["load_id"], count=1)
        token = notifications.make_stakeholder_token(load["load_id"])
        view = client.get(f"/portal/loads/{load['load_id']}?token={token}").data.decode()
        assert f"token={token}" in view and "Load Securement" in view

    def test_without_a_mission_record_the_photos_stay_on_the_load_and_no_alert_is_sent(self, client, pins, mail):
        load = services.create_load(customer="XPO Logistics")
        resp = self.upload(client, load["load_id"], count=1)
        assert b"No Customer Alert went out" in resp.data and not mail.sent
        assert len(services.customer_facing_photos(load["load_id"])) == 1

    def test_no_email_on_file_records_why_no_alert_went(self, client, pins, mail):
        from portal.models import sandbox
        record, load = self.mission_with_open_load(client, pins, email="")
        self.upload(client, load["load_id"], count=1)
        alert = sandbox.get(record["id"])["customer_alerts"][-1]
        assert alert["sent"] is False and "no customer email or phone number on file" in alert["note"]

    def test_only_customer_facing_types_are_accepted_here(self, client, pins, mail):
        _, load = self.mission_with_open_load(client, pins)
        resp = self.upload(client, load["load_id"], photo_type="m6a_findings", count=1)
        assert b"Pick securement or freight condition" in resp.data
        assert services.customer_facing_photos(load["load_id"]) == []
