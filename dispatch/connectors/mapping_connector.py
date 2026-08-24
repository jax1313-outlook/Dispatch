"""Mapping and Routing Connector — distance and geometry, not decisions.

Mileage is the number most likely to be quietly invented. Dispatch already
computes revenue-per-mile, fuel estimates and projected profit from
``distance_miles``, and every one of those figures is only as honest as its
source. Today that source is a value carried on the load record -- entered by a
person, or taken from a load board posting -- and the difference between "the
broker posted 350 miles" and "a routing engine computed 372 practical truck
miles" is a real difference that nothing in the codebase can currently express.

This connector is where the second kind of number would arrive, and its payload
is shaped so the two can never be confused: every distance carries the provider
that produced it, the profile it was computed under (practical, shortest,
truck-legal), and its status word. A distance with no provenance is not upgraded
to one that has some by passing through here.

What it may collect: route geometry, practical and truck-legal distances, drive
time estimates, and the map visual references Route Risk's existing
``map_visual_placeholder`` has been carrying a placeholder for since it was
written (``route_risk/engine.py``).

What it may never do, and cannot declare: set a rate from a mileage, decide
whether a load is worth taking, or write a distance into Current Reality. A
routing engine's mileage is an input to the Opportunity layer's scoring, and the
scoring is advisory all the way to the human gate.

No mapping provider is configured, so every operation refuses. Dispatch's
existing distance handling is untouched.
"""

from __future__ import annotations

from dispatch.connectors.contract import (
    BaseConnector,
    CapabilityDeclaration,
    ConnectorRequest,
    ConnectorResult,
)

PAYLOAD_KIND = "route_geometry"

#: Distance profiles a routing provider may be asked for. Named because
#: "miles" alone is ambiguous, and the ambiguity costs money: a shortest-path
#: mileage under-reports a truck-legal route by enough to matter on a settlement.
DISTANCE_PROFILES: tuple[str, ...] = ("practical", "shortest", "truck_legal")


class MappingAndRoutingConnector(BaseConnector):
    """Computes distances, drive times and route geometry. No provider is configured."""

    connector_id = "mapping"
    connector_name = "Mapping and Routing Connector"
    required_config_keys = ("DISPATCH_MAPPING_API_URL", "DISPATCH_MAPPING_API_KEY")
    credential_keys = ("DISPATCH_MAPPING_API_KEY",)
    auth_method = "api_key"
    capability_declaration = CapabilityDeclaration(
        collects=(
            "route geometry",
            "practical and truck-legal distances",
            "drive time estimates",
            "map visual references",
        ),
        produces=("distances and geometry carrying the profile and provider that produced them",),
        notes=(
            "A computed distance is an input to advisory scoring. It does not set a rate, and "
            "it is not written into a load record by this connector."
        ),
    )

    def fetch(self, request: ConnectorRequest) -> ConnectorResult:
        return self.unconfigured(
            request,
            extra=(
                "No mapping provider is configured. Distances shown in Dispatch remain the ones "
                "already on the load record, with whatever provenance they came in with; "
                "nothing here substitutes a computed number for a missing one."
            ),
        )
