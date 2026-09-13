"""The capacity engine is reachable from the running program, and stays that way.

`dispatch/capacity.py` is 1,861 lines with 1,000 lines of tests against it, and
none of it could be reached:

  * `DynamicCapacity(` appeared nowhere outside `tests/`;
  * no table existed for a profile to be stored in;
  * the one production call into scoring is `portal/helpers.py` ->
    `score_load(data)` with no `capacity`, and `score_load`'s own docstring says
    that without one "the result is exactly what it has always been".

Dead code that is *well tested* is the hard case. It raised the gated coverage
figure while evaluating nothing, and a reviewer reading `test_dynamic_capacity.py`
would conclude the capability was in service.

The first class below is a drift test in the sense `test_repository_doctrine.py`
means it: it reads the source tree and fails if the engine goes back to having no
production caller. A resolved middle state that nothing guards is a middle state
waiting to come back.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dispatch import capacity_store, services
from dispatch.db import set_db_path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_DIRS = ("dispatch", "portal", "cin_lite", "dispatch_launcher", "scripts")


def _production_sources() -> list[Path]:
    files: list[Path] = []
    for directory in PRODUCTION_DIRS:
        root = REPO_ROOT / directory
        if root.is_dir():
            files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return files


class TestItIsNotDeadCode:
    def test_dynamic_capacity_is_instantiated_outside_the_test_suite(self):
        constructing = []
        for path in _production_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "DynamicCapacity":
                        constructing.append(str(path.relative_to(REPO_ROOT)))
        assert constructing, (
            "DynamicCapacity is constructed nowhere outside tests/. The engine is "
            "1,861 lines and its coverage comes entirely from a test file, which is "
            "how dead code reads as a working capability."
        )

    def test_a_table_exists_for_a_profile_to_live_in(self, tmp_path):
        set_db_path(tmp_path / "dispatch.db")
        try:
            from dispatch.db import get_connection

            with get_connection() as conn:
                conn.execute("SELECT COUNT(*) FROM capacity_profiles").fetchone()
        finally:
            set_db_path(None)

    def test_something_a_route_reaches_calls_the_engine(self):
        """`assess_load_capacity` must be called from a portal route, not only
        defined for one."""
        callers = []
        for path in _production_sources():
            if "portal" not in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if "assess_load_capacity" in text:
                callers.append(str(path.relative_to(REPO_ROOT)))
        assert callers, "no portal route reaches the capacity engine"


@pytest.fixture
def fleet(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        equipment = services.create_equipment(unit_number="T-101", equipment_type="dry_van")
        yield equipment
    finally:
        set_db_path(None)


class TestTheProfile:
    def test_a_truck_with_no_profile_is_unconfigured_not_assumed(self, fleet):
        load = services.create_load(customer="Acme")
        services.assign_equipment(load["load_id"], fleet["equipment_id"])

        result = services.assess_load_capacity(load["load_id"])

        assert result["status"] == "UNCONFIGURED"
        assert "no capacity profile" in result["reason"]
        # Assuming a 53-foot dry van is how freight gets accepted onto a trailer
        # that cannot carry it.
        assert result["assessment"] is None

    def test_a_load_with_no_truck_is_unconfigured(self, fleet):
        load = services.create_load(customer="Acme")
        result = services.assess_load_capacity(load["load_id"])
        assert result["status"] == "UNCONFIGURED"
        assert "No truck is assigned" in result["reason"]

    def test_a_profiled_truck_is_assessed(self, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, max_linear_feet=53,
            source="door sticker", verified_by="Mike",
        )
        load = services.create_load(customer="Acme")
        services.assign_equipment(load["load_id"], fleet["equipment_id"])

        result = services.assess_load_capacity(load["load_id"])

        assert result["status"] == "LIVE"
        assert result["assessment"]["capacity_id"]

    def test_a_profile_survives_a_round_trip(self, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, max_volume_cuft=3800,
            max_linear_feet=53, max_pallets=26, source="spec sheet", verified_by="Mike",
            has_liftgate=True,
        )
        capacity = capacity_store.load_capacity(fleet["equipment_id"])
        assert capacity.physical.max_weight_lbs == 44000
        assert capacity.physical.max_pallets == 26
        assert capacity.physical.has_liftgate is True
        assert capacity.physical.configuration_verified_by == "Mike"

    def test_utilization_is_not_persisted(self, fleet):
        """used_* describes what is on the trailer now. A saved one would come
        back as a claim about today made from last week's freight."""
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="spec", verified_by="Mike",
        )
        capacity = capacity_store.load_capacity(fleet["equipment_id"])
        capacity.physical.used_weight_lbs = 18000
        capacity_store.save_profile(capacity)

        reloaded = capacity_store.load_capacity(fleet["equipment_id"])
        assert reloaded.physical.used_weight_lbs == 0

    def test_a_specification_nobody_signed_for_is_not_verified(self, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="a guess",
        )
        capacity = capacity_store.load_capacity(fleet["equipment_id"])
        assert capacity.physical.configuration_verified_by is None
        assert capacity.physical.configuration_status != "VERIFIED"

    def test_an_unknown_truck_is_refused(self, fleet):
        with pytest.raises(ValueError, match="Equipment not found"):
            services.set_equipment_capacity_profile(
                "EQP-NOPE", max_weight_lbs=1, source="x",
            )

    def test_a_profile_written_by_an_older_build_still_loads(self, fleet):
        """A profile that cannot be read is a truck that silently stops being
        assessable."""
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="spec", verified_by="Mike",
        )
        from dispatch.db import get_connection

        with get_connection() as conn:
            conn.execute(
                "UPDATE capacity_profiles SET physical=? WHERE equipment_id=?",
                ('{"max_weight_lbs": 40000, "a_field_that_no_longer_exists": 1}',
                 fleet["equipment_id"]),
            )
        capacity = capacity_store.load_capacity(fleet["equipment_id"])
        assert capacity.physical.max_weight_lbs == 40000

    def test_unreadable_json_degrades_to_defaults_rather_than_raising(self, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="spec",
        )
        from dispatch.db import get_connection

        with get_connection() as conn:
            conn.execute(
                "UPDATE capacity_profiles SET physical=? WHERE equipment_id=?",
                ("{not json", fleet["equipment_id"]),
            )
        assert capacity_store.load_capacity(fleet["equipment_id"]) is not None


class TestCoverage:
    def test_it_names_the_trucks_that_cannot_be_assessed(self, fleet):
        services.create_equipment(unit_number="T-102")
        coverage = services.capacity_coverage()
        assert coverage["total"] == 2
        assert coverage["profiled"] == 0
        assert len(coverage["unprofiled"]) == 2
        assert coverage["complete"] is False

    def test_it_is_complete_once_every_truck_has_one(self, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="spec",
        )
        assert services.capacity_coverage()["complete"] is True


class TestTheRoutes:
    @pytest.fixture
    def client(self, fleet, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
        from portal.app import create_app

        app = create_app({"TESTING": True})
        app.config["LOGIN_DISABLED"] = True
        return app.test_client()

    def test_the_api_reports_unconfigured_honestly(self, client, fleet):
        load = services.create_load(customer="Acme")
        body = client.get(f"/api/dispatch/loads/{load['load_id']}/capacity").get_json()
        assert body["status"] == "ok"
        assert body["capacity"]["status"] == "UNCONFIGURED"
        assert body["capacity"]["reason"]

    def test_a_profile_can_be_set_and_read_back(self, client, fleet):
        response = client.put(
            f"/api/dispatch/equipment/{fleet['equipment_id']}/capacity",
            json={"max_weight_lbs": 44000, "source": "door sticker", "verified_by": "Mike"},
        )
        assert response.status_code == 200
        read = client.get(f"/api/dispatch/equipment/{fleet['equipment_id']}/capacity").get_json()
        assert read["capacity_status"] == "CONFIGURED"

    def test_a_profile_without_a_source_is_refused(self, client, fleet):
        response = client.put(
            f"/api/dispatch/equipment/{fleet['equipment_id']}/capacity",
            json={"max_weight_lbs": 44000},
        )
        assert response.status_code == 400
        assert "source is required" in response.get_json()["error"]

    def test_the_load_page_shows_the_assessment(self, client, fleet):
        services.set_equipment_capacity_profile(
            fleet["equipment_id"], max_weight_lbs=44000, source="spec", verified_by="Mike",
        )
        load = services.create_load(customer="Acme")
        services.assign_equipment(load["load_id"], fleet["equipment_id"])
        body = client.get(f"/dispatch/{load['load_id']}").get_data(as_text=True)
        assert "Does this load fit the truck?" in body
        assert "Advisory only" in body

    def test_the_page_says_unconfigured_rather_than_hiding_the_panel(self, client, fleet):
        load = services.create_load(customer="Acme")
        body = client.get(f"/dispatch/{load['load_id']}").get_data(as_text=True)
        assert "UNCONFIGURED" in body
        assert "No truck is assigned" in body
