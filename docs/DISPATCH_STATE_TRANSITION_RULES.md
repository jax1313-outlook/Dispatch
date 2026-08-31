# DISPATCH STATE TRANSITION RULES

Status: DOCTRINE. Describes rules that current code already partly implements. No runtime
behaviour is changed by this document.

---

## 1. One record, one identity

The Mission Record is created once and enriched for the rest of its life. It is never
copied into a second record, and it never changes identity.

**CONFIRMED in code.** `dispatch/mission.py` and `portal/models/sandbox.py` implement
this: `accept_load()` commits the existing opportunity in place, and `mark_accepted()`
sets `engine_load_id = sandbox_id` — the record points at itself.

Two numbers, two owners, both permanent:

```
Mission 1847     <- ours     (internal, numeric, 4 digits max)
Load 847261      <- theirs   (the broker's, preserved exactly)
```

## 2. Purpose changes; identity does not

```
PURPOSE_OPPORTUNITY  ->  PURPOSE_MISSION
```

The transition is one-way and happens exactly once, at ACCEPT LOAD. Nothing else in the
record's identity changes at that moment.

## 3. Three activation events

| Event | Creates | Reversible |
|---|---|---|
| **START SWEEP** | Opportunities | Yes — an opportunity may be discarded |
| **ACCEPT LOAD** | An allocation — a commitment to a broker | No — a promise was made |
| **LOCK DAY** | The locked sequence, and the calendar | Yes, by exception |

These are the only three events that bring something into existence. Everything else is
enrichment of what already exists. LOCK DAY is detailed in §5.

## 4. Atomic human gates

Recovered from GOLD, which was the first build to separate looking from committing.

| Gate | Meaning | Produces | Commits the operator |
|---|---|---|---|
| **Interested** | I am looking at this | Brief | No |
| **Pursue** | I am committing to this | Workspace | Yes |

Rules:

1. **A gate is crossed by a human, never by the engine.** A recommendation of `PURSUE` does
   not set `pursue`.
2. **A gate is atomic.** It either fully happens — flag set, artifact created, record
   updated — or it does not happen. No half-crossed gate.
3. **Interest is free.** Marking interest costs nothing and commits nothing. If it costs
   something, the operator stops marking it and the system loses the signal.
4. **Crossing is recorded** with who and when. See
   `DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md`.

## 5. Run phases

**CONFIRMED in code.** `dispatch/mission.py` splits the run on the axis of whether the
freight is loaded.

```
PICKUP    created, dispatched, en_route_pickup, at_pickup
DELIVERY  picked_up, in_transit, at_delivery, delivered, completed, archived
```

`in_transit` is the hinge and belongs to DELIVERY: once loaded, the only question that
matters is where it has to be.

### The Capacity Plan carries the day; the Mission Record carries the promise

**The van's capacity may be shared across several brokers** — the LTL and courier model,
and the normal case. Ownership fragments; execution does not.

Governed by `DISPATCH_CAPACITY_PLAN_DOCTRINE.md`:

```
Capacity Plan   vehicle day, stop sequence, capacity allocation,
                route sequence, remaining capacity
      ▲
      │  Mission Records attach to Capacity Plans.
      │  Capacity Plans do not replace Mission Records.
      │
Mission Record  the commitment - per broker, may span multiple days
```

**Everything in this document holds unchanged.** One record, one identity, progressively
enriched, never copied, dual numbering intact. The Capacity Plan does not replace the
Mission Record — it schedules it.

- **The driver sees one Capacity Plan**: one day, one route, one vehicle.
- **Each stakeholder sees only their own Mission** — their load number, documents, proof,
  tracking and status. No broker sees another's freight.
- **A Mission Record may span days.** Pickup Tuesday, delivery Thursday is a valid Mission
  lifecycle, and is why the commitment could not live inside a single day's plan.
- **Capacity binds at the Capacity Plan.** Two pallets are never over capacity alone, only
  against what the day already holds.
- **Every day starts and ends at home base.** Overnight stays are avoided as a matter of
  business model.

### LOCK DAY — a third activation event

| Event | Creates | Reversible |
|---|---|---|
| START SWEEP | Opportunities | Yes |
| ACCEPT LOAD | An allocation — a commitment to a broker | **No** |
| **LOCK DAY** | **The locked sequence, and the calendar** | Yes, by exception |

The sequence is proposed **when the day closes on capacity**, not before — routing a
half-full day wastes attention on a plan the next load will change.

**The engine reasons the sequence. The human locks it.** The calendar is an artifact of the
human's lock, never of the engine's proposal.

**The day is usually closed by powering down** at final arrival — the driver's physical act,
not a button to remember. JOE serves as dialog assistant until then and **may propose** a
close; it may never perform one.

**A power-down is not always the end of a day** — fuel, breaks and docks all power down.
The rule is asymmetric because the costs are: a close proposed late costs one prompt; a
close applied early ends the day with commitments outstanding. So **never close while any
commitment is outstanding**, ask when all stops are done but the van is away from home, and
**stay silent at an ordinary stop** — a system that asks at every fuel stop is one the
driver learns to dismiss.

**Locking records the approved execution plan. It does not create an immutable schedule.**
A materially better opportunity may justify reopening it — Dispatch proposes, the operator
authorizes. See the BOOK IT DANO rule in `DISPATCH_CAPACITY_PLAN_DOCTRINE.md` §4.

**Reopening returns the day to PROPOSED**, and the sequence is re-reasoned from current
facts rather than carried forward — what changed while the day was locked is unknowable.
The previous sequence is kept as history, never as a default.

**A high score is never authority to change the plan.** Only human authority reopens a day,
approves a revised plan, and authorizes the resulting changes.

### Multi-stop breaks the two-phase assumption — RECOMMENDATION

**This model assumes one pickup and one delivery.** A milk run —
pickup → pickup → delivery → pickup → delivery — has no single pickup phase and crosses
back and forth between them.

The minimal change that preserves the doctrine: **phase becomes a property of the current
stop, not of the run.**

```
phase = phase_for(current_stop.stop_type)
```

CURRENT still resolves and never becomes a stored third state. `filter_bundle()` still
reveals rather than deletes. Only the input to `phase_for()` changes — from run status to
stop type.

**Settled by the operator, 30 August 2026.** An allocation completes when its own stops are
done — so a broker may be invoiced before the driver's day ends; the record completes when
every stop is done. Resequencing is initiated by the driver, arranged by JOE presenting
alternatives, and decided by the human. Dropping a stop breaks a commitment only if that
allocation was accepted. See `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` §8.

## 6. CURRENT is resolved, never stored

**CONFIRMED in code.** `resolve_view()` derives CURRENT from the record's status. There is
no third branch and no third data set.

```
One Mission Record, many views.
CURRENT resolves to PICKUP or DELIVERY. It is never a state of its own.
```

`filter_bundle()` **reveals**; it never deletes and performs no I/O. A view is a way of
looking at the record, not a subset stored on disk.

## 7. Evidence belongs to the end of the run that produced it

```
PICKUP    bol, photo, screenshot
DELIVERY  pod, photo, document
```

Evidence is append-only. A BOL captured at pickup is not replaced by a POD at delivery —
both belong to the same record, at different points in its life.

## 8. Transitions that must never happen

| Forbidden | Why |
|---|---|
| Engine advances a state | The engine recommends; the human decides |
| Adapter advances a state | Adapters supply facts, not authority |
| A second record for the same load | One record, one identity |
| Backwards through ACCEPT LOAD | The commitment was real |
| Silent rescoring of a decided record | Destroys the explanation of a past decision |
| A view becoming a state | CURRENT is resolved, not stored |

## 9. Decision vocabulary — recovery, not yet final

**Recovered from v1.3.1**, where it was enforced:

```python
allowed = {"Pursue", "Monitor", "Decline", "Defer", "Undecided"}
if decision not in allowed:
    raise ValueError("Invalid decision")
```

Default `Undecided`. Validation on write. An unrecognised decision is an error, not a
silent pass-through.

**RECOMMENDATION — not final.** These five map onto Dispatch as follows. State names are
deliberately not being fixed here; the mission brief asks for evaluation, not
finalisation.

| L1-COS | Dispatch reading | Note |
|---|---|---|
| Undecided | Default on every new opportunity | Must remain the default |
| Monitor | Interested, no artifact yet | Close to GOLD's `interested` |
| Defer | Not now — revisit at a stated time | Needs a date, or it becomes Decline |
| Decline | Not this one | Should record a reason for pattern learning |
| Pursue | Committing | Maps to GOLD's `pursue` and to ACCEPT LOAD |

**Open question for Mike.** `Monitor` and `Defer` are genuinely different — one is *watch
this*, the other is *ask me later*. Carrying both costs a screen control and some
cognitive load. Carrying only one loses a distinction that v1.0.1 thought worth keeping.
This is a Driver First judgement, not an architectural one.
