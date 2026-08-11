"""Classification per MANAGER.md Section 7's nine-class taxonomy.

Six of the nine classes are reachable from this build's signal sources
(Status, Review Needed, Decision Needed, Conflict, Archive, plus the
Routine/Noise floor for anything below the Review Needed bar) -- no
Library Candidate or Authority signal source is wired in this build.
The full taxonomy is still named explicitly rather than narrowed, so
a future signal source can be classified without inventing a new
taxonomy.

Card levels follow MANAGER.md Section 9 / DISPATCH_CONSTITUTION_v3.md
Section 17: 0 Silent Log, 1 Status, 2 Review, 3 Decision, 4 Conflict,
5 Authority.

ARCHIVE's card level was corrected from 1 to 2 when the Archive Review
Queue wiring (DISPATCH_STAGE12_MANAGER_ARCHIVE_WIRING_DESIGN_v1.md)
made this class reachable for the first time -- it had been defined
since the M2+M3 build but was dead code until now, and the original
value of 1 sat below REVIEW_BAR_CARD_LEVEL, which would have silently
made every Archive Review card unreachable. 2 matches
DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md Section 7's own Portal Card
Model table (Archive Review Card = Level 2) exactly.

The specific thresholds below (e.g. "2x the stall threshold is Decision
Needed, not just Status") are this build's own tunable defaults, not
doctrine -- doctrine specifies the nine classes and their card levels,
not which numeric threshold separates them for a given signal type.
Flagged here rather than silently assumed permanent.
"""

from __future__ import annotations

from dispatch.manager import security_monitor, signals

ROUTINE = "Routine"
STATUS = "Status"
REVIEW_NEEDED = "Review Needed"
DECISION_NEEDED = "Decision Needed"
CONFLICT = "Conflict"
AUTHORITY = "Authority"
ARCHIVE = "Archive"
LIBRARY_CANDIDATE = "Library Candidate"
NOISE = "Noise"

_CARD_LEVEL_BY_CLASS = {
    ROUTINE: 0,
    STATUS: 1,
    REVIEW_NEEDED: 2,
    DECISION_NEEDED: 3,
    CONFLICT: 4,
    AUTHORITY: 5,
    ARCHIVE: 2,
    LIBRARY_CANDIDATE: 2,
    NOISE: 0,
}

# A signal only earns a Work Item + Portal Card at this card level or above.
REVIEW_BAR_CARD_LEVEL = 2

# Stalled-load / overdue-settlement severity split: "just tipped over"
# vs. "meaningfully stuck." Tunable default, documented above.
_STALLED_LOAD_DECISION_MULTIPLE = 2.0
_SETTLEMENT_DECISION_DAYS_OVERDUE = 7

_EXCEPTION_SEVERITY_TO_CLASS = {
    "low": REVIEW_NEEDED,
    "medium": REVIEW_NEEDED,
    "high": DECISION_NEEDED,
    "critical": CONFLICT,
}

_CONFLICT_CARD_LEVEL_TO_CLASS = {
    0: NOISE,
    1: STATUS,
    2: REVIEW_NEEDED,
    3: DECISION_NEEDED,
    4: CONFLICT,
}


def _classify_stalled_load(raw: dict) -> str:
    load = raw["data"]
    if load["hours_in_status"] >= load["threshold_hours"] * _STALLED_LOAD_DECISION_MULTIPLE:
        return DECISION_NEEDED
    return STATUS


def _classify_overdue_settlement(raw: dict) -> str:
    from datetime import datetime, timezone

    stl = raw["data"]
    due = stl.get("due_date", "")
    if not due:
        return STATUS
    try:
        due_date = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return STATUS
    days_overdue = (datetime.now(timezone.utc) - due_date).days
    if days_overdue >= _SETTLEMENT_DECISION_DAYS_OVERDUE:
        return DECISION_NEEDED
    return STATUS


def _classify_open_exception(raw: dict) -> str:
    severity = raw["data"].get("severity", "medium")
    return _EXCEPTION_SEVERITY_TO_CLASS.get(severity, REVIEW_NEEDED)


def _classify_unresolved_conflict(raw: dict) -> str:
    card_level = raw["data"].get("card_level", 2)
    return _CONFLICT_CARD_LEVEL_TO_CLASS.get(card_level, REVIEW_NEEDED)


def _classify_ifta_suspect_entry(_raw: dict) -> str:
    # Verification Workflow: Partially Verified -- needs Mike's review
    # for the specific use, never auto-classified higher or lower.
    return REVIEW_NEEDED


def _classify_ifta_exception(_raw: dict) -> str:
    # Advisory only per IFTAException's own doctrine ("nothing in this
    # codebase reads an exception as a reason to block a submission or
    # a seal") -- worth a look before sealing, never a hard stop.
    return REVIEW_NEEDED


def _classify_security_pattern(_raw: dict) -> str:
    # Stage 12 Phase M6: a repeated security pattern is always Conflict
    # -- no graduated severity, regardless of which pattern fired.
    return CONFLICT


def _classify_archive_review_item(_raw: dict) -> str:
    # DISPATCH_MANAGER_BUILDOUT_DESIGN_v1.md's Portal Card Model gives
    # Archive Review Card one fixed level -- no age-based sub-tiering,
    # unlike stalled loads or overdue settlements.
    return ARCHIVE


_CLASSIFIERS = {
    signals.STALLED_LOAD: _classify_stalled_load,
    signals.OVERDUE_SETTLEMENT: _classify_overdue_settlement,
    signals.OPEN_EXCEPTION: _classify_open_exception,
    signals.UNRESOLVED_CONFLICT: _classify_unresolved_conflict,
    signals.IFTA_SUSPECT_ENTRY: _classify_ifta_suspect_entry,
    signals.IFTA_EXCEPTION: _classify_ifta_exception,
    security_monitor.SECURITY_PATTERN: _classify_security_pattern,
    signals.ARCHIVE_REVIEW_ITEM: _classify_archive_review_item,
}


def _title_and_summary(raw: dict, classification: str) -> tuple[str, str]:
    source_type = raw["source_type"]
    data = raw["data"]
    if source_type == signals.STALLED_LOAD:
        return (
            f"Stalled load {data['load_id']}",
            f"In status '{data['status']}' for {data['hours_in_status']}h "
            f"(threshold {data['threshold_hours']}h).",
        )
    if source_type == signals.OVERDUE_SETTLEMENT:
        return (
            f"Overdue settlement {data['load_id']}",
            f"Payment overdue, due date {data.get('due_date', 'unknown')}.",
        )
    if source_type == signals.OPEN_EXCEPTION:
        return (
            f"Exception: {data.get('exception_type', 'other')} ({data['load_id']})",
            data.get("description", ""),
        )
    if source_type == signals.UNRESOLVED_CONFLICT:
        return (
            f"Conflict Notice: {data.get('conflict_type', 'unknown')}",
            data.get("explanation", ""),
        )
    if source_type == signals.IFTA_SUSPECT_ENTRY:
        return (
            f"Suspect IFTA fuel purchase {data['purchase_id']}",
            f"Extraction confidence {data.get('extraction_confidence')} "
            f"below review threshold.",
        )
    if source_type == signals.IFTA_EXCEPTION:
        return (
            f"IFTA exception: {data.get('exception_type', 'unknown')}",
            data.get("detail", ""),
        )
    if source_type == security_monitor.SECURITY_PATTERN:
        return (
            f"Repeated {data['event_type']} ({data['count']}x in {data['window_hours']}h)",
            f"Security event pattern for {data['key']} -- {data['count']} occurrences.",
        )
    if source_type == signals.ARCHIVE_REVIEW_ITEM:
        return (
            f"Archive Review: {data.get('title', data.get('id', 'unknown'))}",
            f"In the Archive Review Queue, {data.get('age_days', '?')} days old. "
            f"Review and record a Keep/Delete decision at /archive -- "
            f"Manager does not action this itself.",
        )
    return (f"{source_type} signal", "")


def classify_signal(raw: dict) -> dict:
    """Returns raw signal enriched with classification, card_level,
    title, and summary. Never mutates the original signal dict.
    """
    classifier = _CLASSIFIERS.get(raw["source_type"])
    classification = classifier(raw) if classifier else ROUTINE
    title, summary = _title_and_summary(raw, classification)
    return {
        **raw,
        "classification": classification,
        "card_level": _CARD_LEVEL_BY_CLASS[classification],
        "title": title,
        "summary": summary,
    }


def clears_review_bar(classified: dict) -> bool:
    return classified["card_level"] >= REVIEW_BAR_CARD_LEVEL
