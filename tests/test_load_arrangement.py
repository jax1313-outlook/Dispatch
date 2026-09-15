"""Load Arrangement is gone from the product.

Asked whether Load Arrangement -- where freight sits in the truck, which was not
on his printout -- should stay, the Owner ruled on 2026-09-15:

    "good idea but delete now. for small operation not really useful."

and, of the template, "Drop it."

So the Mission Brief, the Driver Cockpit, the arrangement drawer, its form and
its save route are gone. **Stored values are not.** An older record that carries
`load_position_1`..`6` keeps them exactly as stored and still renders on every
surface; nothing shows them and nothing writes them.

This file used to prove the six-box load chart worked. It now proves it is
gone, through the real routes a person uses.
"""

from __future__ import annotations

import pytest

from portal import brief, cockpit
from portal.models import sandbox
from portal.routes import joe_portal


ARRANGED = {f"load_position_{n}": str(n) for n in range(1, 7)}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    yield


@pytest.fixture()
def app():
    from portal.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture()
def older_mission():
    """A record written while Load Arrangement existed, carrying its values."""
    entry = sandbox.create_entry(
        source_type="dispatch", source_id="ARRANGE-1",
        title="Arrangement probe", card_data={"load_id": "ARRANGE-1"},
        summary="")
    data = sandbox._load()
    data[entry["id"]].update(ARRANGED)
    sandbox._save(data)
    return entry["id"]


class TestTheCodeIsGone:
    def test_the_save_route_is_gone(self, app):
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        assert "joe_portal.portal_save_arrangement" not in endpoints
        assert not any(rule.rule.endswith("/arrangement")
                       for rule in app.url_map.iter_rules())

    def test_a_driver_sign_in_is_not_offered_it(self):
        assert "joe_portal.portal_save_arrangement" not in joe_portal.DRIVER_COCKPIT_ENDPOINTS

    def test_the_presentation_code_is_gone(self):
        for name in ("load_arrangement_for", "load_diagram_for", "LOAD_POSITIONS"):
            assert not hasattr(cockpit, name), name
        assert not hasattr(brief, "arrangement_of")

    def test_the_stylesheets_carry_no_arrangement(self):
        for sheet in ("portal/static/joe_portal.css", "portal/static/mission_brief.css"):
            css = open(sheet, encoding="utf-8").read()
            for gone in (".van", ".arrangement", ".trip-diagram", ".capacity-line"):
                assert gone not in css, (sheet, gone)


class TestAPostToTheOldRouteWritesNothing:
    def test_posting_to_the_old_address_does_not_touch_the_record(self, client,
                                                                   older_mission):
        response = client.post(f"/portal/mission/{older_mission}/arrangement",
                               data={"load_position_1": "9"})
        assert response.status_code in (404, 405)
        assert sandbox.get(older_mission)["load_position_1"] == "1"


class TestAnOlderRecordStillRenders:
    def test_the_brief_renders_without_it(self, client, older_mission):
        for url in (f"/brief/mission/{older_mission}",
                    f"/brief/mission/{older_mission}?edit=1"):
            response = client.get(url)
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert "MISSION BRIEF" in html
            for gone in ("LOAD ARRANGEMENT", "REAR DOORS", "BULKHEAD", 'class="van'):
                assert gone not in html, (url, gone)
        assert "arrangement" not in brief.card_for(sandbox.get(older_mission))

    @pytest.mark.parametrize("view", ["PICKUP", "CURRENT", "DELIVERY"])
    def test_the_cockpit_renders_without_it(self, client, older_mission, view):
        response = client.get(f"/portal/mission/{older_mission}?view={view}")
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        for gone in ("OPEN LOAD DIAGRAM", 'id="drawer-loaddiagram"', "LOAD ARRANGEMENT",
                     "SAVE ARRANGEMENT", "load_position_", "REAR DOORS", "BULKHEAD"):
            assert gone not in html, gone

    def test_saving_the_brief_leaves_the_stored_values_alone(self, client, older_mission):
        client.post(f"/brief/mission/{older_mission}/save",
                    data={"customer_poc": "D. Reyes"})
        stored = sandbox.get(older_mission)
        assert stored["customer_poc"] == "D. Reyes"
        for key, value in ARRANGED.items():
            assert stored[key] == value, key

    def test_rendering_rewrites_nothing(self, client, older_mission):
        before = sandbox.get(older_mission)
        client.get(f"/brief/mission/{older_mission}")
        client.get(f"/portal/mission/{older_mission}?view=DELIVERY")
        assert sandbox.get(older_mission) == before
