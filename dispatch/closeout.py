"""The Operations closeout review, between a finished run and retention.

**AUTHORITATIVE RULING, Mike Zachary, 2026-09-17:**

    Driver completes the mission.
    Operations closes the file.
    Archive performs retention.

Three acts, three owners. A driver finishing his run does not retire the file,
and retiring the file is not the same as retaining it.

WHAT THE GATE IS
================

**A reviewed-closeout gate, not a mechanical artifact gate.** The act recorded
is *"I reviewed this file"* — not *"every artifact exists"*. The distinction is
the whole ruling, and it is not a nicety:

    Archive eligibility therefore depends upon:
    - Mission completion
    - Operations closeout review
    - Recorded closeout act
    not:
    - Automatic checklist satisfaction

A checklist gate would have re-stranded the very loads he refused to strand on
2026-09-16 — *"some loads genuinely end without a POD coming back, and forcing
completion would strand them"* — this time by making them permanently
unarchivable instead of permanently unfinished. Operations may close a file
**despite** missing artifacts; `note` is where the reason is kept.

So `review()` below is **informational**. It tells whoever is looking what is
present, what is missing and what the closing packet did. It decides nothing.
`close_file()` is the act, and `is_closed_out()` is what Archive asks.
"""

from __future__ import annotations

from dispatch import store
from dispatch.models import _utc_now

#: What the review displays, in the order Operations reads it. **Evidence
#: types, not a requirement list** -- naming them here does not make them
#: mandatory, and nothing in this module refuses an archive for a missing one.
#:
#: **The three photo names are his**, and the same three the cockpit offers and
#: Publisher fills: *"Publisher, Cockpit, Mission Record, and Placeholder
#: Registry must use the same three names."* This list carried "Photographs"
#: and "Load securement photos" until 2026-09-17, which were neither.
#:
#: Every line here can now be satisfied. The Bill of Lading -- the controlling
#: freight document, *"Federal BOL = controlling freight document"* -- got its
#: upload route in BATCH 8, and the Loaded Vehicle photo got one the same day
#: the vocabulary was corrected.
ARTIFACTS = (
    ("pod", "Signed POD"),
    ("bol", "Signed BOL"),
    # His three photo names, the same three the cockpit and Publisher use.
    ("loaded_vehicle_photo", "Photos - Loaded Vehicle"),
    ("securement_photo", "Photos - Mid-Route Securement"),
    ("final_condition_photo", "Photos - Final Condition"),
    ("document", "Other documents"),
)


def review(load: dict, record: dict | None = None,
           evidence: list[dict] | None = None) -> dict:
    """What Operations reads before closing the file. **Decides nothing.**

    `record` is the portal's mission record, passed in rather than looked up:
    the closing packet report lives in the sandbox and `dispatch/` may not
    import `portal/`.
    """
    load = dict(load or {})
    load_id = str(load.get("load_id") or "")
    if evidence is None:
        evidence = store.list_evidence(load_id) if load_id else []

    held: dict[str, int] = {}
    for item in evidence or []:
        kind = str(item.get("evidence_type") or "")
        held[kind] = held.get(kind, 0) + 1

    present, missing = [], []
    for kind, label in ARTIFACTS:
        count = held.get(kind, 0)
        line = {"type": kind, "label": label, "count": count}
        (present if count else missing).append(line)

    packet = ((record or {}).get("closing_packet") or {})
    return {
        "load_id": load_id,
        "status": str(load.get("status") or ""),
        "present": present,
        "missing": missing,
        "packet": {
            "built": bool(packet),
            "ok": bool(packet.get("ok")),
            "load_number": str(packet.get("load_number") or ""),
            "folder": str(packet.get("folder") or ""),
            "documents": len(packet.get("documents") or []),
            # Placeholders the templates could not fill. Shown because they are
            # what a reviewer would otherwise find out from the customer.
            "unanswered": list(packet.get("missing") or []),
            "note": str(packet.get("note") or ""),
        },
        "closed_out": is_closed_out(load),
        "closed_out_at": str(load.get("closed_out_at") or ""),
        "closed_out_by": str(load.get("closed_out_by") or ""),
        "note": str(load.get("closeout_note") or ""),
    }


def is_closed_out(load: dict | None) -> bool:
    """Whether Operations has reviewed this file. The one question Archive asks."""
    return bool((load or {}).get("closed_out_at"))


def close_file(load_id: str, *, by: str, note: str = "") -> dict:
    """Record the review. **The authoritative closeout operation.**

    Refuses a mission that has not finished -- *"Archive eligibility therefore
    depends upon: Mission completion"* -- and refuses a second review, because
    a closeout that can be overwritten is not a record of who looked.
    """
    load = store.get_load(load_id)
    if not load:
        raise ValueError("Load not found: %s" % load_id)
    if load["status"] not in CLOSEABLE_STATUSES:
        raise ValueError(
            "A file is closed after the mission is finished. This one is %s."
            % str(load["status"]).replace("_", " "))
    if is_closed_out(load):
        raise ValueError("This file was already closed on %s by %s."
                         % (load["closed_out_at"][:16], load["closed_out_by"] or "someone"))
    who = str(by or "").strip()
    if not who:
        raise ValueError("A closeout records who reviewed the file.")
    return store.record_closeout(load_id, at=_utc_now(), by=who,
                                 note=str(note or "").strip())


#: The mission is finished. `completed` is a run that ended with its POD;
#: `delivered` is one that ended without it -- kept archivable by his ruling of
#: 2026-09-16 -- and `cancelled` is a run that ended early and *"is recorded and
#: never deleted."* All three are files that can be reviewed and closed.
CLOSEABLE_STATUSES = ("completed", "delivered", "cancelled")


def queue(loads, records=None) -> list[dict]:
    """Finished missions awaiting Archive, oldest first.

    A queue of what is **waiting on Operations**, so a file cannot go quiet
    between the driver finishing and the Archive retaining it. Already-closed
    files stay listed until they are archived: the review is done, the
    retention is not, and both are visible work.
    """
    records = records or {}
    out = []
    for load in loads or []:
        if str(load.get("status") or "") not in CLOSEABLE_STATUSES:
            continue
        out.append(review(load, records.get(str(load.get("load_id") or ""))))
    out.sort(key=lambda r: (r["closed_out"], r["load_id"]))
    return out
