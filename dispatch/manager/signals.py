"""Read-only signal aggregation for Manager's Staff Report.

Every function here only reads. None of them mutate anything, send a
notification, or write to any table -- confirmed source-by-source
against dispatch/services.py and portal/models/conflict.py before
being wired in here (see DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md
Section 3).

One correction made during implementation, flagged here rather than
silently decided: the build design listed dispatch.services's
check_overdue_settlements() as a read-only source. It is not --
calling it marks settlements overdue in the database and sends an
email via dispatch.notifications.notify_payment_overdue() as a side
effect (that scan already runs elsewhere, e.g. the Portal's existing
"Run Aging Check" button). Manager instead reads the *result* of that
scan via dispatch.services.list_settlements(payment_status="overdue"),
a genuine read with no side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone

from dispatch import services
from portal.models import conflict as conflict_model

# Signal source_type identifiers -- used for classification, priority
# mapping, and Work Item dedup lookups (matched against WorkItem.source_type).
STALLED_LOAD = "stalled_load"
OVERDUE_SETTLEMENT = "overdue_settlement"
OPEN_EXCEPTION = "open_exception"
UNRESOLVED_CONFLICT = "unresolved_conflict"
IFTA_SUSPECT_ENTRY = "ifta_suspect_entry"


def _current_year_quarter() -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    return now.year, (now.month - 1) // 3 + 1


def collect_signals() -> list[dict]:
    """Returns a normalized list of raw signals: each item carries
    source_type, source_id, and the original record under 'data'.
    """
    raw: list[dict] = []

    for load in services.check_stalled_loads():
        raw.append({
            "source_type": STALLED_LOAD,
            "source_id": load["load_id"],
            "data": load,
        })

    for stl in services.list_settlements(payment_status="overdue"):
        raw.append({
            "source_type": OVERDUE_SETTLEMENT,
            "source_id": stl["load_id"],
            "data": stl,
        })

    for exc in services.list_exceptions(status="open"):
        raw.append({
            "source_type": OPEN_EXCEPTION,
            "source_id": exc["exception_id"],
            "data": exc,
        })

    for notice in conflict_model.get_unresolved():
        raw.append({
            "source_type": UNRESOLVED_CONFLICT,
            "source_id": notice["id"],
            "data": notice,
        })

    year, quarter = _current_year_quarter()
    for purchase in services.list_suspect_ifta_fuel_purchases(year, quarter):
        raw.append({
            "source_type": IFTA_SUSPECT_ENTRY,
            "source_id": purchase["purchase_id"],
            "data": purchase,
        })

    return raw
