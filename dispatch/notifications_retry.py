"""Resending what failed, on an operator's say-so.

`dispatch.delivery` records every attempt and schedules the next one. This is
the sweep that acts on that schedule: it takes the attempts whose backoff has
elapsed, replays them through `dispatch.notifications`, and records the outcome
the same way the original attempt was recorded.

Two deliberate limits.

**It is never automatic.** No thread, no timer inside the portal process. The
launcher, a scheduled task, or the Maintenance button runs it, so a resend is
always an event the operator can point at rather than something the program did
while nobody was looking. A freight email going out twice because two workers
swept the same queue is a worse outcome than one going out late.

**It replays from the load, not from a stored body.** Keeping a serialised
message to resend would mean a broker receiving, hours later, a description of a
state the load has since left. Regenerating it from the record means the resend
says what is true now, and an attempt whose load has since been archived or
cancelled is abandoned rather than sent.
"""

from __future__ import annotations

import logging

from dispatch import delivery, notifications, store
from dispatch.observability import event, get_logger

log = get_logger("dispatch.notifications_retry")

#: attempt kind -> how to rebuild that message from the load as it stands now.
REPLAY: dict[str, str] = {
    "load_dispatched": "notify_dispatched",
    "load_delivered": "notify_delivered",
    "load_exception": "notify_exception",
    "pod_generated": "notify_pod_generated",
    "load_archived": "notify_archived",
    "invoice_created": "notify_invoice_created",
    "payment_received": "notify_payment_received",
    "payment_overdue": "notify_payment_overdue",
    "settlement_disputed": "notify_settlement_disputed",
    "settlement_written_off": "notify_settlement_written_off",
    "load_stalled": "notify_stalled",
}


def _rebuild(attempt: dict):
    """The callable that sends this attempt again, or None if it cannot be."""
    func_name = REPLAY.get(attempt["kind"])
    if not func_name:
        return None
    func = getattr(notifications, func_name, None)
    if func is None:
        return None
    load = store.get_load(attempt["subject_ref"]) if attempt["subject_ref"] else None
    if not load:
        return None

    # Every notify_* takes the load first. The ones that also take a record take
    # it for its identifiers, and the load carries enough to name itself; a
    # resend that cannot be rebuilt faithfully is abandoned rather than guessed.
    try:
        import inspect

        arity = len(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        arity = 1
    if arity != 1:
        return None
    return lambda: func(load)


def run_due(*, limit: int = 50, now=None) -> dict:
    """Retry everything whose backoff has elapsed. Returns what happened.

    `now` is injected for the same reason `authcounters` injects it: a backoff
    test that has to sleep four hours to prove the fourth retry is a test nobody
    runs.
    """
    due = delivery.retry_due(limit=limit, now=now)
    sent = failed = abandoned = 0

    for attempt in due:
        send = _rebuild(attempt)
        if send is None:
            delivery.mark_failed(
                attempt["attempt_id"],
                "cannot be rebuilt: the load is gone, or this message is not "
                "one that can be regenerated from the record",
                now=now,
            )
            abandoned += 1
            continue
        try:
            receipt = send()
        except Exception as exc:  # noqa: BLE001
            delivery.mark_failed(attempt["attempt_id"], f"{type(exc).__name__}: {exc}", now=now)
            failed += 1
            continue
        text = "" if receipt is None else str(receipt)
        if text.startswith("not sent"):
            delivery.mark_simulated(attempt["attempt_id"], receipt=text, now=now)
        else:
            delivery.mark_sent(attempt["attempt_id"], receipt=text, now=now)
        sent += 1

    event(
        log, logging.INFO, "retry sweep",
        attempted=len(due), sent=sent, failed=failed, abandoned=abandoned,
    )
    return {"attempted": len(due), "sent": sent, "failed": failed, "abandoned": abandoned}
