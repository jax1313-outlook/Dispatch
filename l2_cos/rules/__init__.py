"""Rule registry — L2-COS Processing Layer.

To add a rule: create a module exposing NAME/VERSION/run(load, **intel) and
append it to ALL_RULES. Nothing else in the pipeline needs to change.
"""

from . import (
    lane_fit,
    rate_anomaly,
    facility_risk,
    broker_risk,
    capacity_match,
    deadhead_cost,
)

ALL_RULES = [
    lane_fit,
    rate_anomaly,
    facility_risk,
    broker_risk,
    capacity_match,
    deadhead_cost,
]
