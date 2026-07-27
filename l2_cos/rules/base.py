"""Rule-module framework — L2-COS Processing Layer.

Cloned from cin_lite/rules/base.py (Rule 15): every rule module is a
standalone, DETERMINISTIC logic unit exposing NAME/VERSION/run(...). It
returns an IntelligenceScore (l2_cos/models/intelligence.py) rather than
cin_lite's RuleResult — same module/version/flags/findings shape, plus a
mandatory 0-100 score, since every module's score rolls up into the
publisher trigger (System Rule 4).

A rule module's `run` signature:

    run(load: dict, *, facility_pickup=None, facility_delivery=None, broker=None) -> IntelligenceScore

`load` is the raw acquisition record (see l2_cos/acquisition.py). The
facility/broker arguments are looked up once from the Operational
Intelligence Libraries (System Rule 14 — l2_cos/intelligence_store.py) and
passed to every module unchanged; a module never re-derives facility or
broker facts itself.
"""

from __future__ import annotations

from l2_cos.models.intelligence import BrokerIntelligence, IntelligenceScore, LocationIntelligence

__all__ = ["IntelligenceScore", "LocationIntelligence", "BrokerIntelligence"]
