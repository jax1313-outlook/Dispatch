# M3_ROUTE_RISK_DURABILITY_WALKTHROUGH_REPORT_v1

## Route Risk Durability

**Status:** Implemented and verified. Branch: `claude/dispatch-repo-context-reconcile-7mblbb`.

**Mission:** M3 of `DISPATCH_BUILD_MATRIX_v1` (Level 1 — defect).

**Closes:** B-19 in `DISPATCH_REPO_RECONCILIATION_PLAN_v1`.

---

## The defect

Route Risk events lived only in `route_risk/engine.py:15`, a module-level dictionary — while a
fully formed `route_risk_events` table sat in the SQLite schema (`dispatch/db.py:343`) and was
**never written to**. Restarting the process destroyed every recorded condition, and the Driver
Portal (`portal/routes/driver_portal.py:120`) then displayed *"Route Risk is not yet available. No
active Route Risk events recorded"* — presenting a fact about the road that was actually an
artifact of a restart.

This was the single reason the protected-state map in the reconciliation could not be completed.
Route Risk events were **not protected** (a restart destroyed them), **not derived** (nothing could
rebuild them), and **not disposable** (a surface read them). The reset doctrine's own falsifiable
test — *"if Dispatch cannot survive a shutdown and startup cycle, the architecture should be
reviewed"* — had exactly one true failure in the repository, and this was it.

## What changed

1. **`dispatch/db.py`** — `route_risk_events` gains `has_map_visual INTEGER NOT NULL DEFAULT 1`,
   in `_SCHEMA` for new databases and as a guarded idempotent `ALTER TABLE` in `_apply_migrations()`
   for existing ones. This is the repository's own established migration mechanism, introduced in
   Phase 5 for exactly this situation. Also adds `idx_route_risk_load`.
2. **`dispatch/store.py`** — `create_route_risk_event()`, `get_route_risk_event()`,
   `list_route_risk_events()`, plus `_route_risk_row_to_event()`.
3. **`route_risk/engine.py`** — optional `store_fn` on the write path and `load_events_fn` on the
   two read paths. Persistence is **injected, never imported** — the same decoupling contract this
   module already used for `comi_eval_fn`. With nothing injected the engine behaves exactly as
   before, in memory.
4. **`dispatch/route_risk.py`** — injects the SQLite store into all three engine calls.

## Design decisions, stated as assumptions (BM-08)

**1. No dual write.** When a store is injected, the event goes to the store and is *not* also kept
in the module dict. Two copies of an operational record would be two sources of truth. As a
consequence `dispatch.route_risk._ROUTE_RISK_EVENTS` is now always empty in normal Dispatch use;
the name stays bound for backwards compatibility and is documented as such.

**2. `has_map_visual` is stored, not reconstructed.** It is `True` at every call site in the
codebase today, so assuming `True` on read would have looked correct indefinitely — which is
precisely why it would have been wrong. A durability fix that quietly reconstructs a field is not a
durability fix. Two fields *are* reconstructed, because they are strictly derived and storing them
would create the disagreement this mission exists to prevent:

- `map_visual_placeholder` — rebuilt from `has_map_visual` + corridor/area, exactly as the engine
  builds it.
- `is_live_data` — always `False`. No live feed is connected; a stored copy could one day disagree
  with reality.

Round-trip equality is asserted directly: `test_stored_event_equals_the_recorded_event`.

**3. Adding a column was judged in-scope; adding a table would not have been.** The build matrix
excluded "adding a table (the table exists)". One column via the documented idempotent migration is
the minimum needed for exact fidelity. If Mike reads this as scope creep, the alternative is to drop
`has_map_visual` fidelity, and that should be an explicit choice rather than a silent one.

## Explicitly out of scope

No external feeds. No change to consequence thresholds or COMI evaluation — those belong to the
Route Risk context, which is **unwritten doctrine (B-09)**. No automatic notification. No decision
about whether Route Risk collects its own feeds or receives them from Intelligence (G-10) — that is
Mike's, and nothing here presumes an answer.

## Pre-existing ambiguity found, deliberately not resolved

`created_at` has second precision, and `get_route_risk()` picks the latest via
`max(events, key=created_at)`. Two events recorded in the same second **tie**, and the tie is
resolved by list order. This tied in the in-memory store too — it is not introduced here. Picking a
tiebreak rule would be a behavior change outside a durability mission, so it is recorded rather than
fixed, and the affected test forces timestamps apart deliberately rather than asserting something
vague. Flagged for the Route Risk context work.

## Automated test results

Full suite: `python -m pytest` — **2771 passed**. 20 new tests in
`tests/test_route_risk_durability.py`: survival across a module reload, the event being in the
database rather than module memory, no dual write, exact round-trip equality, every engine field
surviving, the placeholder reconstructed exactly, `has_map_visual=False` not silently becoming
`True`, booleans returning as booleans rather than SQLite ints, latest-event and ordering with
timestamps forced apart, per-load scoping, COMI flags still driven by the real evaluator (level 0
silent, driver alerted from level 1, stakeholder + publisher from level 3), the engine remaining
free of any `dispatch` import, the engine still using memory with nothing injected, and the
migration staying a harmless no-op when re-run.

One test asserts by source inspection that `route_risk/engine.py` contains no `import dispatch` —
a structural guard, following the precedent already set in `tests/test_ifta_report_approvals.py:204`.

## Live walkthrough — a real process restart

The suite proves survival with a module reload. This is the stronger claim: two separate
interpreters against one database file.

```
--- PROCESS 1 ---
P1 recorded: rr-feee460d4d | Level 4
    (I-95 blizzard closure, consequence 4, 180 min delay, corridor I-95 N)
<process exits -- all module state destroyed>

--- PROCESS 2, brand new interpreter ---
P2 engine in-memory dict : {}                        <- nothing in memory
P2 available             : True                      <- was False before M3
P2 summary               : I-95 blizzard closure
P2 consequence_level     : 4
P2 delay_minutes         : 180
P2 driver alert required : True
P2 map placeholder label : Corridor Map Placeholder: I-95 N
```

Before M3, process 2 printed `available: False` and the "no active Route Risk events" message.

## Effect on the protected-state map

Route Risk events move from **unclassifiable** to **authoritative and protected**, stored in the
same SQLite database as loads, milestones and evidence, under the same WAL journal and the same
foreign-key enforcement. The protected set drafted in the reconciliation can now be completed —
which was the stated precondition for any reset work.

## Boundaries observed

No layer created or named; this writes to a table that already existed. The standalone engine stays
standalone — persistence injected, not imported — so `route_risk/` remains independently usable, and
a structural test enforces it. Manager untouched. No calendar. No judgment added: thresholds are
unchanged and no component chooses anything.
