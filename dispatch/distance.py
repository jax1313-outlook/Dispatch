"""Miles for a lane, and where the number came from.

CO-3, 2026-09-14. The mapping and distance provider is **not chosen**. Scoring
still needs miles, so this module asks in a fixed order and says, every time,
which answer it used:

    1. the mapping provider  -- through `dispatch/connectors/mapping_connector.py`,
                                the governed boundary that already exists for it.
                                Today it reports UNCONFIGURED and answers nothing.
    2. miles typed or listed -- what the Owner typed, or the listing carried. MANUAL.
    3. the built-in lane table -- `dispatch.scoring`'s 22 lanes, the last resort.
                                UNVERIFIED: nobody measured these for this truck.

Nothing is estimated beyond that. A lane none of the three can answer has no
miles, the status is ABSENT, and every consumer shows the gap.

**Vendor-agnostic.** No provider is named here or anywhere outside its adapter.
When one is chosen it is configured on the connector, and this module starts
receiving LIVE answers without a change.
"""

from __future__ import annotations

BASIS_PROVIDER = "mapping provider"
BASIS_TYPED = "as typed or listed"
BASIS_TABLE = "built-in distance table"
BASIS_NONE = "no source"


def provider_status() -> str:
    """The mapping provider's status word. UNCONFIGURED until one is chosen."""
    try:
        from dispatch.connectors import registry

        return registry.get("mapping").configuration().status.value
    except Exception:  # noqa: BLE001 - a status line must never take a screen down
        return "UNAVAILABLE"


def _from_provider(origin: str, destination: str) -> tuple:
    """`(miles, status_word)` from the connector; `(None, word)` when it cannot answer."""
    try:
        from dispatch.connectors import registry
        from dispatch.connectors.contract import ConnectorRequest

        connector = registry.get("mapping")
        result = connector.fetch(ConnectorRequest(
            operation="distance",
            params={"origin": origin, "destination": destination, "profile": "practical"},
            requested_by="dispatch.distance"))
    except Exception:  # noqa: BLE001 - reported as UNAVAILABLE, never raised to a card
        return None, "UNAVAILABLE"
    if not result.ok or result.payload is None:
        return None, result.status.value
    try:
        miles = float(result.payload.data.get("miles"))
    except (TypeError, ValueError):
        return None, "UNAVAILABLE"
    return (miles if miles > 0 else None), result.status.value


def _typed(value):
    try:
        miles = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return miles if miles > 0 else None


def miles_between(origin: str, destination: str, *, typed=None) -> dict:
    """Miles for one lane, with the basis and status that produced them.

    Returns `{"miles", "basis", "status", "provider_status", "note"}`.
    """
    provider_miles, provider_word = _from_provider(origin or "", destination or "")
    if provider_miles:
        return {"miles": provider_miles, "basis": BASIS_PROVIDER, "status": provider_word,
                "provider_status": provider_word, "note": ""}

    typed_miles = _typed(typed)
    if typed_miles:
        return {"miles": typed_miles, "basis": BASIS_TYPED, "status": "MANUAL",
                "provider_status": provider_word,
                "note": "Miles as typed or listed; the mapping provider is %s."
                        % provider_word}

    from dispatch.scoring import known_distance

    table = known_distance(origin or "", destination or "") if origin and destination else None
    if table is not None:
        return {"miles": float(table), "basis": BASIS_TABLE, "status": "UNVERIFIED",
                "provider_status": provider_word,
                "note": "Miles from the built-in distance table; the mapping provider is %s."
                        % provider_word}

    return {"miles": None, "basis": BASIS_NONE, "status": "ABSENT",
            "provider_status": provider_word,
            "note": "No miles: the mapping provider is %s, none were typed, and the "
                    "cities are not in the built-in table." % provider_word}
