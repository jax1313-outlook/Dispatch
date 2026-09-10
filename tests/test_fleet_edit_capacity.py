"""A unit's type and its capacity numbers are a Fleet edit, not a code change.

The capacity builder's own comment says so: swapping the trailer should be an
edit on this screen and every consumer sees the new envelope on the next call.
The inline edit form was quietly breaking that. It carried VIN, plate, make,
model, year and notes, and nothing else -- so a unit filed under the wrong type
could only be fixed by deleting it and starting again, and the payload and
dimensions that feed the envelope could not be corrected at all.
"""

from __future__ import annotations

import pytest

from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture(autouse=True)
def _db(tmp_path):
    set_db_path(tmp_path / "test.db")
    yield
    set_db_path(None)


@pytest.fixture
def client():
    from portal.app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestCorrectingAUnit:
    def test_the_type_can_be_changed_without_deleting_the_unit(self, client):
        """Mike filed the trailer as "other" because the list he was looking at
        had no enclosed trailer on it."""
        eqp = services.create_equipment(unit_number="1", equipment_type="other")

        resp = client.patch(f"/api/dispatch/equipment/{eqp['equipment_id']}",
                            json={"equipment_type": "enclosed_trailer"})
        assert resp.status_code == 200
        assert resp.get_json()["equipment"]["equipment_type"] == "enclosed_trailer"

    def test_the_capacity_numbers_can_be_corrected(self, client):
        eqp = services.create_equipment(unit_number="13", equipment_type="cargo_van")

        resp = client.patch(f"/api/dispatch/equipment/{eqp['equipment_id']}", json={
            "gvwr_lb": 9950, "payload_lb": 4604,
            "cargo_length_in": 146, "cargo_width_in": 54,
            "cargo_height_in": 79, "door_width_in": 48,
        })
        assert resp.status_code == 200
        updated = resp.get_json()["equipment"]
        assert updated["payload_lb"] == 4604
        assert updated["cargo_length_in"] == 146

    def test_a_type_that_is_not_on_the_list_is_refused(self, client):
        eqp = services.create_equipment(unit_number="9")
        resp = client.patch(f"/api/dispatch/equipment/{eqp['equipment_id']}",
                            json={"equipment_type": "spaceship"})
        assert resp.status_code == 400


class TestTheFormOffersThem:
    def test_the_edit_form_carries_the_type_and_the_capacity_fields(self, client):
        services.create_equipment(unit_number="13", equipment_type="cargo_van")
        html = client.get("/settings").data.decode()

        assert 'name="equipment_type"' in html
        for field in ("gvwr_lb", "payload_lb", "cargo_length_in",
                      "cargo_width_in", "cargo_height_in", "door_width_in"):
            assert f'name="{field}"' in html, f"missing {field}"


class TestTheEnvelopeFollowsTheEdit:
    def test_correcting_the_payload_changes_the_capacity_envelope(self, client):
        """The point of all of it. Nothing is hard coded, so a Fleet edit moves
        the number every consumer reads."""
        from dispatch.capacity import physical_capacity_from_equipment

        eqp = services.create_equipment(unit_number="13", equipment_type="cargo_van")
        before = physical_capacity_from_equipment([services.get_equipment(eqp["equipment_id"])])

        client.patch(f"/api/dispatch/equipment/{eqp['equipment_id']}",
                     json={"payload_lb": 4604})
        after = physical_capacity_from_equipment([services.get_equipment(eqp["equipment_id"])])

        assert after.max_weight_lbs == 4604
        assert after.max_weight_lbs != before.max_weight_lbs
