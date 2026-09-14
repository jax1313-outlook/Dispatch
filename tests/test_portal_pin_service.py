"""The three portals ask the Library PIN Service (portal/models/pin_service.py).

Mike Zachary, 2026-09-13:
  * Operations Portal -> PIN Service; Driver Portal -> PIN Service; Customer
    Portal -> PIN Service. The answer is Authenticated with a role, or Denied.
  * "Driver PINS should be no more that 4 digits/characters long and
    unassigned, created by a driver." Five drivers, no further security:
    "Keep only 4 digits" (drivers use the last four of their SSN).
  * "Customer Load Number from Load card will be the Customer PIN and auto sent
    to the email on file at the time of the load commital as a separate email
    template explaining the use of the Portal and it's entry system. This is
    part of the On-boarding Packet."
  * "Operations PIN will be Authorized by Mike Zachary through voice or dialog
    box entry with Joe."
"""

from __future__ import annotations

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
                      origin="Jacksonville, FL", destination="Atlanta, GA"):
    from portal.models import sandbox
    entry = sandbox.create_entry(source_type="dispatch", source_id=load_number, title="Portal probe",
                                 card_data={"origin": origin, "destination": destination}, summary="")
    data = sandbox._load()
    data[entry["id"]].update({"customer": customer, "load_number": load_number, "customer_email": email})
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

    def test_no_email_on_file_makes_the_pin_and_says_nothing_was_sent(self, client, pins, mail):
        sign_in_operations(client, pins)
        record = committed_mission(client, email="")
        assert (record["portal_access"]["pin"], record["portal_access"]["sent"]) == ("CREATED", False)
        assert "no customer email on file" in record["portal_access"]["note"] and not mail.sent

    def test_a_failed_send_is_recorded_as_not_sent(self, client, pins, monkeypatch):
        from portal.routes import joe_portal
        monkeypatch.setattr(joe_portal, "_mail_connector", lambda: FakeMail(ok=False))
        sign_in_operations(client, pins)
        record = committed_mission(client)
        assert record["portal_access"]["sent"] is False
        assert "Outlook is not open" in record["portal_access"]["note"]

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
