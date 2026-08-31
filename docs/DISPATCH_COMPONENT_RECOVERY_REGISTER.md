# DISPATCH COMPONENT RECOVERY REGISTER

Status: REGISTER. Read-only inventory of what the lineage holds, where it lives, and what
Dispatch should do with it. No runtime behaviour is changed by this document.

Labels: **CONFIRMED** — verified in source. **INFERRED** — reasoned from evidence.
**RECOMMENDATION** — a proposal for Mike. **UNKNOWN** — not established.

---

## Legend for Status

| Status | Meaning |
|---|---|
| `PRESENT` | Already in Dispatch, working |
| `PARTIAL` | In Dispatch, but incomplete or structurally wrong |
| `LOST` | Existed in the lineage, absent from Dispatch |
| `NEW` | Never existed anywhere; must be built |

---

## A. Governance and authority

| ID | Component | Source | Status | Action |
|---|---|---|---|---|
| R-01 | Master Constitution | v1.0.1 + v1.1 (two differing copies) | LOST | Reconcile, then adopt as doctrine |
| R-02 | Project Memory Rules | v1.0.1 + v1.1 (two differing copies) | LOST | Reconcile, then adopt |
| R-03 | Human final authority | v1.0.1 doctrine; current Dispatch | PRESENT | Hold. Not configurable. |
| R-04 | No-fabrication rule | v1.0.1 doctrine; v1.1 code | PARTIAL | Rule exists; enforcement does not |
| R-05 | Decision vocabulary | v1.3.1 `update_decision()` | LOST | Recover; map to Dispatch (names not final) |
| R-06 | Decision validation on write | v1.3.1 (`raise ValueError`) | LOST | Recover |
| R-07 | Default `Undecided` | v1.3.1 schema default | LOST | Recover |

## B. Evaluation

| ID | Component | Source | Status | Action |
|---|---|---|---|---|
| R-08 | Blocking-condition veto | v1.0.1 `app.py:197`, v1.3.1 `app.py:87` | **PARTIAL** | `capacity.py` has `SEVERITY_BLOCKING`; `scoring.py` does not use it. **Integrate.** |
| R-09 | Severity ladder | v1.0.1 (BLOCKING only); `capacity.py` has INFO/ADVISORY/BLOCKING | PARTIAL | Align vocabulary; write the catalogue |
| R-10 | Externalised weights | v1.0.1 `config/scoring_rules.json` | LOST | Recover into policy profile |
| R-11 | Classification bands | v1.0.1 `classify()` | PARTIAL | Dispatch has a score, no bands |
| R-12 | Reasons as stored output | v1.0.1, v1.3.3 | LOST | Recover |
| R-13 | Risks as stored output | v1.0.1, v1.3.3 | PARTIAL | Dispatch computes, does not store separately |
| R-14 | Missing-information as stored output | INFERRED from v1.0.1 risk strings | NEW | Build |
| R-15 | Tiered territory (core / acceptable / expansion / hard_no) | v1.3.3 `settings.json` | LOST | Recover; add veto on hard_no |
| R-16 | `location_status` + `location_reason` | v1.3.3 | LOST | Recover |
| R-17 | Growth potential + reason | v1.3.3 `growth()` | LOST | Recover |
| R-18 | Recommended action | v1.3.3 | LOST | Recover as separate output |
| R-19 | Confidence | v1.3.3 | LOST | Recover — and fix (see R-20) |
| R-20 | Confidence from information completeness | nowhere | NEW | v1.3.3 derived confidence from score. Wrong. |
| R-21 | Filter stage | nowhere | NEW | No build ever had one |
| R-22 | Sort stage, separate from score | nowhere | NEW | Build |
| R-23 | Position impact | current Dispatch `scoring.py` | PRESENT | Keep as a dimension |
| R-24 | Return-home requirement | current Dispatch | PRESENT | Keep |
| R-25 | Tomorrow position risk | current Dispatch | PRESENT | Keep — this is Reserve Capacity thinking |
| R-26 | HOS risk | current Dispatch | PRESENT | Keep |
| R-27 | Route risk | current Dispatch | PRESENT | Keep |
| R-28 | Deadhead miles | current Dispatch | PRESENT | Keep |
| R-29 | Fuel estimate | current Dispatch | PRESENT | Keep; move rate to profile |
| R-30 | Economic opportunity | current Dispatch | PARTIAL | Splits into score + recommendation |
| R-31 | Return position value | INFERRED from R-23/R-25 | NEW | Named dimension in the mission brief |

## C. Workflow

| ID | Component | Source | Status | Action |
|---|---|---|---|---|
| R-32 | One evolving record | GOLD; current Dispatch `mission.py` | PRESENT | Hold |
| R-33 | Atomic human gates | GOLD | PARTIAL | ACCEPT LOAD exists; Interested/Pursue do not |
| R-34 | Interested → Brief | GOLD (`interested`, `brief_path`) | LOST | Recover |
| R-35 | Pursue → Workspace | GOLD (`pursue`, `workspace_path`) | LOST | Recover |
| R-36 | Publisher | GOLD `publisher_mvp.py` | LOST | Recover — Lane B excludes; later mission |
| R-37 | Artifact creation | GOLD (4 briefs on disk) | LOST | Recover with Publisher |
| R-38 | Workspace creation | GOLD (2 workspaces on disk) | LOST | Recover with Publisher |
| R-39 | Archive | GOLD | PARTIAL | Dispatch has archive paths |
| R-40 | Duplicate protection | GOLD | LOST | Recover at adapter boundary |
| R-41 | Source preservation | GOLD (`raw_json`, `source_url`) | PARTIAL | Load number preserved; raw source not |
| R-42 | Run history | v1.1 / GOLD (`scan_runs`) | PARTIAL | Sweep exists; history not stored |
| R-43 | Recovery paths | GOLD `ensure_column()` | LOST | Recover — schema migration without data loss |
| R-44 | Mission numbering | current Dispatch | PRESENT | Hold |
| R-45 | Dual numbering | current Dispatch | PRESENT | Hold |
| R-46 | View resolution (CURRENT) | current Dispatch | PRESENT | Hold |

## D. Operations

| ID | Component | Source | Status | Action |
|---|---|---|---|---|
| R-47 | Scheduled scanning (06:00 / 12:00 / 18:00) | v1.1, v1.3, v1.3.1, v1.3.3 config | LOST | Recover into profile |
| R-48 | Repeated operational execution | v1.1 (10 scan runs — most exercised build) | LOST | Recover |
| R-49 | Dashboard reset | v1.3 `reset()` | LOST | Recover as an explicit, confirmed action |
| R-50 | Clean-room testing | v1.3.1 (empty archive by design) | LOST | Adopt as practice, not code |
| R-51 | Connector recovery | v1.3 sprint | INFERRED | Lesson: recover by reporting, never by fabricating |
| R-52 | Adapter UNAVAILABLE contract | JOE Outlook adapter | PARTIAL | Formalise across all adapters |
| R-53 | Credential hygiene | — | **NEW** | Live key in 13+ files across lineage |

## E. Current Dispatch doctrine — hold, do not rebuild

| ID | Component | Status |
|---|---|---|
| R-54 | Mission Record | PRESENT |
| R-55 | System Independence | PRESENT |
| R-56 | Driver First | PRESENT |
| R-57 | COMI | PRESENT |
| R-58 | Librarian | PRESENT |
| R-59 | Route Risk | PRESENT |
| R-60 | JOE | PRESENT |
| R-61 | Progressive Detail | PRESENT |

---

## Priority

**RECOMMENDATION.** Recovery order, by consequence of being wrong.

| Rank | Item | Why first |
|---|---|---|
| 1 | **R-08 blocking veto** | `capacity.py` can block; `scoring.py` cannot, and a load that cannot be run still scores 95 there |
| 2 | **R-10 externalised policy** | Every other recovery needs somewhere to put its thresholds |
| 3 | **R-21 / R-22 filter and sort** | Cannot separate the stages without them existing |
| 4 | **R-15..R-19 territory, growth, recommendation, confidence** | The dimensions the brief requires |
| 5 | **R-05..R-07 decision vocabulary** | Needs the state model settled first |
| 6 | **R-33..R-38 gates and Publisher** | Explicitly out of scope for Lane B |

## Open items

- **ANSWERED 30 Aug 2026:** the vehicle is a cargo van with trailer, 6 pallets, 10,000 lb
  capacity. This adds **R-62 — pallet capacity as a blocking condition** (`NEW`; nothing in
  the lineage tracked pallets) and invalidates three capability defaults calibrated for a
  Class 8 truck. See `DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md` §3, Defect D.
- **UNKNOWN:** whether a v1.2 ever existed. No folder, no artifact, no reference found.
- **UNKNOWN:** whether v1.0.1's `decision` column was ever set to a non-default value. Its
  database was read for counts only.
- **OPEN:** the two Master Constitution copies differ. Which is authoritative?
- **OPEN (Mike's decision):** SAM.gov key rotation.
- **OPEN (Mike's decision):** whether `Monitor` and `Defer` both survive into Dispatch.
