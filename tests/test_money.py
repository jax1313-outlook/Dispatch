"""Money is exact, or it is not money.

Every monetary column in this schema was REAL and every monetary field a float.
`Decimal` appeared nowhere; 102 `round()` calls appeared instead, which is the
signature of a program patching drift at each display site while the accumulator
keeps it. The service layer had already recorded the symptom -- two financial
reports disagreeing by pennies on identical data -- and adopted round-then-sum
as the workaround.

These tests pin the replacement: whole cents end to end, ROUND_HALF_UP at the one
boundary where a decimal fraction genuinely exists, and totals that are exact
rather than nearly right.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from dispatch import money, services, store
from dispatch.db import get_connection, set_db_path
from dispatch.money_schema import (
    MONETARY_COLUMNS,
    init_money_schema,
    money_column_report,
    verify_money_integrity,
)


@pytest.fixture
def database(tmp_path):
    set_db_path(tmp_path / "dispatch.db")
    try:
        yield
    finally:
        set_db_path(None)


class TestConversion:
    @pytest.mark.parametrize(
        "value,cents",
        [
            (2675.15, 267515),
            ("2675.15", 267515),
            ("$2,675.15", 267515),
            ("(12.34)", -1234),  # accounting negative
            (Decimal("0.01"), 1),
            (5, 500),            # a bare int is dollars, not cents
            (0, 0),
            (None, 0),
            ("", 0),
            (-18.35, -1835),
        ],
    )
    def test_amounts_convert_exactly(self, value, cents):
        assert money.to_cents(value) == cents

    def test_a_float_converts_through_its_repr_not_its_binary_expansion(self):
        """Decimal(2675.15) is 2675.15000000000009094947...; rounding that is how
        a value typed as 2675.15 becomes 2675.16 at some later scale."""
        assert money.to_cents(2675.15) == 267515
        assert money.to_cents(0.1 + 0.2) == 30

    def test_halves_round_away_from_zero_not_to_even(self):
        """Python's round() gives 0.12 here. Invoices and tax schedules give 0.13."""
        assert round(0.125, 2) == 0.12  # the behaviour being rejected
        assert money.to_cents("0.125") == 13
        assert money.to_cents("0.135") == 14
        assert money.to_cents("-0.125") == -13

    @pytest.mark.parametrize("bad", [True, False, "abc", "12.3.4", float("nan"), float("inf"), object()])
    def test_a_non_amount_is_refused_rather_than_coerced(self, bad):
        with pytest.raises(money.MoneyError):
            money.to_cents(bad)

    def test_round_trips_to_a_display_value(self):
        assert money.to_float(267515) == 2675.15
        assert money.to_decimal(267515) == Decimal("2675.15")
        assert money.format_money(-123450) == "-$1,234.50"
        assert money.format_money(0) == "$0.00"
        assert money.format_money(5) == "$0.05"


class TestArithmetic:
    def test_accumulation_is_exact(self):
        """300 fuel surcharges of 18.35 as floats give 5505.000000000014."""
        as_floats = 0.0
        for _ in range(300):
            as_floats += 18.35
        assert as_floats != 5505.00

        assert money.total([money.to_cents(18.35)] * 300) == money.to_cents(5505.00)

    def test_a_percentage_matches_the_paper_calculation(self):
        assert money.percentage(money.to_cents(2675.15), 27) == money.to_cents(722.29)

    def test_a_rate_over_distance_rounds_once(self):
        cents = money.multiply(money.to_cents(2.47), 1140)
        assert cents == money.to_cents(2815.80)

    def test_an_allocation_never_invents_or_loses_a_penny(self):
        parts = money.allocate(money.to_cents(100), [1, 1, 1])
        assert sum(parts) == money.to_cents(100)
        assert parts == [3334, 3333, 3333]

    @pytest.mark.parametrize("amount", [1, 7, 99, 100_00, 123_45, -50_01])
    @pytest.mark.parametrize("weights", [[1], [1, 1], [1, 2, 3], [5, 5, 5, 5, 5, 5, 5]])
    def test_allocation_always_sums_to_the_whole(self, amount, weights):
        assert sum(money.allocate(amount, weights)) == amount

    def test_allocation_refuses_impossible_inputs(self):
        with pytest.raises(money.MoneyError):
            money.allocate(100, [])
        with pytest.raises(money.MoneyError):
            money.allocate(100, [0, 0])
        with pytest.raises(money.MoneyError):
            money.allocate(100, [1, -1])


class TestTheStoredRepresentation:
    def test_every_monetary_column_has_an_exact_companion(self, database):
        with get_connection() as conn:
            report = money_column_report(conn)
        assert report["complete"], [r for r in report["rows"] if not r["present"]]
        assert report["total"] == sum(len(c) for c in MONETARY_COLUMNS.values())

    def test_the_companion_recovers_the_amount_that_was_entered(self, database):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=2675.15, confirmed_by="Mike")
        with get_connection() as conn:
            row = conn.execute(
                "SELECT rate_amount, rate_amount_cents FROM rate_confirmations"
            ).fetchone()
        assert row["rate_amount_cents"] == 267515

    def test_it_tracks_an_update_with_no_write_path_of_its_own(self, database):
        """A generated column cannot be forgotten, which is the reason it is one."""
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1000.00, confirmed_by="Mike")
        services.confirm_rate(load["load_id"], rate_amount=1234.56, confirmed_by="Mike")
        with get_connection() as conn:
            assert conn.execute(
                "SELECT rate_amount_cents FROM rate_confirmations"
            ).fetchone()[0] == 123456

    def test_adding_the_columns_is_idempotent(self, database):
        with get_connection() as conn:
            assert init_money_schema(conn)["added"] == []

    def test_integrity_holds_across_a_populated_database(self, database):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1875.40, confirmed_by="Mike")
        for _ in range(50):
            services.add_expense(load["load_id"], category="fuel", amount=18.35)
        with get_connection() as conn:
            assert verify_money_integrity(conn)["ok"]

    def test_integrity_reports_a_value_that_was_never_whole_cents(self, database):
        """A third-party import, or a rate typed to four decimals. Worth saying so."""
        load = services.create_load(customer="Acme")
        services.add_expense(load["load_id"], category="fuel", amount=10.00)
        with get_connection() as conn:
            conn.execute("UPDATE expenses SET amount = 10.007")
            result = verify_money_integrity(conn)
        assert result["ok"] is False
        assert result["findings"][0]["table"] == "expenses"


class TestTheReportsThatUsedToDisagree:
    def test_the_financial_dashboard_total_is_exact(self, database):
        load = services.create_load(customer="Acme")
        for _ in range(300):
            services.add_expense(load["load_id"], category="fuel", amount=18.35)

        dashboard = services.get_financial_dashboard()
        assert dashboard["total_expenses_cents"] == money.to_cents(5505.00)
        assert dashboard["total_expenses"] == 5505.00

    def test_revenue_across_many_loads_accumulates_without_drift(self, database):
        for _ in range(200):
            load = services.create_load(customer="Acme")
            services.confirm_rate(load["load_id"], rate_amount=1425.33, confirmed_by="Mike")

        dashboard = services.get_financial_dashboard()
        assert dashboard["total_revenue_cents"] == money.to_cents(1425.33) * 200
        assert dashboard["loads_with_rate"] == 200

    def test_profit_is_the_difference_of_two_exact_numbers(self, database):
        load = services.create_load(customer="Acme")
        services.confirm_rate(load["load_id"], rate_amount=1000.10, confirmed_by="Mike")
        services.add_expense(load["load_id"], category="fuel", amount=30.03)

        dashboard = services.get_financial_dashboard()
        assert dashboard["total_profit_cents"] == money.to_cents(970.07)
        assert dashboard["total_profit"] == 970.07

    def test_a_per_mile_rate_becomes_revenue_once(self, database):
        load = services.create_load(customer="Acme")
        services.confirm_rate(
            load["load_id"], rate_amount=2.47, rate_type="per_mile",
            distance_miles=1140, confirmed_by="Mike",
        )
        rows = store.get_load_financial_rows()
        assert rows[0]["revenue_cents"] == money.to_cents(2815.80)

    def test_the_chart_and_the_dashboard_agree_to_the_cent(self, database):
        """The exact disagreement the round-then-sum convention was introduced to paper over."""
        for i in range(120):
            load = services.create_load(customer="Acme")
            services.confirm_rate(load["load_id"], rate_amount=1000.0 + i * 0.01, confirmed_by="Mike")

        dashboard = services.get_financial_dashboard()
        charts = services.get_chart_data()
        charted = sum(m["revenue_cents"] for m in charts["monthly_revenue"])
        assert charted == dashboard["total_revenue_cents"]

    def test_settlement_totals_are_exact(self, database):
        """Settlement money is derived from the rate confirmation, so build one."""
        for _ in range(3):
            load = services.create_load(customer="Acme")
            services.confirm_rate(load["load_id"], rate_amount=1000.10, confirmed_by="Mike")
            services.create_settlement(load["load_id"])

        rollup = store.get_settlement_rollup()
        assert isinstance(rollup["total_outstanding_cents"], int)
        assert rollup["total_paid_cents"] == 0
        assert money.to_float(rollup["total_outstanding_cents"]) == rollup["total_outstanding"]
