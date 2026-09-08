"""The equipment record is the asset profile the capacity engine was waiting for.

**Owner ruling, 2026-09-08:** *"can you build entry space that feeds load
arrangement and cargo limits for scoring and Booking? They need real numbers but
I do not want to hard code these numbers in. Then changing equipment requires a
trip back to you."*

`PhysicalCapacity` has carried `asset_profile_id` and reported `UNCONFIGURED`
since it was written, and nobody had ever filled one in. This builds one from
the units themselves rather than inventing a new shape -- so **swapping the
trailer is a Fleet edit, not a code change**, which is the whole of the ruling.
"""

from __future__ import annotations

import pytest

from dispatch import capacity

VAN = dict(unit_number="VAN-1", equipment_type="cargo_van", payload_lb=4604,
           cargo_length_in=146, cargo_width_in=54, cargo_height_in=79,
           pallet_positions=4, has_ramp=1)
TRAILER = dict(unit_number="TRL-1", equipment_type="enclosed_trailer",
               payload_lb=5918, cargo_length_in=288, cargo_width_in=100,
               cargo_height_in=84, pallet_positions=8)


class TestTheNumbersComeFromTheUnits:
    def test_weight_is_the_sum_of_the_payloads(self):
        assert capacity.physical_capacity_from_equipment(
            [VAN, TRAILER]).max_weight_lbs == 10522

    def test_volume_is_derived_and_never_typed(self):
        """A number entered twice is a number that will disagree with itself."""
        envelope = capacity.physical_capacity_from_equipment([VAN])
        # Four places, the module's own `_round` -- not two. A capacity engine
        # that rounds differently from itself is one nobody can reconcile.
        assert envelope.max_volume_cuft == round(146 * 54 * 79 / 1728, 4)

    def test_linear_feet_is_derived_from_the_lengths(self):
        assert capacity.physical_capacity_from_equipment(
            [VAN, TRAILER]).max_linear_feet == round((146 + 288) / 12, 4)

    def test_pallet_positions_are_counted_not_computed(self):
        """A wheel well costs a position the floor area knows nothing about, so
        the number that matters is the one somebody counted."""
        assert capacity.physical_capacity_from_equipment(
            [VAN, TRAILER]).max_pallets == 12

    def test_a_feature_on_any_unit_is_a_feature_of_the_combination(self):
        envelope = capacity.physical_capacity_from_equipment([VAN, TRAILER])
        assert envelope.has_ramp is True
        assert envelope.has_liftgate is False

    def test_changing_a_unit_changes_the_envelope(self):
        """**The ruling, as a test.** Swapping the trailer is a Fleet edit."""
        bigger = dict(TRAILER, payload_lb=7000)
        assert (capacity.physical_capacity_from_equipment([VAN, bigger])
                .max_weight_lbs) == 11604


class TestItIsHonestAboutWhatItDoesNotKnow:
    def test_no_equipment_is_unconfigured(self):
        envelope = capacity.physical_capacity_from_equipment([])
        assert envelope.configuration_status == "UNCONFIGURED"
        assert envelope.max_weight_lbs == 0

    def test_a_unit_with_no_numbers_makes_it_partial(self):
        envelope = capacity.physical_capacity_from_equipment(
            [VAN, dict(unit_number="TRL-1", equipment_type="enclosed_trailer")])
        assert envelope.configuration_status == "PARTIAL"
        assert "1 of 2" in envelope.configuration_source

    def test_an_unstated_payload_adds_nothing_rather_than_zero(self):
        """**Zero is "not stated", never "no limit".** A total with a blank in
        it is a number that looks like an answer."""
        assert capacity.physical_capacity_from_equipment(
            [VAN, dict(unit_number="TRL-1")]).max_weight_lbs == 4604

    def test_it_never_marks_itself_verified(self):
        """Somebody has to have checked the plate against the paperwork, and no
        function can attest to that."""
        assert capacity.physical_capacity_from_equipment(
            [VAN, TRAILER]).configuration_status == "UNVERIFIED"

    def test_a_unit_missing_one_dimension_contributes_no_volume(self):
        """Two of three dimensions is not a box."""
        flat = dict(VAN, cargo_height_in=0)
        assert capacity.physical_capacity_from_equipment([flat]).max_volume_cuft == 0

    def test_rubbish_in_a_field_does_not_raise(self):
        """A number typed as a word must not take the Booking board down."""
        envelope = capacity.physical_capacity_from_equipment(
            [dict(VAN, payload_lb="lots")])
        assert envelope.max_weight_lbs == 0


class TestNothingIsHardcoded:
    def test_the_module_holds_no_vehicle_numbers(self):
        """The whole point. **The only constant here is cubic inches per cubic
        foot**, which is arithmetic and not a fact about a truck."""
        import inspect

        source = inspect.getsource(capacity.physical_capacity_from_equipment)
        for from_the_document in ("4604", "5918", "9950", "9990", "19940"):
            assert from_the_document not in source
