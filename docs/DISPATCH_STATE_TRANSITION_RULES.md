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

## 3. Two activation events

| Event | Creates | Reversible |
|---|---|---|
| **START SWEEP** | Opportunities | Yes — an opportunity may be discarded |
| **ACCEPT LOAD** | The Mission | No — a commitment was made to a broker |

These are the only two events that bring something into existence. Everything else is
enrichment of what already exists.

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

### The Run carries the Mission — CONFIRMED requirement

**The van's capacity may be shared across several brokers.** Six pallets can be one
broker's whole vehicle, or three brokers at two pallets each — the LTL and courier model,
and the normal case.

This requires a level above the Mission Record, because dual numbering has no answer when
three brokers are aboard:

| | **Mission** | **Run** |
|---|---|---|
| Is | a commitment to a broker | a plan for the vehicle |
| Identity | mission number + their load number | run id + date + vehicle |
| Changeable | no — a promise was made | **yes, freely, until executed** |
| Completes | when *its* stops are done | when *all* stops are done |

**Nothing in this document changes.** One record, one identity, dual numbering, progressive
enrichment and ACCEPT LOAD as the irreversible gate all hold exactly as written. The Run
does not replace the Mission — it **schedules** it, and it owns the stop order, the
vehicle and the day.

Two consequences worth stating here:

- **Capacity binds at the Run.** A two-pallet Mission is never over capacity by itself. It
  is over capacity *on a particular run*. The real question is not "does this fit the van"
  but **"does this still fit Tuesday"**.
- **Resequencing is not an override.** Stop order was never promised to anyone; time
  windows were. Any sequence honouring every Mission's window and the vehicle's capacity is
  permitted, and needs no override because nothing is being overridden.

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

Not settled here, because they are commitment questions rather than data questions: whether
a multi-stop load completes per stop or at the last stop, whether stops may be resequenced
or dropped after ACCEPT LOAD, and whether dropping a `filler` stop breaks the commitment to
the broker. See `DISPATCH_LOAD_ARRANGEMENT_SPEC.md` §8.

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
