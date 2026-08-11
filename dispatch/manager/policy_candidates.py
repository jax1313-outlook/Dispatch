"""Manager's Policy Routing Hook Candidate -- Stage 12 Phase M7, per
DISPATCH_STAGE12_MANAGER_M7_POLICY_HOOK_DESIGN_v1.md.

This is NOT a policy engine. It does not design, implement, or
consume "GX." Nothing in this module or anything that calls it acts
on any signal, approves anything, or removes Mike from any decision.
It defines the narrowest possible read-only interface shape a future,
separately-designed, separately-approved system could someday consume
-- counts only, of the single classification tier doctrine names as
the only one a future automated system could ever safely touch
(MANAGER.md's own "Auto-log: no card, no interruption, routine,
expected, low-risk" definition, i.e. card_level 0 -- classify.ROUTINE
and classify.NOISE specifically, not Status, which is still a
human-facing "awareness only" tier per MANAGER.md Section 9).

No individual signal detail (load IDs, exception IDs, etc.) is ever
exposed here -- counts only. Reuses staff_report.generate_staff_report()'s
already-computed output; this module changes nothing about how that
function works.
"""

from __future__ import annotations

from dispatch.manager import staff_report
from dispatch.manager.classify import NOISE, ROUTINE

_AUTO_LOG_CLASSIFICATIONS = (ROUTINE, NOISE)

_NOTE = (
    "Counts only. No individual signal detail is exposed or retained. "
    "Nothing here is actionable without further Mike-approved work; "
    "this is a Phase M7 candidate interface, not a working policy engine."
)


def auto_log_summary() -> dict:
    """Returns Auto-log-tier (card_level 0) classification counts from
    the current Staff Report pass. Never exposes Status, Review Needed,
    Decision Needed, Conflict, Archive, or Authority counts, and never
    exposes individual record data -- both deliberate, narrow scope
    limits, not omissions.
    """
    report = staff_report.generate_staff_report()
    counts = report["counts"]
    auto_log_counts = {
        classification: counts[classification]
        for classification in _AUTO_LOG_CLASSIFICATIONS
        if classification in counts
    }
    return {"auto_log_counts": auto_log_counts, "note": _NOTE}
