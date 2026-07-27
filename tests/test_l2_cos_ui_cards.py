"""Tests for the Operations Portal Card logic (dashboard doctrine)."""

from __future__ import annotations

from l2_cos.models.intelligence import PUBLISH_THRESHOLD
from l2_cos.ui import cards
from l2_cos.ui.repository import LoadBundle, get_load_bundle, list_load_bundles


def test_is_high_value_match_threshold():
    assert not cards.is_high_value_match(PUBLISH_THRESHOLD - 1)
    assert cards.is_high_value_match(PUBLISH_THRESHOLD)


def test_build_card_clean_load_has_badge(seeded_l2_cos_archive):
    bundles = {b.load_id: b for b in list_load_bundles()}
    clean = next(b for b in bundles.values() if b.overall_score >= PUBLISH_THRESHOLD)
    card = cards.build_card(clean)

    assert card.high_value_match is True
    assert card.badge == f"✅ HIGH VALUE MATCH | Score {clean.overall_score}"
    assert card.stage == "BOOKED"


def test_build_card_below_threshold_has_no_badge(seeded_l2_cos_archive):
    bundles = list_load_bundles()
    risky = next(b for b in bundles if b.overall_score < PUBLISH_THRESHOLD)
    card = cards.build_card(risky)

    assert card.high_value_match is False
    assert card.badge == ""


def test_red_indicator_when_facility_or_broker_flags_present(seeded_l2_cos_archive):
    bundles = list_load_bundles()
    for bundle in bundles:
        card = cards.build_card(bundle)
        # Both sample loads' facilities/brokers carry at least one historical flag.
        assert card.indicator == cards.RED_INDICATOR
        assert card.red_flag_reasons


def test_clear_indicator_when_no_flags():
    from l2_cos.models.intelligence import BrokerIntelligence, LocationIntelligence
    from l2_cos.models.state import Load

    clean_facility = LocationIntelligence(facility_id="F1", name="Clean DC", address="1 Rd")
    clean_broker = BrokerIntelligence(broker_id="B1", company_name="Clean Co", payment_terms="Net 15")
    bundle = LoadBundle(
        load_id="L-1",
        raw_load={"origin": "A", "destination": "B", "equipment_type": "Dry Van"},
        intelligence={"broker_risk": {"flags": ["payment_terms_acceptable"]}},
        overall_score=50,
        load=Load(load_id="L-1"),
        facility_pickup=clean_facility,
        facility_delivery=clean_facility,
        broker=clean_broker,
        publisher_result=None,
    )
    card = cards.build_card(bundle)
    assert card.indicator == cards.CLEAR_INDICATOR
    assert card.red_flag_reasons == []


def test_broker_name_falls_back_to_broker_id_when_unresolved():
    from l2_cos.models.state import Load

    bundle = LoadBundle(
        load_id="L-2",
        raw_load={"origin": "A", "destination": "B", "broker_id": "BRK-UNKNOWN"},
        intelligence={},
        overall_score=10,
        load=Load(load_id="L-2"),
        facility_pickup=None,
        facility_delivery=None,
        broker=None,
        publisher_result=None,
    )
    card = cards.build_card(bundle)
    assert card.broker_name == "BRK-UNKNOWN"
    assert card.red_flag_reasons == []


def test_get_load_bundle_missing_returns_none():
    assert get_load_bundle("NOPE") is None
