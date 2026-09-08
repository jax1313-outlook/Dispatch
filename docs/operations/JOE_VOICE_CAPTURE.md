# Speaking a load into Dispatch

**What this is:** Mike says a board listing out loud; Dispatch records it as an
Opportunity through the seventh contract.

**The code is not in this repository.** JOE is a plug-in and lives in
`D:\Joe Assistant\Assistant_Plugin`, which is the separation §5.4 requires:
Dispatch starts and runs whether or not JOE exists. The operator guide is
`D:\Joe Assistant\Assistant_Plugin\docs\JOE_VOICE_CO_DRIVER_OPERATION.md` and
that is the page to read. This one exists so a builder standing in the Dispatch
repository knows where the other half is, and what Dispatch owes it.

---

## What Dispatch provides

| | |
|---|---|
| The contract | `POST /api/joe/opportunity` — the seventh, ratified 2026-09-06 |
| Identity | **Dispatch mints the `OPP-` id.** JOE holds no store and generates none |
| Deduplication | Dispatch's, in `dispatch/opportunity.py`. A repeat capture merges and fills gaps |
| Rehearsal tagging | Automatic, when the node runs with `DISPATCH_REHEARSAL_SESSION` set |
| Authentication | A bearer token — `DISPATCH_JOE_TOKEN`, in the node's environment |

**JOE reads nothing and writes no operational truth.** An Opportunity is a
*possibility*; §5.2 keeps possibilities and commitments in different places and
the transition between them is one-way, explicit, and nowhere near JOE.

---

## To run it

1. Start Dispatch — `DISPATCH_START_HERE.cmd`.
2. Double-click `JOE_CO_DRIVER.cmd` in `D:\Joe Assistant\Assistant_Plugin`.

It states the microphone, the recognizer, the node and the driver in the locked
vocabulary before it starts, and stops rather than running half-configured.

---

## To test it without touching live data

Open a rehearsal session and start the node inside it. Every capture made in
that session is tagged at creation and marked wherever it is displayed, which is
what the Rehearsal Data doctrine requires.

```bash
cd "D:\Dispatch" && py -3 -c "from dispatch import rehearsal; print(rehearsal.start_session(label='voice capture', actor_id='mike')['session_id'])"
```

Then start Dispatch with `DISPATCH_REHEARSAL_SESSION` set to the id it printed.

---

## What this does not need

**No Microsoft account, tenant, licence, gateway, Copilot Studio work, or Teams
configuration.** The recognizer runs on the node's own CPU and its model is
already on disk, so spoken capture works with no signal at all — which is what
CONOPS v1.1 requires of anything that must survive an intermittent link.

The Microsoft dependencies that do exist belong to Copilot as an optional
*reasoning* provider, and are not on this path. The measurement is in
`D:\MD Files\MICROSOFT_DEPENDENCY_REPORT_2026-09-07.md`.
