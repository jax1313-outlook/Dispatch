"""Where a truck's capacity profile lives, so the capacity engine can be reached.

`dispatch/capacity.py` is 1,861 lines with 1,000 lines of tests against it, and
before this module nothing in the running program could use any of it:

  * `DynamicCapacity(` was never instantiated outside `tests/`;
  * there was no table it could be stored in;
  * the only production call into `dispatch/scoring.py` is
    `portal/helpers.py` -> `score_load(data)` with no `capacity` argument, and
    `score_load`'s own docstring says that without one "the result is exactly
    what it has always been".

That is a worse state than either alternative. Dead code that is *well tested*
is invisible -- it raises the gated coverage figure while doing nothing -- and a
reviewer reading the test file concludes the capability is in service.

**The resolution is to wire it, not to reserve it.** `docs/MANAGER.md` is the
repository's precedent for formally reserving a capability, and it is explicit
about what it is reserving: something "named in planning and never built". That
precedent does not reach working code. The Purpose Statement's second verb is
*Evaluate Possibilities*, and this engine is the only thing in the repository
that does it; shelving it would remove a built capability to tidy up a gap that
is one table wide.

What was actually missing is small: an asset's capacity profile had nowhere to
be written down. Equipment rows already exist, so a profile is one row per
truck, and the sections serialise as JSON because they are a document -- nothing
queries inside them, and a column per field would be forty columns that change
whenever the engine grows one.

**Utilization is not stored.** `used_weight_lbs` and its siblings describe
freight physically on a trailer right now, and reconstructing yesterday's
utilization from a saved row would present a stale fact as a current one. A
rehydrated profile carries the verified specification and an empty load.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone

from dispatch.capacity import (
    CargoArrangementCapacity,
    DynamicCapacity,
    PhysicalCapacity,
    PositionCapacity,
    ReserveCapacity,
    TimeCapacity,
)
from dispatch.db import get_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS capacity_profiles (
    equipment_id  TEXT PRIMARY KEY,
    capacity_id   TEXT NOT NULL,
    driver_id     TEXT NOT NULL DEFAULT '',
    physical      TEXT NOT NULL DEFAULT '{}',
    time_capacity TEXT NOT NULL DEFAULT '{}',
    position      TEXT NOT NULL DEFAULT '{}',
    reserve       TEXT NOT NULL DEFAULT '{}',
    cargo         TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
"""

#: column -> the dataclass it holds. Utilization and the ledgers are absent by
#: design; see the module docstring.
SECTIONS = {
    "physical": PhysicalCapacity,
    "time_capacity": TimeCapacity,
    "position": PositionCapacity,
    "reserve": ReserveCapacity,
    "cargo": CargoArrangementCapacity,
}

#: Utilization describes what is on the trailer now. Never persisted, never
#: rehydrated -- a saved "used 18,000 lbs" would come back as a claim about
#: today's trailer made from last week's freight.
UTILIZATION_FIELDS = (
    "used_weight_lbs", "used_volume_cuft", "used_linear_feet", "used_pallets",
)


def init_capacity_schema(conn) -> None:
    conn.executescript(_SCHEMA)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dump(section) -> str:
    data = asdict(section)
    for name in UTILIZATION_FIELDS:
        data.pop(name, None)
    return json.dumps(data, sort_keys=True)


def _hydrate(cls, raw: str):
    """Build a section from stored JSON, ignoring fields the class no longer has.

    Forward and backward compatible on purpose: a profile written by an older
    build must still load after the engine grows a field, and a field that was
    removed must not crash the constructor. A capacity profile that cannot be
    read is a truck that silently stops being assessable.
    """
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    allowed = {f.name for f in fields(cls)} if is_dataclass(cls) else set()
    return cls(**{k: v for k, v in data.items() if k in allowed})


def save_profile(capacity: DynamicCapacity) -> dict:
    """Write (or replace) the profile for this truck. One row per equipment."""
    if not capacity.equipment_id:
        raise ValueError("a capacity profile must name the equipment it describes")
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO capacity_profiles
                   (equipment_id, capacity_id, driver_id, physical, time_capacity,
                    position, reserve, cargo, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(equipment_id) DO UPDATE SET
                   capacity_id=excluded.capacity_id,
                   driver_id=excluded.driver_id,
                   physical=excluded.physical,
                   time_capacity=excluded.time_capacity,
                   position=excluded.position,
                   reserve=excluded.reserve,
                   cargo=excluded.cargo,
                   updated_at=excluded.updated_at""",
            (
                capacity.equipment_id, capacity.capacity_id, capacity.driver_id,
                _dump(capacity.physical), _dump(capacity.time),
                _dump(capacity.position), _dump(capacity.reserve), _dump(capacity.cargo),
                now, now,
            ),
        )
    return get_profile_row(capacity.equipment_id)


def get_profile_row(equipment_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM capacity_profiles WHERE equipment_id=?", (equipment_id,)
        ).fetchone()
    return dict(row) if row else None


def load_capacity(equipment_id: str, *, driver_id: str = "") -> DynamicCapacity | None:
    """The truck's capacity as the engine wants it, or None if none is on file.

    None is a real answer and callers must handle it: an unprofiled truck is
    `UNCONFIGURED`, not "assume a 53-foot dry van". Inventing a specification is
    how a load gets accepted onto a trailer that cannot carry it.
    """
    row = get_profile_row(equipment_id)
    if row is None:
        return None
    return DynamicCapacity(
        capacity_id=row["capacity_id"],
        equipment_id=row["equipment_id"],
        driver_id=driver_id or row["driver_id"],
        physical=_hydrate(PhysicalCapacity, row["physical"]),
        time=_hydrate(TimeCapacity, row["time_capacity"]),
        position=_hydrate(PositionCapacity, row["position"]),
        reserve=_hydrate(ReserveCapacity, row["reserve"]),
        cargo=_hydrate(CargoArrangementCapacity, row["cargo"]),
        updated_at=row["updated_at"],
    )


def list_profiles() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM capacity_profiles ORDER BY equipment_id"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_profile(equipment_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM capacity_profiles WHERE equipment_id=?", (equipment_id,)
        )
    return cursor.rowcount > 0


def profile_coverage() -> dict:
    """How many trucks can be assessed, and how many cannot.

    A number a screen can state. "Capacity is implemented" and "three of your
    four trucks have no profile, so three of them cannot be assessed" are
    different facts, and only the second one is actionable.
    """
    from dispatch import store

    equipment = store.list_equipment()
    profiled = {row["equipment_id"] for row in list_profiles()}
    unprofiled = [e for e in equipment if e["equipment_id"] not in profiled]
    return {
        "total": len(equipment),
        "profiled": len([e for e in equipment if e["equipment_id"] in profiled]),
        "unprofiled": [
            {"equipment_id": e["equipment_id"], "label": e.get("unit_number") or e["equipment_id"]}
            for e in unprofiled
        ],
        "complete": bool(equipment) and not unprofiled,
    }
