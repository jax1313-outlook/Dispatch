# DISPATCH EXTERNAL ADAPTER BOUNDARIES

Status: DOCTRINE. No runtime behaviour is changed by this document.

---

## 1. What an adapter is

An adapter is the only place in Dispatch that knows a specific external system exists.
Everything inside the boundary works in Dispatch's own vocabulary.

**Test of a correct boundary:** the external system can be replaced entirely without
editing evaluation, state or storage code. If swapping the load board means touching
scoring, the boundary is in the wrong place.

## 2. The adapter contract

Every adapter, without exception, returns one of three outcomes:

| Outcome | Meaning |
|---|---|
| `DATA` | Reached the source. Here is what it said, with provenance and retrieval time. |
| `UNAVAILABLE` | Could not reach the source, or the source failed. **Not "no results".** |
| `EMPTY` | Reached the source. It genuinely returned nothing. |

And obeys four rules:

1. **Never fabricates.** No sample data, no cached-presented-as-live, no invented defaults.
2. **Never decides.** An adapter supplies facts. It does not set a state, cross a gate or
   authorise anything.
3. **Never blocks the chassis.** A slow or dead external system degrades one part of the
   screen, not the product.
4. **Always attributes.** Every fact it returns names its source and when it was retrieved.

Rule 1 exists because the lineage broke it. v1.0.1's `sample_opportunities` fabricated
opportunities when the SAM connector failed — against its own constitution. See
`DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md` §4.

## 3. The boundaries

### Opportunity sources — SAM.gov, load boards

- Inbound only. Dispatch reads; it does not post, bid or respond.
- Source records are preserved as received. Broker load numbers are kept **exactly**.
- Duplicate protection at the boundary: the same opportunity seen twice is one record.
  (Recovered from GOLD.)
- Rate limits and quotas are the adapter's problem, not the chassis's.

### Mail — Outlook

- **Read is separate from write, and write does not exist yet.**
- The current JOE Outlook adapter is read-only and asserts it (`_assert_read_only()`).
  No draft, write, move, delete, reply, forward, attachment-save or send capability.
- Any future transmission passes through the human-in-the-loop seam, not through this
  boundary. Approved mailboxes: `ops@l1truck.com`, `Admin@l1truck.com`.
- Moving unwanted mail to Junk or Deleted Items is reversible and permitted. Permanent
  purge and automatic emptying are not authorised.

### Reasoning — JOE

- JOE **describes**. It does not compute the score, set a state or cross a gate.
- If JOE is unavailable, records display without narrative. **No field goes blank and no
  number changes.** The chassis produced those numbers; JOE only spoke about them.
- JOE's eight permitted functions and its authority limits are governed by JOE's own
  doctrine and are not extended by anything in Dispatch.

### Distance and geography

- Currently a 22-pair lookup table in `dispatch/scoring.py`.
- Falls back to the tiered territory model, then to `UNKNOWN` — never to a guessed
  mileage. A fabricated distance becomes a fabricated rate-per-mile, which becomes a
  fabricated recommendation.

### Publisher

- Produces artifacts — briefs, workspaces, documents — from records that already exist.
- Never originates a record and never sends anything.
- Recovered from GOLD, which is the only build that has it.

## 4. Credentials

**CONFIRMED, open item.** Every L1-COS build carries a live 40-character SAM.gov API key
in both `.env` and `.env.example`; v1.1 carries a third copy in `.env.txt`.

Rules for Dispatch:

1. Credentials live in `.env`, which is git-ignored. Never in `.env.example`.
2. `.env.example` carries key **names** and empty values only.
3. An adapter with no credential reports `UNAVAILABLE` — it does not fall back to sample
   data.
4. No credential is printed, logged, or written into an artifact.

## 5. Boundary review checklist

Before any adapter merges:

- [ ] Distinguishes `UNAVAILABLE` from `EMPTY`
- [ ] Cannot fabricate under any failure path
- [ ] Cannot set state or cross a gate
- [ ] Attributes every fact with source and retrieval time
- [ ] Failure is visible to the operator in plain language
- [ ] Chassis still runs with the adapter removed entirely
- [ ] No credential in code, log, artifact or example file
