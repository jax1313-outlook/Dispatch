"""Rule registry — Processing Layer.

To add a rule: create a module exposing NAME/VERSION/run(contract) and append it
to ALL_RULES. Nothing else in the pipeline needs to change.
"""

from . import (
    set_aside,
    naics_sin,
    pricing_anomaly,
    cyber_compliance,
    vendor_network,
    past_performance,
    subcontractor_dominance,
    jv_mp_structure,
    foreign_influence,
)

ALL_RULES = [
    set_aside,
    naics_sin,
    pricing_anomaly,
    cyber_compliance,
    vendor_network,
    past_performance,
    subcontractor_dominance,
    jv_mp_structure,
    foreign_influence,
]
