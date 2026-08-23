# DISPATCH PURPOSE STATEMENT

**Document Type:** Core Architecture & Governing Purpose
**Program:** Dispatch
**Authority:** Mike Zachary remains final authority.
**Scope:** Whole System

---

## Purpose Statement

Dispatch exists to:

1. **See Reality.**
2. **Evaluate Possibilities.**
3. **Choose A Future.**
4. **Execute The Mission.**

All software components, interfaces, pipelines, and data models within Dispatch shall align with and support this core purpose statement.

---

## Core Architectural Discoveries & Guiding Principles

### 1. Current Mission Is Always Priority #1
Dispatch must always prioritize the currently executing mission above future opportunities.
- **Core Rule:** `Current Mission > Everything Else`
- No future opportunity evaluation may interfere with safe and effective execution of the current mission.

### 2. Week View Is Capacity Visualization, Not Scheduling
Week View is **NOT** a dispatch board, planning board, or scheduling system.
- **Core Purpose:** Allow the owner/operator to instantly see:
  - Available Capacity
  - Consumed Capacity
  - Reserve Capacity
  - Position Capacity
  - Schedule Gaps
- Week View exists for operational awareness, not planning or scheduling.

### 3. Score Does Not Decide
Score exists strictly to reduce noise and sort human attention.
- **Core Rule:** `Score reduces noise. Humans decide.`
- Score does not approve, reject, or choose.
- Mike Zachary and the owner/operator retain 100% decision authority. Automation, AI, or algorithms hold zero decision-making authority.

### 4. Intelligence Volume Can Be Large
The Intelligence layer assumes opportunity abundance and high-volume intake (50, 100, 200+ opportunities simultaneously).
- The architecture assumes abundance, never one opportunity at a time.

### 5. Opportunity Processing Pipeline Workflow
Opportunities flow linearly through structured operational states:
```
INTELLIGENCE (collects opportunities)
  ↓
ANALYSIS (adds operational context)
  ↓
SCORE (reduces noise)
  ↓
FILTERS / SORT (shape candidate pool)
  ↓
OPPORTUNITY CARDS (represent possible futures)
  ↓
OWNER / OPERATOR (human judgment & decision)
  ↓
COMMIT LOAD
  ↓
CALENDAR
```

### 6. Reality Versus Futures Separation
Dispatch operates in two strictly separated operational states:
- **State 1: Current Reality** (What is true now: Current Mission, Week View, Truck Position, Commitments, Capacity).
- **State 2: Possible Futures** (What could become true: Opportunity Cards, What-if Scenarios, Capacity Consumption, Revenue Creation, Position Creation, Future Weeks).
- **Core Rules:**
  - `Calendar stores commitments.`
  - `Opportunity Cards store possibilities.`
  - `Reality and Possibilities must remain separate.`

### 7. Opportunity Card Lifecycle
A formal non-reversible transition from possibility to reality:
`Discovered` → `Analyzed` → `Scored` → `Filtered` → `Presented` → `Selected` → `Committed` → `Calendar Event` → `Current Reality`
- Opportunity Cards represent futures; Calendar Events represent reality. These concepts are never merged.

### 8. Dynamic Capacity as Spine Engine
Dynamic Capacity is a first-class Dispatch Spine object (not a scheduler feature or portal widget) spanning 6 core operational dimensions:
- Physical Capacity
- Time Capacity
- Position Capacity
- Reserve Capacity
- Cargo Arrangement Capacity
- Stop Sequence Capacity

### 9. Truck Arrangement Is Operational Intelligence
Truck Arrangement is operational data (not documentation) that influences Capacity, Scheduling, Scoring, Pricing, and Revenue Projection.

### 10. Driver Portal Is Execution Focused
The Driver Portal is an execution interface (Current Mission, Week View, Contacts, Navigation, Milestones, POD, Fuel, Settlement) focused entirely on Mission Execution.
- The Driver Portal is NOT an opportunity workspace or dispatch planner.
