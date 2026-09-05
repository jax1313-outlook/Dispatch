# CURRENT REALITY VERSUS POSSIBLE FUTURES ARCHITECTURE

> **HOS / ELD boundary (Operational Readiness Mission, Section 1.6).** Dispatch is not an
> ELD and holds no hours-of-service data. There is no ELD, GPS, or telematics integration
> anywhere in the program, and none is configured. Every reference to HOS below describes
> either (a) a value **estimated** from distance and appointment windows, or (b) a
> capability that would require a live trusted external source that does not exist today.
> The driver is responsible for legal HOS compliance. Nothing in this document is a
> readiness claim that Dispatch knows a duty clock. Where an HOS value is displayed, it is
> labeled as an estimate at the surface.


**Document Type:** Core Architecture Specification
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Data Architecture & State Management

---

## 1. Executive Summary

Dispatch operates in two strictly separated operational states:
1. **State 1: Current Reality** — What is true now.
2. **State 2: Possible Futures** — What could become true.

The boundary between Reality and Possibilities is absolute. Mixing or blurring these states creates operational confusion, double-booking, and corrupts single-source-of-truth commitments.

---

## 2. Dual State Model

```
┌─────────────────────────────────────────────────────────────┐
│                    STATE 1: CURRENT REALITY                 │
│  • Current Mission (Executing)                              │
│  • Week View (Capacity Visualization)                       │
│  • Truck / Asset Position (no GPS or HOS feed exists)        │
│  • Commitments (Calendar Events & Rate Confirmations)       │
│  • Active Capacity (Consumed vs Available)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
            COMMIT LOAD ACTION │ (Human Authority Decision)
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                   STATE 2: POSSIBLE FUTURES                 │
│  • Opportunity Cards (Discovered & Scored)                  │
│  • What-if Scenarios                                        │
│  • Hypothetical Capacity Consumption                        │
│  • Projected Revenue / Profitability                        │
│  • Future Position Creation                                 │
│  • Future Weeks Planning                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Core Architectural Rules

1. **Calendar Stores Commitments:**
   - The Calendar model (`dispatch/store.py`, `LoadCalendar`) stores **only** committed, booked, and verified loads.
   - An unbooked or uncommitted opportunity card must **never** appear on the Calendar as a confirmed event.

2. **Opportunity Cards Store Possibilities:**
   - Opportunity Cards (`dispatch/opportunities.py`) hold speculative, discovered, or analyzed market loads.
   - They represent possible future revenue, position creation, and capacity consumption.

3. **Strict Separation:**
   - Reality and Possibilities must remain separate in database persistence, memory stores, API responses, and UI components.
   - A query for active driver status or truck position must reflect **Current Reality** only.
   - Scenario evaluations calculate hypothetical outcomes in memory without mutating **Current Reality**.

4. **Current Mission Supremacy:**
   - Executing mission data (State 1) takes top priority over any speculative evaluation (State 2).
   - `Current Mission > Everything Else`

---

## 4. State Transition Gate

Moving an object from **Possible Futures** (State 2) to **Current Reality** (State 1) requires an explicit **Commit Load** action:

1. **Human Choice Required:** Only the owner/operator (human authority) can initiate the transition from Opportunity Card to Committed Load.
2. **Side Effects of Commitment:**
   - Opportunity Card transitions to `Committed`.
   - A canonical `Load` and `RateConfirmation` are created/linked in State 1.
   - A `Calendar Event` is generated on the canonical calendar.
   - Dynamic Capacity for the affected time window is marked as `Consumed`.
   - The Opportunity Card lifecycle completes and locks.

---

## 5. Subsystem Isolation

- **Driver Portal:** Interacts almost exclusively with **State 1 (Current Reality)**. The driver focuses on execution (Current Mission, Week View, Milestones, POD, Settlement).
- **Intelligence & Scoring Engines:** Produce and refine **State 2 (Possible Futures)** objects. They do not alter State 1 records.
- **Operations Dashboard:** Displays State 1 in the primary cockpit view while presenting State 2 in a dedicated candidate/opportunity workspace.
