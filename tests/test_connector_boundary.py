"""The connector boundary, proven structurally rather than asserted.

Section 6.2: "A connector may never call Spine transition code, never write to
``loads.status``, and never write to any Current Reality table. **Enforce this
structurally** (module boundaries, import rules, and tests) -- not by convention
alone."

This file is the "and tests" half of that sentence, and it works in both
directions. It runs the import-graph scan over the real package, and it also
feeds the scanner code that *does* violate the rule, so a scan that had quietly
stopped detecting anything would fail here rather than pass everything.
"""

from __future__ import annotations

import sqlite3

import pytest

from dispatch import services
from dispatch.connectors import audit, registry
from dispatch.connectors.boundary import (
    ALLOWED_TABLES,
    BoundaryViolation,
    CURRENT_REALITY_TABLES,
    DATABASE_ALLOWED_FILES,
    FORBIDDEN_MODULES,
    assert_module_clean,
    assert_package_clean,
    execute,
    module_imports,
    package_files,
    sealed,
    sealed_connector,
    sql_tables,
    transitive_first_party_imports,
    verify_file,
    verify_package,
)
from dispatch.connectors.contract import AuditRecord, ConnectorRequest, ConnectorStatus
from dispatch.connectors.mock import MockRouteRiskConnector
from dispatch.connectors.route_risk_connector import (
    AdvisoryRouteRiskEvaluator,
    normalize_conditions,
)
from dispatch.db import set_db_path

_PACKAGE_DIR = package_files()[0].parent


@pytest.fixture()
def connector_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))
    monkeypatch.setenv("PORTAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    set_db_path(tmp_path / "boundary.db")
    yield tmp_path
    set_db_path(None)


@pytest.fixture()
def probe_module(tmp_path):
    """Write a throwaway module and hand back its path, for scanning."""

    def _write(source: str, name: str = "probe.py"):
        path = tmp_path / name
        path.write_text(source, encoding="utf-8")
        return path

    return _write


@pytest.fixture()
def probe_inside_package():
    """A throwaway module written *inside* the package, removed afterwards.

    Needed for the relative-import case: ``from .. import store`` only resolves
    to ``dispatch.store`` for a file that actually sits in the package, which is
    exactly the smuggling route the scan has to close.
    """
    path = _PACKAGE_DIR / "_boundary_probe_tmp.py"

    def _write(source: str):
        path.write_text(source, encoding="utf-8")
        return path

    try:
        yield _write
    finally:
        if path.exists():
            path.unlink()


# ── the import graph ──────────────────────────────────────────────────


class TestTheImportGraphHolds:
    def test_the_whole_package_is_clean(self):
        assert verify_package() == {}

    def test_assert_package_clean_passes_silently(self):
        assert_package_clean() is None

    @pytest.mark.parametrize("connector_id", registry.CONNECTOR_IDS)
    def test_no_registered_connector_imports_spine_services_or_store(self, connector_id):
        module = type(registry.get(connector_id)).__module__
        path = _PACKAGE_DIR / f"{module.rsplit('.', 1)[-1]}.py"
        imported = module_imports(path) | transitive_first_party_imports(path)
        for forbidden in FORBIDDEN_MODULES:
            assert not any(
                name == forbidden or name.startswith(forbidden + ".") for name in imported
            ), f"{module} reaches {forbidden}"

    def test_the_mock_is_held_to_the_same_rule(self):
        assert verify_file(_PACKAGE_DIR / "mock.py") == []

    def test_only_the_audit_and_boundary_files_know_a_database_exists(self):
        for path in package_files():
            if path.name in DATABASE_ALLOWED_FILES:
                continue
            imported = module_imports(path)
            assert "sqlite3" not in imported
            assert "dispatch.db" not in imported

    def test_only_the_audit_file_contains_sql_and_only_for_its_own_table(self):
        for path in package_files():
            tables = sql_tables(path)
            if path.name == "audit.py":
                assert tables == set(ALLOWED_TABLES)
            else:
                assert tables == set()

    def test_no_current_reality_table_is_named_anywhere_in_the_package(self):
        for path in package_files():
            assert not (sql_tables(path) & CURRENT_REALITY_TABLES)

    def test_the_email_connector_reaches_the_existing_transport_and_nothing_worse(self):
        reachable = transitive_first_party_imports(
            _PACKAGE_DIR / "email_transport_connector.py"
        )
        assert "cin_lite.email_delivery" in reachable
        assert not any(name.startswith("dispatch.services") for name in reachable)


class TestTheScannerActuallyDetects:
    """The other direction: feed it violations and check it says so."""

    def test_a_direct_forbidden_import_is_caught(self, probe_module):
        path = probe_module("from dispatch.services import create_load\n")
        violations = verify_file(path)
        assert any("dispatch.services" in v for v in violations)

    def test_a_spine_import_is_caught(self, probe_module):
        path = probe_module("import dispatch.spine.state\n")
        assert any("Spine" in v for v in verify_file(path))

    def test_a_relative_import_that_climbs_out_of_the_package_is_caught(
        self, probe_inside_package
    ):
        path = probe_inside_package("from .. import store\n")
        assert any("dispatch.store" in v for v in verify_file(path))

    def test_an_import_of_the_database_layer_is_caught(self, probe_module):
        path = probe_module("import sqlite3\n")
        assert any("may know a database exists" in v for v in verify_file(path))

    def test_sql_against_a_current_reality_table_is_caught(self, probe_module):
        path = probe_module('QUERY = "UPDATE loads SET status = ? WHERE load_id = ?"\n')
        assert any("a Current Reality table" in v for v in verify_file(path))

    def test_a_select_against_current_reality_is_caught(self, probe_module):
        path = probe_module('QUERY = "SELECT driver FROM loads WHERE load_id = ?"\n')
        assert any("'loads'" in v for v in verify_file(path))

    def test_sql_against_any_other_table_is_caught_too(self, probe_module):
        path = probe_module('QUERY = "INSERT INTO scratch (a) VALUES (1)"\n')
        assert any("'scratch'" in v for v in verify_file(path))

    def test_a_transitive_forbidden_import_is_caught(self, probe_module):
        path = probe_module("import dispatch.opportunities\n")
        assert any("transitively" in v for v in verify_file(path))

    def test_ordinary_prose_mentioning_sql_words_is_not_read_as_sql(self, probe_module):
        path = probe_module(
            '"""Select a provider from the list and update loads by hand."""\n'
        )
        assert verify_file(path) == []

    def test_assert_package_clean_reports_every_offending_file(self, probe_inside_package):
        probe_inside_package("from dispatch.store import get_load\n")
        with pytest.raises(BoundaryViolation, match="boundary is broken"):
            assert_package_clean()


class TestOnlyPackageConnectorsMayBeExecuted:
    def test_a_connector_defined_outside_the_package_is_refused(self, connector_db):
        class SmugglerConnector(MockRouteRiskConnector):
            pass

        with pytest.raises(BoundaryViolation, match="not part of dispatch.connectors"):
            execute(SmugglerConnector(), ConnectorRequest("fetch_conditions"))

    def test_a_package_connector_passes_the_check(self):
        assert assert_module_clean("dispatch.connectors.mock") is None

    def test_the_check_is_cached_after_the_first_call(self):
        assert_module_clean("dispatch.connectors.mock")
        assert assert_module_clean("dispatch.connectors.mock") is None


# ── the runtime seal ──────────────────────────────────────────────────


class TestTheRuntimeSeal:
    def test_no_database_connection_can_be_opened_inside_the_seal(self):
        with sealed("mock.route_risk"):
            with pytest.raises(BoundaryViolation, match="attempted to open a database"):
                sqlite3.connect(":memory:")

    def test_the_seal_is_released_afterwards(self):
        with sealed("mock.route_risk"):
            pass
        connection = sqlite3.connect(":memory:")
        connection.close()

    def test_the_seal_is_released_even_when_the_block_raises(self):
        with pytest.raises(RuntimeError):
            with sealed("mock.route_risk"):
                raise RuntimeError("boom")
        connection = sqlite3.connect(":memory:")
        connection.close()

    def test_the_seal_names_the_connector_holding_it(self):
        assert sealed_connector() == ""
        with sealed("mock.route_risk"):
            assert sealed_connector() == "mock.route_risk"
        assert sealed_connector() == ""

    def test_current_reality_is_unreachable_from_inside_the_seal(self, connector_db):
        with sealed("mock.route_risk"):
            with pytest.raises(BoundaryViolation):
                services.create_load(customer="Level 1 Transport")

    def test_dispatch_keeps_working_after_the_seal_lifts(self, connector_db):
        with sealed("mock.route_risk"):
            pass
        load = services.create_load(customer="Level 1 Transport")
        assert services.get_load(load["load_id"])["customer"] == "Level 1 Transport"

    def test_a_connector_that_reaches_for_a_database_is_stopped(self, connector_db):
        connector = MockRouteRiskConnector(failure_mode="boundary_probe")
        with pytest.raises(BoundaryViolation, match="transport and normalize"):
            execute(connector, ConnectorRequest("fetch_conditions"))

    def test_the_same_probe_succeeds_when_nothing_seals_it(self, connector_db):
        """Proves the refusal comes from the seal, not from the probe failing."""
        connector = MockRouteRiskConnector(failure_mode="boundary_probe")
        assert connector.fetch(ConnectorRequest("fetch_conditions")).ok is True

    def test_a_violation_is_audited_before_it_is_raised(self, connector_db):
        connector = MockRouteRiskConnector(failure_mode="boundary_probe")
        with pytest.raises(BoundaryViolation):
            execute(connector, ConnectorRequest("fetch_conditions"))
        rows = audit.list_audit("mock.route_risk")
        assert rows and rows[0]["outcome"] == "refused"
        assert "attempted to open a database connection" in rows[0]["reason"]

    def test_a_violation_is_never_downgraded_into_a_result(self, connector_db):
        """A boundary breach is a programming error and must not look operational."""
        recorded: list[AuditRecord] = []
        connector = MockRouteRiskConnector(failure_mode="boundary_probe")
        with pytest.raises(BoundaryViolation):
            execute(connector, ConnectorRequest("fetch_conditions"), audit_sink=recorded.append)
        assert len(recorded) == 1
        assert recorded[0].status is ConnectorStatus.UNAVAILABLE


class TestConnectorsDoNotTouchCurrentReality:
    def test_a_full_connector_call_leaves_the_load_untouched(self, connector_db):
        load = services.create_load(customer="Level 1 Transport", notes="original")
        before = services.get_load(load["load_id"])

        result = execute(MockRouteRiskConnector(), ConnectorRequest(
            "fetch_conditions", {"load_id": load["load_id"]}
        ))
        assert result.ok

        after = services.get_load(load["load_id"])
        assert after == before

    def test_every_registered_connector_can_be_called_without_writing_anything(
        self, connector_db
    ):
        load = services.create_load(customer="Level 1 Transport")
        before = services.get_load(load["load_id"])
        for connector in registry.all_connectors():
            execute(connector, ConnectorRequest("probe", {"load_id": load["load_id"]}))
        assert services.get_load(load["load_id"]) == before


# ── Section 6.5: the evaluation layer cannot write either ─────────────


class TestTheEvaluationLayerCannotChangeCurrentReality:
    def test_evaluation_completes_with_every_database_connection_refused(self, connector_db):
        payload = execute(
            MockRouteRiskConnector(), ConnectorRequest("fetch_conditions", {"load_id": "L-1"})
        ).payload

        with sealed("route_risk.evaluation"):
            assessment = AdvisoryRouteRiskEvaluator().evaluate(payload)

        assert assessment.consequence_level == 3
        assert assessment.advisory is True

    def test_an_evaluator_that_tried_to_write_would_be_stopped(self, connector_db):
        load = services.create_load(customer="Level 1 Transport")
        with sealed("route_risk.evaluation"):
            with pytest.raises(BoundaryViolation):
                services.add_milestone(load["load_id"], event_type="dispatched")
        assert services.get_load(load["load_id"])["status"] == "created"

    def test_evaluation_changes_no_load_record(self, connector_db):
        load = services.create_load(customer="Level 1 Transport")
        before_load = services.get_load(load["load_id"])
        before_visibility = services.get_visibility(load["load_id"])
        payload = execute(
            MockRouteRiskConnector(),
            ConnectorRequest("fetch_conditions", {"load_id": load["load_id"]}),
        ).payload
        assessment = AdvisoryRouteRiskEvaluator().evaluate(payload)

        # The assessment says a Mission Visibility update is required. It does
        # not perform one, and nothing else does on its behalf.
        assert assessment.mission_visibility_update_required is True
        assert services.get_load(load["load_id"]) == before_load
        assert services.get_visibility(load["load_id"]) == before_visibility

    def test_the_evaluation_module_cannot_reach_spine_services_or_store(self):
        assert verify_file(_PACKAGE_DIR / "route_risk_connector.py") == []

    def test_an_evaluator_cannot_be_handed_a_payload_without_a_status(self):
        with pytest.raises(TypeError):
            normalize_conditions()  # type: ignore[call-arg]
