# Are alerts detected, generated, delivered, and tracked?

- Opened: 2026-09-09, by Mike, during the Home walk
- Status: OPEN
- Raised by: the premise that the red alerts on screen should already have been
  sent to `ops@l1truck.com`, and therefore that the screen is reporting a past
  alert rather than acting as an alert center

## Short answer

No alert has ever been sent to `ops@l1truck.com`.

One alert artifact exists on this machine. It was written to a file, not sent.
It is addressed to a placeholder. It was produced on 2026-09-06 for a demo load.

The premise needs correcting before it can be built on. Alerting has not already
happened, so the screen cannot be treated as a report of a completed alert.

## 1. Alert detection

**Proven by repository evidence.**

`check_stalled_loads` in `dispatch/services.py` compares each load's time in
status against a threshold. It runs on every render of the Dispatch tab.

Two independent pieces of evidence. The code path was read. And the Home screen
on 2026-09-09 displayed a count of two stalled loads, which is a live run
producing a real number from real data.

Detection is the one category that is not in doubt.

Not examined yet: whether the Exceptions tab detects on the same basis. That is
tab 01 scope and is not covered by this note.

## 2. Alert generation

**Stalled alerts: proven by repository evidence, once, manually.**

**The other ten notification types: implemented but unverified.**

`dispatch/notifications.py` defines eleven notification builders. Each composes
a subject, a plain-text body and an HTML body, then hands the message to the
shared transport in `cin_lite/email_delivery.py`.

Ten of them fire automatically from inside the service layer, after the database
write they report on has committed. Dispatched, exception, delivered, POD
generated, archived, invoice created, payment received, payment overdue,
settlement disputed and settlement written off.

The eleventh, stalled, does not fire automatically. Its only non-test caller is
the POST endpoint behind the Send Stall Alerts button. There is no scheduler, no
cron entry and no timed job anywhere in the repository that calls it.

The runtime evidence is one file:

```
D:\Archive\CIN\Outbox\dispatch-stalled-SBX-DISPATCH-E2E-DEMO-001.eml
6054 bytes, written 2026-09-06
Subject: [DISPATCH] STALLED — Southeast Freight Partners (195h in at_delivery)
```

All eleven types write into that same outbox, named per load, so an artifact
would exist for each one that had run. Exactly one exists. That is the whole
notification history of this machine, and it is a demo load.

## 3. Alert delivery

**Missing.**

The transport sends by SMTP only when `DISPATCH_SMTP_HOST` is set in the
environment. When it is not set, it writes the message to the outbox and returns
the string `not sent (SMTP not configured); written to ...`.

There is no `.env` file in the working copy. The only Dispatch variable present
in the environment is the email HMAC secret. No SMTP host, port, user or
password is configured.

The one artifact carries placeholder addressing, which is what the defaults
produce when nothing is configured:

```
From: dispatch@dispatch.local
To:   reviewer@dispatch.local
```

`ops@l1truck.com` appears exactly once in the entire repository, in
`docs/DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md`, named as an approved mailbox. It
is not configured as a recipient anywhere in the code. Nothing routes to it.

So the address in the premise is **assumed by doctrine**, and delivery to it is
**missing**.

## 4. Alert tracking

**Missing.**

The transport returns a string saying what happened, sent or not sent and where.
That string is the only record of the outcome, and it is discarded. The wrapper
that calls every notification runs the call inside a try block and keeps no
return value, by design, so that a mail failure cannot turn a completed database
write into a false error.

There is no notification table, no alert table and no audit row. Nothing in the
schema records that an alert was raised, attempted or delivered.

The stalled notify endpoint returns a field named `notified`. It is the count of
loads found stalled, not the count of alerts delivered. On a machine with no
SMTP configured it will report a positive number while delivering nothing. That
is worth raising as a defect on tab 01.

## Summary

| Category | Class |
| --- | --- |
| Detection | Proven by repository evidence |
| Generation, stalled | Proven by repository evidence — once, manually, demo load |
| Generation, other ten types | Implemented but unverified |
| Delivery | Missing |
| Delivery to `ops@l1truck.com` | Assumed by doctrine |
| Tracking | Missing |

## What this changes

The screen is not reporting an alert that already went out. Until delivery and
tracking exist, no screen can honestly claim an alert was sent, and no build
item should assume upstream alerting as a precondition.

Three questions for Mike, in order:

1. Should alerts be delivered by SMTP from the truck, given that the laptop is
   the server and may be offline? A written outbox may be the correct design
   rather than a failure, in which case delivery is not missing, it is deferred,
   and something has to drain that outbox.
2. Should stalled alerts fire automatically, or stay on a button? Right now
   they are the only one of the eleven that a human has to press.
3. What has to be recorded, and where, for an alert to count as tracked?

## Answer

Not yet answered.
