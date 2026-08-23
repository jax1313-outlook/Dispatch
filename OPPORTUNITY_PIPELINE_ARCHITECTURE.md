# OPPORTUNITY PIPELINE ARCHITECTURE

**Document Type:** Core Pipeline Architecture
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Opportunity Intake, Filtering, Scoring, & Commitment (`dispatch/opportunities.py`)

---

## 1. Executive Summary

The Opportunity Processing Pipeline handles high-volume opportunity intake (assuming abundance: 50, 100, 200+ opportunities) and translates raw market intelligence into structured, actionable **Possible Futures** for owner/operator decision-making.

---

## 2. Pipeline Workflow

```
INTELLIGENCE
  (collects raw market opportunities: SAM.gov, load boards, broker feeds)
  ↓
ANALYSIS
  (adds operational context: deadhead, HOS impact, fuel cost, route risk)
  ↓
SCORE
  (reduces noise & sorts attention; DOES NOT DECIDE)
  ↓
FILTERS / SORT
  (shapes candidate pool according to operator preferences & capacity constraints)
  ↓
OPPORTUNITY CARDS
  (represents possible futures with revenue, position creation, & margin details)
  ↓
OWNER / OPERATOR JUDGMENT
  (human evaluates options and chooses a future; Human Authority D10)
  ↓
COMMIT LOAD
  (human action converts card from State 2 Possibility to State 1 Reality)
  ↓
CALENDAR
  (stores confirmed commitment on single source of truth calendar)
```

---

## 3. High-Volume Intake & Abundance Assumptions

- The architecture assumes **opportunity abundance**, never single-opportunity processing.
- Pipeline processors batch, analyze, and score opportunities asynchronously or in bulk.
- Pipeline throughput handles 200+ candidates without UI lag or blocking execution of the Current Mission.

---

## 4. Opportunity Card Formal Lifecycle

An Opportunity Card moves through a formal 9-stage lifecycle state machine:

```
1. Discovered     --> Raw intelligence collected
2. Analyzed       --> Operational context added (deadhead, HOS, fuel)
3. Scored         --> Noise reduction score calculated
4. Filtered       --> Applied user criteria (min rate, origin radius)
5. Presented      --> Displayed to owner/operator in UI
6. Selected       --> Operator highlights candidate for detailed comparison
7. Committed      --> Operator confirms booking (Commit Load action)
8. Calendar Event --> Commitment recorded on canonical calendar
9. Current Reality--> Converted into active dispatch Load object
```

### Transition Rule
The transition from `Presented` / `Selected` to `Committed` is a **one-way non-reversible gate** that can ONLY be triggered by explicit human choice.

---

## 5. Architectural Rule: Score Does Not Decide

- **Core Rule:** `Score reduces noise. Humans decide.`
- The score (0–100) serves to rank and highlight high-efficiency opportunities.
- The score **NEVER** auto-books, auto-rejects, or auto-commits any load.
- No software agent or algorithm holds authority to commit capital or asset capacity.
