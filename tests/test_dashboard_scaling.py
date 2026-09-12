"""The dashboards cost the same at 10 loads as at 200.

The defect this pins was not slow SQL. It was shape: `get_financial_dashboard()`
and `get_chart_data()` each walked every load and asked the database twice about
it, and every one of those asks opened a connection of its own. SQLite reads the
whole schema into memory before the first statement on a new connection, which
on this schema is ~0.65 ms, so the cost was ~1.3 ms per load and nothing about it
looked wrong in a test — every fixture holds three loads.

Measured before the fix, on a real portal client: /home took 261 ms at 50 loads,
2,005 ms at 500 and 7,786 ms at 2,000. After: 10 ms, 18 ms, 47 ms.

The per-connection schema build that made each of those asks so expensive is
a separate defect with its own fix and its own tests
(`tests/test_schema_build_once.py`); this file is only about the *number* of
asks.

These tests count **connections**, not milliseconds. A wall-clock assertion on a
shared CI runner is a flake generator, and it also tests the runner rather than
the code. The invariant that actually matters is that the count does not grow
with the number of loads, and that is exact, reproducible and machine-independent.
"""

from __future__ import annotations

import sqlite3

import pytest

from dispatch import db as dispatch_db
from dispatch import services
from dispatch.db import set_db_path


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        yield
    finally:
        set_db_path(None)


class ConnectionCounter:
    """Counts real SQLite connections opened while it is installed."""

    def __init__(self, monkeypatch):
        self.count = 0
        real = sqlite3.connect

        def counting(*args, **kwargs):
            self.count += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(dispatch_db.sqlite3, "connect", counting)

    def reset(self):
        self.count = 0


def _make_loads(n: int, *, with_money: bool = True) -> None:
    for i in range(n):
        load = services.create_load(customer=f"Customer {i % 7}", broker_shipper="TQL")
        if with_money:
            services.confirm_rate(
                load["load_id"], rate_amount=1500.0 + i, confirmed_by="Mike"
            )
            services.add_expense(load["load_id"], category="fuel", amount=210.55)


@pytest.mark.parametrize(
    "report",
    ["get_financial_dashboard", "get_chart_data"],
)
def test_the_report_opens_the_same_number_of_connections_at_any_size(
    database, monkeypatch, report
):
    fn = getattr(services, report)

    _make_loads(5)
    counter = ConnectionCounter(monkeypatch)
    fn()
    small = counter.count

    _make_loads(60)  # 13x the data
    counter.reset()
    fn()
    large = counter.count

    assert small == large, (
        f"{report} opened {small} connections for 5 loads and {large} for 65. "
        "That is the per-load query shape coming back: it is what made /home take "
        "7.8 seconds on a 2,000-load database."
    )
    assert large <= 4, f"{report} opens {large} connections; it should need one or two"


def test_the_home_page_connection_count_does_not_grow_with_the_load_table(
    database, monkeypatch, tmp_path
):
    """The whole page, not just one report on it."""
    monkeypatch.setenv("PORTAL_SECRET_KEY", "scaling-test-secret")
    monkeypatch.setenv("DISPATCH_EMAIL_SECRET", "scaling-test-email")
    from portal.app import create_app

    app = create_app({"TESTING": True})
    app.config["LOGIN_DISABLED"] = True
    client = app.test_client()

    _make_loads(5)
    client.get("/home")  # warm any first-call work that is not per-load
    counter = ConnectionCounter(monkeypatch)
    assert client.get("/home").status_code == 200
    small = counter.count

    _make_loads(60)
    counter.reset()
    assert client.get("/home").status_code == 200
    large = counter.count

    assert large <= small + 1, (
        f"/home opened {small} connections with 5 loads and {large} with 65. "
        "A page whose cost tracks the size of the loads table gets slower every "
        "month the business runs."
    )
