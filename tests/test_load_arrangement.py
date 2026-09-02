"""Where the driver put the freight.

    Grab and go, not hunt and seek.

This is the Penske load chart, and the operator made the case from a year of
running one: dock loaders work from a chart so the trailer is loaded in reverse
route order, and handing that chart to the next driver became company policy
because it tells him how many items there are and where they sit. Without it a
correctly loaded trailer looks like a disorganised mess.

The thing it records is not the route. Route order and load order are related
and are not the same:

    Route      Stop 1, Stop 2, Stop 3
    Van        Stop 3 at the bulkhead, Stop 1 at the doors

because the first stop is always loaded last.

**The driver is the load planner. Dispatch only remembers the arrangement.**
No optimiser, no weight balancing, no automatic placement, no stop sequencing.
Those are maintenance, and the man loading the truck already knows where the
freight goes.
"""

from __future__ import annotations

import pytest

from portal import cockpit
from portal.models import sandbox


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    yield


def _arranged(**positions):
    record = {"card_data": {}}
    record.update({f"load_position_{k}": v for k, v in positions.items()})
    return cockpit.load_arrangement_for(record)


class TestItRemembersWhatTheDriverDid:
    def test_six_positions_because_that_is_what_the_van_has(self):
        assert cockpit.LOAD_POSITIONS == 6
        assert len(_arranged()["positions"]) == 6

    def test_it_is_laid_out_the_way_he_faces_the_van(self):
        """Rear doors nearest, bulkhead deepest, two across. A list would make
        him translate; the shape of the van does not."""
        arrangement = _arranged()
        assert arrangement["near_label"] == "REAR DOORS"
        assert arrangement["far_label"] == "BULKHEAD"
        assert [len(row) for row in arrangement["rows"]] == [2, 2, 2]

    def test_a_three_stop_run_reads_backwards_from_the_route(self):
        """The first stop loads last, so it sits at the doors."""
        arrangement = _arranged(**{"1": "1", "2": "1", "3": "2",
                                   "4": "2", "5": "3", "6": "3"})
        rows = [[slot["value"] for slot in row] for row in arrangement["rows"]]
        assert rows == [["1", "1"], ["2", "2"], ["3", "3"]]

    def test_an_empty_position_is_empty_not_broken(self):
        """Empty space is capacity -- the answer to whether two more will fit
        on the way back."""
        arrangement = _arranged(**{"1": "1", "2": "1"})
        assert arrangement["empty_count"] == 4
        assert arrangement["occupied_count"] == 2
        assert arrangement["positions"][5]["empty"] is True

    def test_nothing_recorded_says_so(self):
        arrangement = _arranged()
        assert arrangement["recorded"] is False
        assert arrangement["summary"] == "Not recorded"


class TestItDoesNotInterpretWhatHeTyped:
    """Free-form on purpose. Stop numbers today; COLD, FROZEN, DRY tomorrow."""

    @pytest.mark.parametrize("typed", ["1", "12", "A", "COLD", "3/4", "S2",
                                       "  7  ", "x"])
    def test_values_are_stored_exactly_as_entered(self, typed):
        arrangement = _arranged(**{"1": typed})
        assert arrangement["positions"][0]["value"] == typed.strip()

    def test_a_six_stop_route_needs_no_special_handling(self):
        arrangement = _arranged(**{str(n): str(n) for n in range(1, 7)})
        assert arrangement["occupied_count"] == 6
        assert [s["value"] for s in arrangement["positions"]] == list("123456")

    def test_it_does_not_reorder_or_renumber_anything(self):
        """No route logic. A mixed load is his business, not the program's."""
        arrangement = _arranged(**{"1": "1", "2": "1", "3": "3",
                                   "4": "2", "5": "3", "6": "4"})
        assert [s["value"] for s in arrangement["positions"]] == \
            ["1", "1", "3", "2", "3", "4"]

    def test_nothing_validates_a_stop_that_does_not_exist(self):
        """Position 6 saying stop 9 on a three-stop run is not this module's
        argument to have. It records; the driver decides."""
        arrangement = _arranged(**{"6": "9"})
        assert arrangement["positions"][5]["value"] == "9"
        assert arrangement["occupied_count"] == 1


class TestTheDriverCanTypeItIn:
    @pytest.fixture()
    def client(self):
        from portal.app import create_app

        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    @pytest.fixture()
    def mission(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="ARRANGE-1",
            title="Arrangement probe", card_data={"load_id": "ARRANGE-1"},
            summary="")
        return entry["id"]

    def test_saving_puts_it_on_the_record(self, client, mission):
        client.post(f"/portal/mission/{mission}/arrangement", data={
            "load_position_1": "1", "load_position_2": "1",
            "load_position_3": "2", "load_position_4": "2",
            "load_position_5": "3", "load_position_6": "",
        })
        record = sandbox.get(mission)
        assert record["load_position_1"] == "1"
        assert record["load_position_5"] == "3"
        assert record["load_position_6"] == ""

    def test_it_returns_him_to_the_view_he_was_on(self, client, mission):
        """Saving a load chart should not move him off the screen he was
        working from."""
        response = client.post(f"/portal/mission/{mission}/arrangement",
                               data={"load_position_1": "1", "view": "DELIVERY"})
        assert response.status_code == 302
        assert "view=DELIVERY" in response.headers["Location"]

    def test_clearing_a_position_clears_it(self, client, mission):
        """Unloading stop 1 has to be recordable, or the chart goes stale and
        stale is worse than absent."""
        client.post(f"/portal/mission/{mission}/arrangement",
                    data={"load_position_1": "1"})
        client.post(f"/portal/mission/{mission}/arrangement",
                    data={"load_position_1": ""})
        assert sandbox.get(mission)["load_position_1"] == ""

    def test_an_unknown_mission_does_not_create_one(self, client):
        response = client.post("/portal/mission/NOPE/arrangement",
                               data={"load_position_1": "1"})
        assert response.status_code == 302
        assert sandbox.get("NOPE") is None

    def test_the_boxes_live_behind_open_load_diagram(self, client, mission):
        """Off the glass, one step in. What is on the truck belongs on the
        driving screen; where it physically sits is worked from at a dock."""
        html = client.get(f"/portal/mission/{mission}?view=PICKUP").get_data(as_text=True)
        assert html.count('name="load_position_') == 6

        drawer = html[html.index('id="drawer-loaddiagram"'):]
        drawer = drawer[:drawer.index("</aside>")]
        assert drawer.count('name="load_position_') == 6
        assert "REAR DOORS" in drawer
        assert "BULKHEAD" in drawer
        assert "SAVE ARRANGEMENT" in drawer

    def test_it_is_not_on_the_front_screen(self, client, mission):
        html = client.get(f"/portal/mission/{mission}?view=PICKUP").get_data(as_text=True)
        glass = html[:html.index("<aside")]
        assert "load_position_" not in glass
        assert "REAR DOORS" not in glass
