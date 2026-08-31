"""The Policy Profile: the operator's business judgement, validated whole.

`dispatch/scoring.py` held nine business values as module constants — home base,
fuel cost, rate bands, weight limit, radius, HOS assumptions. Changing any of
them meant editing Python. These tests pin the move, the validation, and the one
rule that makes the move safe: the shipped defaults reproduce the old constants
exactly, so nothing scored differently on the day it landed.
"""

from __future__ import annotations

import json

import pytest

from dispatch.policy import (
    PolicyProfile,
    PolicyProfileError,
    active_profile,
    default_profile,
    load_profile,
    profile_from_dict,
    set_active_profile,
)


# The values dispatch/scoring.py carried before the profile existed.
OLD_CONSTANTS = {
    "home_base": "Jacksonville, FL",
    "operating_radius_miles": 500,
    "fuel_cost_per_mile": 0.62,
    "hours_available_default": 11.0,
    "drive_speed_mph": 50,
    "weight_limit_lbs": 45000,
}


@pytest.fixture(autouse=True)
def _clean_profile_cache():
    set_active_profile(None)
    yield
    set_active_profile(None)


class TestTheMoveChangedNothing:
    def test_defaults_reproduce_the_old_constants_exactly(self):
        p = default_profile()
        for name, value in OLD_CONSTANTS.items():
            assert getattr(p, name) == value, name

    def test_default_rate_bands_reproduce_the_old_constants(self):
        r = default_profile().rate_per_mile
        assert (r.floor, r.good, r.excellent) == (2.50, 4.00, 5.50)

    def test_the_shipped_file_matches_the_in_code_defaults(self):
        """A drifted file would score differently from a fresh checkout."""
        from dispatch.policy import SHIPPED_PROFILE_PATH

        raw = json.loads(SHIPPED_PROFILE_PATH.read_text(encoding="utf-8"))
        from_file = profile_from_dict(raw)
        in_code = default_profile()
        for name in OLD_CONSTANTS:
            assert getattr(from_file, name) == getattr(in_code, name), name


class TestDefaultsAreHonest:
    def test_defaults_say_they_are_defaults(self):
        assert default_profile().is_default is True

    def test_a_loaded_profile_does_not_claim_to_be_default(self, tmp_path):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({"profile_version": "1.0.0"}), encoding="utf-8")
        assert load_profile(path).is_default is False

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        """A fresh install works, on defaults that admit what they are."""
        p = load_profile(tmp_path / "absent.json")
        assert p.is_default is True
        assert p.home_base == "Jacksonville, FL"


class TestTheOperatorCanChangeValues:
    def test_a_supplied_value_overrides_the_default(self, tmp_path):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({
            "profile_version": "1.0.0",
            "money": {"fuel_cost_per_mile": 0.21},
        }), encoding="utf-8")
        assert load_profile(path).fuel_cost_per_mile == 0.21

    def test_unsupplied_values_keep_their_defaults(self, tmp_path):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({
            "profile_version": "1.0.0",
            "money": {"fuel_cost_per_mile": 0.21},
        }), encoding="utf-8")
        p = load_profile(path)
        assert p.weight_limit_lbs == 45000
        assert p.home_base == "Jacksonville, FL"

    def test_rate_bands_merge_individually(self, tmp_path):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({
            "profile_version": "1.0.0",
            "money": {"rate_per_mile": {"floor": 3.00}},
        }), encoding="utf-8")
        r = load_profile(path).rate_per_mile
        assert (r.floor, r.good, r.excellent) == (3.00, 4.00, 5.50)


class TestValidationIsTotal:
    """A half-applied profile is the worst possible state."""

    def test_a_typo_is_refused_rather_than_ignored(self):
        with pytest.raises(PolicyProfileError, match="unknown key"):
            profile_from_dict({"profile_version": "1.0.0",
                               "money": {"fuel_cost_per_mil": 0.21}})

    def test_an_unknown_section_is_refused(self):
        with pytest.raises(PolicyProfileError, match="unknown top-level key"):
            profile_from_dict({"profile_version": "1.0.0", "monies": {}})

    def test_a_non_numeric_value_is_refused(self):
        with pytest.raises(PolicyProfileError, match="must be a number"):
            profile_from_dict({"profile_version": "1.0.0",
                               "money": {"fuel_cost_per_mile": "cheap"}})

    def test_a_negative_value_is_refused(self):
        with pytest.raises(PolicyProfileError, match="greater than zero"):
            profile_from_dict({"profile_version": "1.0.0",
                               "capability": {"weight_limit_lbs": -1}})

    def test_rate_bands_out_of_order_are_refused(self):
        with pytest.raises(PolicyProfileError, match="floor <= good <= excellent"):
            profile_from_dict({"profile_version": "1.0.0",
                               "money": {"rate_per_mile": {"floor": 9.0}}})

    def test_a_missing_version_is_refused(self):
        with pytest.raises(PolicyProfileError, match="profile_version"):
            profile_from_dict({"profile_version": ""})

    def test_every_problem_is_reported_not_just_the_first(self):
        with pytest.raises(PolicyProfileError) as exc:
            profile_from_dict({
                "profile_version": "1.0.0",
                "money": {"fuel_cost_per_mile": "cheap"},
                "capability": {"weight_limit_lbs": -1, "drive_speed_mph": "fast"},
            })
        message = str(exc.value)
        assert "fuel_cost_per_mile" in message
        assert "weight_limit_lbs" in message
        assert "drive_speed_mph" in message

    def test_a_comment_key_is_allowed(self):
        p = profile_from_dict({"_comment": "notes", "profile_version": "1.0.0",
                               "money": {"_why": "x", "fuel_cost_per_mile": 0.3}})
        assert p.fuel_cost_per_mile == 0.3

    def test_malformed_json_is_refused(self, tmp_path):
        path = tmp_path / "p.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(PolicyProfileError, match="could not be read"):
            load_profile(path)


class TestTheProfileCannotGrantAuthority:
    """Not an omission. A setting that grants authority can be set by accident."""

    @pytest.mark.parametrize("key", ["auto_accept", "auto_decline", "auto_send",
                                     "auto_book", "skip_human_review"])
    def test_an_authority_granting_key_is_refused(self, key):
        with pytest.raises(PolicyProfileError, match="unknown top-level key"):
            profile_from_dict({"profile_version": "1.0.0", key: True})


class TestRunningSystemDegradesHonestly:
    def test_a_bad_file_does_not_stop_dispatch(self, tmp_path, monkeypatch):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({"profile_version": "1.0.0",
                                    "capability": {"weight_limit_lbs": -5}}),
                        encoding="utf-8")
        monkeypatch.setenv("DISPATCH_POLICY_PROFILE", str(path))
        set_active_profile(None)
        p = active_profile()
        assert p.weight_limit_lbs == 45000  # fell back, did not partially apply

    def test_a_bad_file_says_why(self, tmp_path, monkeypatch):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({"profile_version": "1.0.0",
                                    "capability": {"weight_limit_lbs": -5}}),
                        encoding="utf-8")
        monkeypatch.setenv("DISPATCH_POLICY_PROFILE", str(path))
        set_active_profile(None)
        assert active_profile().warnings
        assert "weight_limit_lbs" in active_profile().warnings[0]

    def test_a_good_file_carries_no_warning(self, tmp_path, monkeypatch):
        path = tmp_path / "p.json"
        path.write_text(json.dumps({"profile_version": "1.0.0"}), encoding="utf-8")
        monkeypatch.setenv("DISPATCH_POLICY_PROFILE", str(path))
        set_active_profile(None)
        assert active_profile().warnings == ()


class TestScoringReadsTheProfile:
    """The point of the exercise: business values are editable without Python."""

    def _load(self):
        return {
            "load_id": "L1",
            "origin": "Jacksonville, FL",
            "destination": "Savannah, GA",
            "distance_miles": 140,
            "rate": 625,
            "weight_lbs": 20000,
            "equipment_match": "match",
        }

    def test_changing_fuel_cost_changes_the_fuel_estimate(self):
        from dispatch.scoring import compute_fuel_estimate

        set_active_profile(default_profile())
        before = compute_fuel_estimate(self._load())

        cheap = profile_from_dict({"profile_version": "1.0.0",
                                   "money": {"fuel_cost_per_mile": 0.21}})
        set_active_profile(cheap)
        after = compute_fuel_estimate(self._load())

        assert after < before

    def test_changing_the_weight_limit_changes_route_risk(self):
        from dispatch.scoring import compute_route_risk

        set_active_profile(default_profile())
        assert "overweight" not in compute_route_risk(self._load())

        strict = profile_from_dict({"profile_version": "1.0.0",
                                    "capability": {"weight_limit_lbs": 10000}})
        set_active_profile(strict)
        assert "overweight" in compute_route_risk(self._load())

    def test_changing_the_rate_floor_changes_the_economic_flag(self):
        from dispatch.scoring import compute_economic_opportunity

        set_active_profile(default_profile())
        assert "Good" in compute_economic_opportunity(self._load())

        demanding = profile_from_dict({"profile_version": "1.0.0",
                                       "money": {"rate_per_mile":
                                                 {"floor": 5.0, "good": 6.0,
                                                  "excellent": 7.0}}})
        set_active_profile(demanding)
        assert "Below floor" in compute_economic_opportunity(self._load())

    def test_changing_home_base_changes_deadhead(self):
        from dispatch.scoring import compute_deadhead_miles

        set_active_profile(default_profile())
        from_jax = compute_deadhead_miles(self._load())

        moved = profile_from_dict({"profile_version": "1.0.0",
                                   "identity": {"home_base": "Atlanta, GA"}})
        set_active_profile(moved)
        assert compute_deadhead_miles(self._load()) != from_jax

    def test_zero_lines_of_python_changed_between_those_four(self):
        """Stated as a test because it is the doctrine, not a nicety."""
        assert isinstance(default_profile(), PolicyProfile)
