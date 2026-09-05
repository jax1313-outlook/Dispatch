# DISPATCH SYSTEM INDEPENDENCE DOCTRINE

Status: DOCTRINE. No runtime behaviour is changed by this document.

---

## 1. The principle

**Dispatch remains operable when every external system is down.**

Not degraded into uselessness. Operable. The truck still moves, the record still updates,
the human still decides. External systems make Dispatch *better informed*. They do not
make it *work*.

## 2. What Dispatch owns and never delegates

| Owned by Dispatch | Consequence |
|---|---|
| The Mission Record | No external system holds the authoritative copy |
| Mission numbering | Numbers are ours; broker load numbers are theirs, preserved exactly |
| State transitions | No adapter may advance a state |
| Policy profile | Lives in Dispatch config, not in a vendor account |
| Decision history | Who authorised what, when — stored locally |
| Evaluation | Filter, score, sort, recommend all run locally with no network |

## 3. What Dispatch borrows

| Borrowed | From | If unavailable |
|---|---|---|
| Opportunity feed | SAM.gov, load boards | Sweep reports UNAVAILABLE. Existing records unaffected. |
| Mail | Outlook | Communication marked unavailable. Nothing drafted or claimed sent. |
| Reasoning / language | JOE | Records display without narrative. No field goes blank. |
| Distance, geocoding | lookup tables, future services | Falls back to tiered territory model, then UNKNOWN. |

## 4. The UNAVAILABLE contract

Every adapter must be able to say three things and no others:

1. **Here is the data** — with provenance. See `DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md`.
2. **UNAVAILABLE** — I could not reach the source. This is not "no results".
3. **EMPTY** — I reached the source and it genuinely returned nothing.

**UNAVAILABLE and EMPTY must never be conflated.** A sweep that cannot reach SAM.gov and a
sweep that reaches SAM.gov and finds nothing look identical to the operator unless the
adapter distinguishes them — and one of those two means "go look yourself".

An adapter may not substitute sample, cached-as-if-live, or invented data for either.

### Precedent: the v1.0.1 fallback

v1.0.1 shipped with `sample_opportunities` — a fabrication path that produced plausible
opportunities when the SAM connector failed. Its own Master Constitution forbade exactly
that. The code and the doctrine disagreed.

v1.1 removed it. The build folder named `v1_3_1_no_fallback` is named for a fix that had
already happened two builds earlier.

**CONFIRMED:** `sample_opportunities` appears 3 times in v1.0.1 `app.py`, and 0 times in
v1.1, v1.3, v1.3.1, v1.3.3 and GOLD.

## 5. Degraded mode is a designed state, not an accident

Dispatch must have a defined answer to each of these, visible to the operator:

- No internet
- No SAM.gov / no load board
- No Outlook
- No JOE
- No prior data (fresh install)
- Corrupt or partial record

In every case: **say what is unavailable, keep working on what remains, change nothing
silently.**

## 6. Replaceable adapters

Any external system may be swapped for another without touching the chassis. The load
board, the mail transport, the reasoning provider and the opportunity source all sit
behind boundaries. If replacing one requires editing evaluation logic, the boundary is in
the wrong place.

See `DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md`.

## 7. Driver First

The operator is a single owner-operator driving the truck. Independence is not an
architectural preference here — it is the difference between a tool that works at a truck
stop on a bad signal and one that does not.

Consequences that follow from Driver First and are binding:

- Local-first. Works offline.
- No mandatory account, subscription or vendor login to see your own loads.
- Nothing blocks on a network call that could have been avoided.
- Reduced cognitive load: fewer things shown, not more.
