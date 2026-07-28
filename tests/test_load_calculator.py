"""Tests for the dispatch load calculator."""

from __future__ import annotations

import pytest

from cin_lite.dispatch.load_calculator import calculate_load, LoadResult


@pytest.fixture
def sample_load() -> dict:
    """A strong regional load that should score well."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Orlando, FL",
        "miles": 140,
        "rate": 560.00,
        "weight": 28000,
        "equipment_type": "dry_van",
        "pickup_date": "2026-07-29",
        "delivery_date": "2026-07-29",
    }


@pytest.fixture
def marginal_load() -> dict:
    """A longer-haul load at minimum acceptable rate."""
    return {
        "origin": "Jacksonville, FL",
        "destination": "Atlanta, GA",
        "miles": 350,
        "rate": 700.00,
        "weight": 15000,
        "equipment_type": "flatbed",
        "pickup_date": "2026-07-30",
    }


class TestCalculateLoadBasic:
    def test_returns_load_result(self, sample_load):
        result = calculate_load(sample_load)
        assert isinstance(result, LoadResult)

    def test_strong_load_is_viable(self, sample_load):
        result = calculate_load(sample_load)
        assert result.viable is True

    def test_strong_load_rate_per_mile(self, sample_load):
        result = calculate_load(sample_load)
        assert result.rate_per_mile == 4.0

    def test_strong_load_weight_utilization(self, sample_load):
        result = calculate_load(sample_load)
        assert result.weight_utilization == round(28000 / 44000, 2)

    def test_strong_load_high_score(self, sample_load):
        result = calculate_load(sample_load)
        assert result.score == 100

    def test_strong_load_flags(self, sample_load):
        result = calculate_load(sample_load)
        assert "rate_excellent" in result.flags
        assert "distance_preferred" in result.flags
        assert "good_weight_utilization" in result.flags
        assert "equipment_supported" in result.flags


class TestCalculateLoadMarginal:
    def test_marginal_load_is_viable(self, marginal_load):
        result = calculate_load(marginal_load)
        assert result.viable is True

    def test_marginal_rate_per_mile(self, marginal_load):
        result = calculate_load(marginal_load)
        assert result.rate_per_mile == 2.0

    def test_marginal_distance_acceptable(self, marginal_load):
        result = calculate_load(marginal_load)
        assert "distance_acceptable" in result.flags

    def test_marginal_lower_score(self, marginal_load, sample_load):
        marginal = calculate_load(marginal_load)
        strong = calculate_load(sample_load)
        assert marginal.score < strong.score


class TestCalculateLoadRejection:
    def test_rate_below_minimum_not_viable(self):
        load = {"miles": 200, "rate": 100.00, "weight": 10000, "equipment_type": "dry_van"}
        result = calculate_load(load)
        assert result.viable is False
        assert "rate_below_minimum" in result.flags

    def test_distance_too_far_not_viable(self):
        load = {"miles": 800, "rate": 3200.00, "weight": 30000, "equipment_type": "dry_van"}
        result = calculate_load(load)
        assert result.viable is False
        assert "distance_too_far" in result.flags

    def test_overweight_not_viable(self):
        load = {"miles": 100, "rate": 500.00, "weight": 50000, "equipment_type": "flatbed"}
        result = calculate_load(load)
        assert result.viable is False
        assert "overweight" in result.flags


class TestCalculateLoadEdgeCases:
    def test_invalid_miles_zero(self):
        result = calculate_load({"miles": 0, "rate": 500})
        assert result.viable is False
        assert "invalid_miles" in result.flags
        assert result.rate_per_mile is None

    def test_invalid_miles_negative(self):
        result = calculate_load({"miles": -10, "rate": 500})
        assert result.viable is False
        assert "invalid_miles" in result.flags

    def test_invalid_miles_missing(self):
        result = calculate_load({"rate": 500})
        assert result.viable is False
        assert "invalid_miles" in result.flags

    def test_invalid_rate_zero(self):
        result = calculate_load({"miles": 100, "rate": 0})
        assert result.viable is False
        assert "invalid_rate" in result.flags
        assert result.rate_per_mile is None

    def test_invalid_rate_missing(self):
        result = calculate_load({"miles": 100})
        assert result.viable is False
        assert "invalid_rate" in result.flags

    def test_weight_missing(self):
        load = {"miles": 100, "rate": 400.00, "equipment_type": "dry_van"}
        result = calculate_load(load)
        assert result.viable is True
        assert "weight_missing" in result.flags
        assert result.weight_utilization is None

    def test_unknown_equipment(self):
        load = {"miles": 100, "rate": 400.00, "weight": 20000, "equipment_type": "helicopter"}
        result = calculate_load(load)
        assert "equipment_unknown" in result.flags

    def test_no_equipment(self):
        load = {"miles": 100, "rate": 400.00, "weight": 20000}
        result = calculate_load(load)
        assert "equipment_supported" not in result.flags
        assert "equipment_unknown" not in result.flags

    def test_light_load(self):
        load = {"miles": 100, "rate": 400.00, "weight": 5000, "equipment_type": "sprinter"}
        result = calculate_load(load)
        assert "light_load" in result.flags


class TestLoadResultSerialization:
    def test_to_json(self, sample_load):
        result = calculate_load(sample_load)
        data = result.to_json()
        assert isinstance(data, dict)
        assert data["viable"] is True
        assert data["rate_per_mile"] == 4.0
        assert isinstance(data["flags"], list)
        assert isinstance(data["breakdown"], dict)
