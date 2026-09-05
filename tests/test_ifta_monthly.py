"""Tests for IFTA monthly form, tax rates, CSV export, and related API/template."""

from __future__ import annotations

import csv
import io

import pytest

from dispatch.db import set_db_path
from dispatch.models import IFTA_JURISDICTIONS, IFTA_TAX_RATES
from dispatch import services, store


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


def _seed_data(month="01"):
    """Seed trip legs and fuel purchases for a given month in 2025."""
    services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date=f"2025-{month}-15", vehicle_id="V1")
    services.add_ifta_trip_leg(jurisdiction="IN", miles=300, date=f"2025-{month}-20", vehicle_id="V1")
    services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=80, amount=280, date=f"2025-{month}-16", vehicle_id="V1")
    services.add_ifta_fuel_purchase(jurisdiction="IN", gallons=40, amount=160, date=f"2025-{month}-21", vehicle_id="V1")


# ── Tax rate model tests ──────────────────────────────────────────


class TestIFTATaxRates:
    def test_all_jurisdictions_have_rates(self):
        for j in IFTA_JURISDICTIONS:
            assert j in IFTA_TAX_RATES, f"Missing tax rate for {j}"
            assert "rate" in IFTA_TAX_RATES[j]
            assert "surcharge" in IFTA_TAX_RATES[j]

    def test_rates_are_positive(self):
        for j, r in IFTA_TAX_RATES.items():
            assert r["rate"] >= 0, f"{j} has negative rate"
            assert r["surcharge"] >= 0, f"{j} has negative surcharge"

    def test_indiana_has_surcharge(self):
        assert IFTA_TAX_RATES["IN"]["surcharge"] == 0.11

    def test_kentucky_has_surcharge(self):
        assert IFTA_TAX_RATES["KY"]["surcharge"] == 0.02

    def test_nevada_has_surcharge(self):
        assert IFTA_TAX_RATES["NV"]["surcharge"] == 0.0055

    def test_new_mexico_has_surcharge(self):
        assert IFTA_TAX_RATES["NM"]["surcharge"] == 0.01

    def test_texas_no_surcharge(self):
        assert IFTA_TAX_RATES["TX"]["surcharge"] == 0.0
        assert IFTA_TAX_RATES["TX"]["rate"] == 0.20

    def test_rate_count_matches_jurisdictions(self):
        assert len(IFTA_TAX_RATES) == len(IFTA_JURISDICTIONS)

    def test_canadian_provinces_present(self):
        for prov in ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]:
            assert prov in IFTA_TAX_RATES

    def test_dc_present(self):
        assert "DC" in IFTA_TAX_RATES


# ── Monthly report service tests ──────────────────────────────────


class TestMonthlyReport:
    def test_empty_report(self):
        report = services.get_ifta_monthly_report(2025, 1)
        assert report["year"] == 2025
        assert report["month"] == 1
        assert report["month_label"] == "January 2025"
        assert report["total_miles"] == 0
        assert report["total_gallons"] == 0
        assert report["fleet_mpg"] == 0
        assert report["jurisdictions"] == []
        assert report["total_tax_owed"] == 0
        assert report["total_surcharge"] == 0
        assert report["total_due"] == 0

    def test_invalid_month_zero(self):
        with pytest.raises(ValueError, match="month"):
            services.get_ifta_monthly_report(2025, 0)

    def test_invalid_month_thirteen(self):
        with pytest.raises(ValueError, match="month"):
            services.get_ifta_monthly_report(2025, 13)

    def test_invalid_month_negative(self):
        with pytest.raises(ValueError, match="month"):
            services.get_ifta_monthly_report(2025, -1)

    def test_date_range_january(self):
        report = services.get_ifta_monthly_report(2025, 1)
        assert report["date_from"] == "2025-01-01"
        assert report["date_to"] == "2025-01-31"

    def test_date_range_february(self):
        report = services.get_ifta_monthly_report(2025, 2)
        assert report["date_from"] == "2025-02-01"
        assert report["date_to"] == "2025-02-28"

    def test_date_range_february_leap(self):
        report = services.get_ifta_monthly_report(2024, 2)
        assert report["date_to"] == "2024-02-29"

    def test_date_range_december(self):
        report = services.get_ifta_monthly_report(2025, 12)
        assert report["date_from"] == "2025-12-01"
        assert report["date_to"] == "2025-12-31"
        assert report["month_label"] == "December 2025"

    def test_month_labels(self):
        labels = [
            (1, "January"), (2, "February"), (3, "March"), (4, "April"),
            (5, "May"), (6, "June"), (7, "July"), (8, "August"),
            (9, "September"), (10, "October"), (11, "November"), (12, "December"),
        ]
        for m, name in labels:
            report = services.get_ifta_monthly_report(2025, m)
            assert report["month_label"] == f"{name} 2025"

    def test_report_with_data(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        assert report["total_miles"] == 800
        assert report["total_gallons"] == 120
        assert len(report["jurisdictions"]) == 2

    def test_date_filtering(self):
        _seed_data("01")
        services.add_ifta_trip_leg(jurisdiction="TX", miles=200, date="2025-02-10")
        jan = services.get_ifta_monthly_report(2025, 1)
        feb = services.get_ifta_monthly_report(2025, 2)
        assert jan["total_miles"] == 800
        assert feb["total_miles"] == 200

    def test_vehicle_filter(self):
        _seed_data("01")
        services.add_ifta_trip_leg(jurisdiction="TX", miles=100, date="2025-01-15", vehicle_id="V2")
        report = services.get_ifta_monthly_report(2025, 1, vehicle_id="V1")
        assert report["total_miles"] == 800
        assert report["vehicle_id"] == "V1"

    def test_report_has_trip_and_fuel_counts(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        assert report["trip_leg_count"] == 2
        assert report["fuel_purchase_count"] == 2


# ── Tax computation tests ─────────────────────────────────────────


class TestTaxComputation:
    def test_tax_owed_calculation(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=1000, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=100, amount=350, date="2025-01-20")
        report = services.get_ifta_monthly_report(2025, 1)
        tx = report["jurisdictions"][0]
        net = tx["net_taxable_gallons"]
        assert tx["tax_rate"] == 0.20
        assert tx["tax_owed"] == round(net * 0.20, 2)

    def test_surcharge_calculation_indiana(self):
        services.add_ifta_trip_leg(jurisdiction="IN", miles=500, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="IN", gallons=50, amount=200, date="2025-01-20")
        report = services.get_ifta_monthly_report(2025, 1)
        ind = report["jurisdictions"][0]
        net = ind["net_taxable_gallons"]
        assert ind["surcharge_rate"] == 0.11
        assert ind["surcharge"] == round(net * 0.11, 2)
        assert ind["total_due"] == round(ind["tax_owed"] + ind["surcharge"], 2)

    def test_no_surcharge_when_rate_zero(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=50, amount=175, date="2025-01-20")
        report = services.get_ifta_monthly_report(2025, 1)
        tx = report["jurisdictions"][0]
        assert tx["surcharge_rate"] == 0.0
        assert tx["surcharge"] == 0.0

    def test_total_due_sums_all_jurisdictions(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        manual_tax = sum(j["tax_owed"] for j in report["jurisdictions"])
        manual_sur = sum(j["surcharge"] for j in report["jurisdictions"])
        assert report["total_tax_owed"] == round(manual_tax, 2)
        assert report["total_surcharge"] == round(manual_sur, 2)
        assert report["total_due"] == round(manual_tax + manual_sur, 2)

    def test_negative_net_taxable_gives_credit(self):
        services.add_ifta_trip_leg(jurisdiction="TX", miles=100, date="2025-01-15")
        services.add_ifta_trip_leg(jurisdiction="OK", miles=100, date="2025-01-16")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=500, amount=1750, date="2025-01-20")
        report = services.get_ifta_monthly_report(2025, 1)
        ok = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "OK")
        assert ok["fuel_gallons"] == 0
        assert ok["net_taxable_gallons"] > 0
        tx = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "TX")
        assert tx["net_taxable_gallons"] < 0
        assert tx["tax_owed"] < 0

    def test_quarterly_report_also_has_tax_fields(self):
        _seed_data("01")
        report = services.get_ifta_quarterly_report(2025, 1)
        assert "total_tax_owed" in report
        assert "total_surcharge" in report
        assert "total_due" in report
        for j in report["jurisdictions"]:
            assert "tax_rate" in j
            assert "surcharge_rate" in j
            assert "tax_owed" in j
            assert "total_due" in j

    def test_missing_rate_jurisdiction_refuses_to_aggregate(self, monkeypatch):
        """A jurisdiction with no rate on file must refuse the report, not
        silently compute a $0.00 fallback -- a missing-data zero is forbidden,
        even though the jurisdiction itself is a valid IFTA_JURISDICTIONS entry."""
        from dispatch.models import IFTA_TAX_RATES
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        monkeypatch.delitem(IFTA_TAX_RATES, "TX")
        with pytest.raises(ValueError, match="TX"):
            services.get_ifta_monthly_report(2025, 1)

    def test_genuine_zero_rate_still_computes_a_real_zero(self, monkeypatch):
        """A jurisdiction whose real, stored rate is exactly 0.0 must continue
        to compute normally -- a calculated zero is valid and must never be
        confused with a missing-data refusal."""
        from dispatch.models import IFTA_TAX_RATES
        monkeypatch.setitem(IFTA_TAX_RATES, "TX", {"rate": 0.0, "surcharge": 0.0})
        services.add_ifta_trip_leg(jurisdiction="TX", miles=500, date="2025-01-15")
        services.add_ifta_fuel_purchase(jurisdiction="TX", gallons=80, amount=280, date="2025-01-16")
        report = services.get_ifta_monthly_report(2025, 1)
        tx = next(j for j in report["jurisdictions"] if j["jurisdiction"] == "TX")
        assert tx["tax_rate"] == 0.0
        assert tx["tax_owed"] == 0.0


# ── CSV export tests ──────────────────────────────────────────────


class TestExportCSV:
    def test_csv_header_rows(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0][0] == "IFTA Report"
        assert rows[0][1] == "January 2025"
        assert rows[1][0] == "Date Range"
        assert rows[1][1] == "2025-01-01"

    def test_csv_vehicle_row(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1, vehicle_id="V1")
        csv_text = services.export_ifta_csv(report)
        assert "V1" in csv_text

    def test_csv_no_vehicle_row_when_empty(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        row_starts = [r[0] for r in rows if r]
        assert "Vehicle" not in row_starts

    def test_csv_column_headers(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        assert "Jurisdiction" in csv_text
        assert "Tax Rate" in csv_text
        assert "Surcharge Rate" in csv_text
        assert "Tax Owed" in csv_text
        assert "Total Due" in csv_text

    def test_csv_data_rows(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Jurisdiction")
        data_rows = [r for r in rows[header_idx + 1:] if r and r[0] and r[0] != "TOTALS" and r[0] != ""]
        assert len(data_rows) == 2
        juris = {r[0] for r in data_rows}
        assert juris == {"IN", "TX"}

    def test_csv_totals_row(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        totals = [r for r in rows if r and r[0] == "TOTALS"]
        assert len(totals) == 1
        assert totals[0][1] == str(report["total_miles"])

    def test_csv_quarterly_label(self):
        _seed_data("01")
        report = services.get_ifta_quarterly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        assert "Q1 2025" in csv_text

    def test_csv_fleet_mpg_row(self):
        _seed_data("01")
        report = services.get_ifta_monthly_report(2025, 1)
        csv_text = services.export_ifta_csv(report)
        assert "Fleet MPG" in csv_text

    def test_csv_empty_report(self):
        report = services.get_ifta_monthly_report(2025, 6)
        csv_text = services.export_ifta_csv(report)
        assert "IFTA Report" in csv_text
        assert "June 2025" in csv_text


# ── Monthly report API tests ─────────────────────────────────────


class TestMonthlyReportAPI:
    def test_monthly_report_endpoint(self, client):
        _seed_data("03")
        resp = client.get("/api/dispatch/ifta/monthly-report?year=2025&month=3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["month"] == 3
        assert data["month_label"] == "March 2025"
        assert data["total_miles"] == 800

    def test_monthly_report_missing_params(self, client):
        resp = client.get("/api/dispatch/ifta/monthly-report")
        assert resp.status_code == 400

    def test_monthly_report_missing_month(self, client):
        resp = client.get("/api/dispatch/ifta/monthly-report?year=2025")
        assert resp.status_code == 400

    def test_monthly_report_invalid_month(self, client):
        resp = client.get("/api/dispatch/ifta/monthly-report?year=2025&month=13")
        assert resp.status_code == 400

    def test_monthly_report_non_integer(self, client):
        resp = client.get("/api/dispatch/ifta/monthly-report?year=abc&month=1")
        assert resp.status_code == 400

    def test_monthly_report_with_vehicle(self, client):
        _seed_data("01")
        resp = client.get("/api/dispatch/ifta/monthly-report?year=2025&month=1&vehicle_id=V1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["vehicle_id"] == "V1"

    def test_monthly_report_has_tax_fields(self, client):
        _seed_data("01")
        resp = client.get("/api/dispatch/ifta/monthly-report?year=2025&month=1")
        data = resp.get_json()
        assert "total_tax_owed" in data
        assert "total_surcharge" in data
        assert "total_due" in data


# ── CSV export API tests ──────────────────────────────────────────


class TestCSVExportAPI:
    def test_csv_export_quarterly(self, client):
        _seed_data("01")
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=quarter&quarter=1")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers["Content-Disposition"]
        assert "ifta_2025_Q1.csv" in resp.headers["Content-Disposition"]

    def test_csv_export_monthly(self, client):
        _seed_data("03")
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=month&month=3")
        assert resp.status_code == 200
        assert "ifta_2025_03.csv" in resp.headers["Content-Disposition"]
        body = resp.data.decode()
        assert "March 2025" in body

    def test_csv_export_missing_year(self, client):
        resp = client.get("/api/dispatch/ifta/export-csv?type=quarter&quarter=1")
        assert resp.status_code == 400

    def test_csv_export_missing_quarter(self, client):
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=quarter")
        assert resp.status_code == 400

    def test_csv_export_missing_month(self, client):
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=month")
        assert resp.status_code == 400

    def test_csv_export_invalid_quarter(self, client):
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=quarter&quarter=5")
        assert resp.status_code == 400

    def test_csv_export_with_vehicle(self, client):
        _seed_data("01")
        resp = client.get("/api/dispatch/ifta/export-csv?year=2025&type=month&month=1&vehicle_id=V1")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "V1" in body


# ── Template tests ────────────────────────────────────────────────


class TestIFTAMonthlyTemplate:
    def test_monthly_view_toggle_present(self, client):
        resp = client.get("/ifta")
        html = resp.data.decode()
        assert "Quarterly" in html
        assert "Monthly" in html

    def test_monthly_view_loads(self, client):
        resp = client.get("/ifta?view=month&year=2025&month=6")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "June 2025" in html

    def test_quarterly_view_still_works(self, client):
        resp = client.get("/ifta?view=quarter&year=2025&quarter=2")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Q2 2025" in html

    def test_tax_columns_present(self, client):
        _seed_data("01")
        resp = client.get("/ifta?year=2025&quarter=1")
        html = resp.data.decode()
        assert "Tax Rate" in html
        assert "Tax Owed" in html
        assert "Surcharge" in html
        assert "Total Due" in html

    def test_tax_totals_bar(self, client):
        _seed_data("01")
        resp = client.get("/ifta?year=2025&quarter=1")
        html = resp.data.decode()
        assert "Tax Owed:" in html
        assert "Surcharges:" in html
        assert "Total Due:" in html

    def test_csv_export_link_present(self, client):
        resp = client.get("/ifta?year=2025&quarter=1")
        html = resp.data.decode()
        assert "Export CSV" in html
        assert "export-csv" in html

    def test_monthly_report_with_data(self, client):
        _seed_data("01")
        resp = client.get("/ifta?view=month&year=2025&month=1")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "January 2025" in html
        assert "TX" in html
        assert "IN" in html

    def test_monthly_view_shows_month_selector(self, client):
        resp = client.get("/ifta?view=month&year=2025&month=6")
        html = resp.data.decode()
        assert "Jan" in html or "January" in html

    def test_default_view_is_quarterly(self, client):
        resp = client.get("/ifta")
        html = resp.data.decode()
        assert "Quarterly" in html

    def test_total_due_summary_card(self, client):
        _seed_data("01")
        resp = client.get("/ifta?year=2025&quarter=1")
        html = resp.data.decode()
        assert "Total Due" in html
