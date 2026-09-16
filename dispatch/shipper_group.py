"""One card per delivery, and the only thing that binds two of them.

**Owner's model, 2026-09-15.** Three pallets, one customer, three car
dealerships:

    "a customer has 3 pallets for it's own customers at three different car
     dealerships. Each pallet goes to a different location across many miles.
     each mission which becomes a load card at commit list the delivery. Top
     right corner is 1 of 3, 2 of 3, 3 of 3. the customer is the same but each
     delivery is a different location and a different Bill of Lading. because
     the consignee is different. all three signed Bill of Lading is returned to
     the shipper as POD."

Why they cannot be stops on one mission, in his words:

    "rain stops one stop from completing so the driver returns with one load
     still onboard. This is why each must stand alone totally. the only binding
     item is the shipper. Everything thing else stands alone. to the driver he
     really does not care how many stops come from one shipper. He only cares
     about the completed delivery and the return of all documents."

    "Nothing about it binds them together. this is why i created the card system
     in the first place and used deterministic algorythm to process. they are
     event activated. button, click, voice, email. One card pre load mission."

    "2 out of three get paid that day."

    "The '1 of 3' label on each card that is enough! not more!"

**So this module is a label and nothing else.** It holds no status, no money, no
workflow and no cascade. Committing, delivering, invoicing, re-appointing or
discarding one card does not read, write or touch another. Every card carries its
own Load Number -- *"YES!!! EITHER FROM THE SHIPPER OR WE CREATE IT"* -- its own
mission number, its own BOL, its own signed POD and its own invoice.

A card that belongs to no group shows no label at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

#: The tag itself: the first card's Load Number. A plain string on the record,
#: deliberately not a table, a parent id or a foreign key -- those are the shapes
#: that grow a cascade later.
KEY = "shipper_group"

#: When this card joined the group. Order, and nothing more. A load number is
#: drawn at random (`dispatch/load_number.py`), so it cannot put three cards in
#: the order they were opened; `created_at` is only accurate to the second, and
#: three cards for one shipper are opened in one sitting.
JOINED_KEY = "shipper_group_at"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tag_of(record: dict) -> str:
    """The group this card belongs to, or "" when it stands alone."""
    return str((record or {}).get(KEY) or "").strip()


def tag_for(source: dict) -> str:
    """The tag a second delivery for this shipper joins.

    The source card's tag if it already has one, otherwise its own Load Number --
    so the first card names the group, and a third card joins the same group as
    the second rather than starting one of its own.
    """
    source = source or {}
    existing = tag_of(source)
    if existing:
        return existing
    return str(source.get("load_number")
               or (source.get("card_data") or {}).get("load_id") or "").strip()


def label(number, total) -> str:
    """"1 of 3". Empty when there is nothing to count.

    *"The '1 of 3' label on each card that is enough! not more!"*
    """
    try:
        number, total = int(number), int(total)
    except (TypeError, ValueError):
        return ""
    if total <= 1:
        return ""
    return f"{number} of {total}"


def members(records, tag: str) -> list:
    """Every card in this group, in the order they were opened. **Read only.**

    `records` is the store as it is held -- a mapping of id to record, or any
    iterable of records.
    """
    tag = str(tag or "").strip()
    if not tag:
        return []
    values = records.values() if hasattr(records, "values") else (records or [])
    found = [r for r in values if isinstance(r, dict) and tag_of(r) == tag]
    return sorted(found, key=lambda r: (str(r.get(JOINED_KEY) or ""),
                                        str(r.get("created_at") or ""),
                                        str(r.get("id") or "")))


def position(record: dict, records) -> dict:
    """Where this card sits in its group, and what the corner reads.

    `{"tag": "", "number": 0, "total": 0, "label": ""}` for a card with no group
    -- and for one whose group has no other member, because "1 of 1" is a label
    that answers a question nobody asked.
    """
    tag = tag_of(record)
    empty = {"tag": "", "number": 0, "total": 0, "label": ""}
    if not tag:
        return empty
    listed = members(records, tag)
    ids = [str(r.get("id") or "") for r in listed]
    try:
        number = ids.index(str((record or {}).get("id") or "")) + 1
    except ValueError:
        return empty
    return {"tag": tag, "number": number, "total": len(listed),
            "label": label(number, len(listed))}
