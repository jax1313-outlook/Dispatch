# DECISION_LOG.md

Append-only record of owner-approved changes to Dispatch's governed capabilities (the IFTA calculation engine, the archive/evidence layer, and the decision-gate/finalization mechanism — see `DISPATCH_PHASE1_PROCESS_DISCIPLINE_LAUNCH_PACKAGE_v1`, Section 1, for the exact scope). Dispatch's routine operational features (load board, brokers, fleet, billing, driver pay, compliance, calendar, SAM.gov/CIN-Lite acquisition, sync) are not tracked here — they continue under CI alone, at their normal pace.

Each entry records the literal, verbatim approval text given for that specific change, not a paraphrase, so Dispatch's own governance claims are checkable against something concrete.

---

## 2026-08-05 — Process discipline adopted (Phase 1)

**PR:** (this change)
**Capability:** Process/governance itself — establishes this log and the walkthrough-report convention for future governed-capability changes.
**Approved by:** Mike (owner)
**Approval, verbatim:** "approved perform" — in response to `DISPATCH_PHASE1_PROCESS_DISCIPLINE_LAUNCH_PACKAGE_v1`, itself following the "OWNER RESPONSE" that approved Phase 1 ("process discipline") for planning alongside Phase 2.

---

## 2026-08-05 — IFTA missing-data hardening (Phase 2)

**PR:** #74
**Capability:** IFTA calculation engine (`dispatch/services.py`), `/ifta` page route (`portal/routes/pages.py`, `portal/templates/ifta.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "approved perform" — in response to `DISPATCH_IFTA_PHASE2_LAUNCH_PACKAGE_v1`, itself following the "OWNER RESPONSE" approving Phase 2 for planning with the instruction: "Prepare launch package for Phase 2 first: - refuse-on-missing-rate - mileage plausibility warning. Use Dispatch as the target. Use Hold only as reference/proven pattern. Do not import Hold wholesale. Do not replace Dispatch IFTA engine. Do not alter unrelated Dispatch capabilities."
**Walkthrough:** `PHASE2_IFTA_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — Archive content-hash verification (Phase 3)

**PR:** (this change)
**Capability:** Archive/evidence layer (`cin_lite/archive.py`), `/api/pipeline/archive` and `/api/pipeline/archive/<id>` routes (`portal/routes/pipeline.py`), `/archive` page route (`portal/routes/pages.py`, `portal/templates/archive.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "fail closed, approved perform" — answering `DISPATCH_ARCHIVE_PHASE3_LAUNCH_PACKAGE_v1`'s open question (Section 8: whether a hash mismatch on read should fail closed or return data with a non-blocking warning) and approving the package for implementation.
**Walkthrough:** `PHASE3_ARCHIVE_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — IFTA quarter finalization gate (Phase 4)

**PR:** (this change)
**Capability:** Decision-gate/finalization mechanism, new for IFTA (`dispatch/services.py`, `dispatch/models.py`, `dispatch/store.py`, `dispatch/db.py`), new routes (`portal/routes/dispatch_api.py`), `/ifta` page route (`portal/routes/pages.py`, `portal/templates/ifta.html`, `portal/templates/ifta_approval_decision.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "Quarterly only for now, single reviewer is fine" — answering `DISPATCH_IFTA_PHASE4_FINALIZATION_GATE_LAUNCH_PACKAGE_v3`'s two remaining open questions (granularity, approval authentication), following Mike's direction that this workflow was already proven in Hold ("we created this yesterday in the Hold/IFTA. QuickBooks integration was to be held by placeholder until API connection can be accomplished") and his instruction to "create the required gate."
**Walkthrough:** `PHASE4_IFTA_FINALIZATION_GATE_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — IFTA fuel-purchase evidence linkage + review dashboard (Phase 5)

**PR:** (this change)
**Capability:** IFTA calculation engine provenance (`dispatch/services.py`'s `_ifta_aggregate()`), new fuel-purchase evidence layer (`dispatch/models.py`, `dispatch/db.py`, `dispatch/store.py`, `dispatch/services.py`), new routes (`portal/routes/dispatch_api.py`), new `/ifta/review` page (`portal/routes/pages.py`, `portal/templates/ifta_review.html`), `/ifta` page fuel-purchase form (`portal/templates/ifta.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "Yes, write it for both" — approving research and launch package preparation for both items — followed by "Prepare the deployment guide, continue to build using your best judgement," which authorized implementing `DISPATCH_IFTA_PHASE5_LAUNCH_PACKAGE_v2`'s two remaining open questions (fuel-purchase receipt-upload UX; `/ifta/review` route naming/placement) using best judgment, per Mike's earlier explicit endorsement of this session's launch-package-first discipline ("I'd like to keep that discipline here too... i agree continue in your best manner").
**Walkthrough:** `PHASE5_IFTA_EVIDENCE_AND_REVIEW_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — IFTA exception detectors (Phase 6a)

**PR:** #79
**Capability:** IFTA calculation engine (`dispatch/services.py`'s new detector functions and their wiring into `submit_ifta_quarter_for_approval()`), new `ifta_exceptions` layer (`dispatch/models.py`, `dispatch/db.py`, `dispatch/store.py`), new route (`portal/routes/dispatch_api.py`), `/ifta/review` Exceptions panel replacing Phase 5's ad hoc Plausibility Warnings panel (`portal/templates/ifta_review.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "Approved both, use your best judgement" — approving `DISPATCH_IFTA_PHASE6A_EXCEPTION_DETECTORS_LAUNCH_PACKAGE_v1` and `DISPATCH_IFTA_PHASE6B_RECEIPT_VISION_PREFILL_LAUNCH_PACKAGE_v1` together, authorizing both packages' open questions to be resolved using best judgment (Section 6 of each). For 6a: the Exceptions panel replaces rather than sits alongside the old warnings panel (Open Question 1), and `broken_evidence_linkage` findings are flagged, never used to block evidence resolution at seal time (Open Question 2).
**Walkthrough:** `PHASE6A_IFTA_EXCEPTION_DETECTORS_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — Vision-assisted fuel-receipt pre-fill (Phase 6b)

**PR:** (this change)
**Capability:** IFTA fuel-purchase intake (`cin_lite/agents/receipt_vision.py`, new), new route (`portal/routes/dispatch_api.py`), `/ifta` page fuel-purchase form (`portal/templates/ifta.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "Approved both, use your best judgement" — approving `DISPATCH_IFTA_PHASE6A_EXCEPTION_DETECTORS_LAUNCH_PACKAGE_v1` and `DISPATCH_IFTA_PHASE6B_RECEIPT_VISION_PREFILL_LAUNCH_PACKAGE_v1` together, authorizing both packages' open questions to be resolved using best judgment. For 6b: `extraction_confidence` is a discardable form-fill hint, not persisted on the saved fuel purchase (Open Question 1); this ships now with the graceful "unavailable, fill manually" fallback as its only exercised behavior, since no real `ANTHROPIC_API_KEY` exists in this build/deploy environment yet (Open Question 2) — the live-extraction code path is real but untested live, same honesty Hold's own README states for its equivalent.
**Walkthrough:** `PHASE6B_RECEIPT_VISION_PREFILL_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-05 — Suspect Entries panel (Phase 7)

**PR:** (this change)
**Capability:** IFTA fuel-purchase model (`dispatch/models.py`, `dispatch/db.py`), fuel-purchase creation (`dispatch/services.py`'s `add_ifta_fuel_purchase()`), `/ifta/review` Suspect Entries panel (`dispatch/services.py`'s `build_ifta_review_dashboard()`, `portal/templates/ifta_review.html`), new route field (`portal/routes/dispatch_api.py`), `/ifta` page fuel-purchase form (`portal/templates/ifta.html`)
**Approved by:** Mike (owner)
**Approval, verbatim:** "please answer question" — asking me to resolve `DISPATCH_IFTA_PHASE7_SUSPECT_ENTRIES_LAUNCH_PACKAGE_v1`'s one open question (whether suspect-entry count should factor into the readiness rollup) myself, then proceed. Resolved no: matching Hold's own precedent of keeping this an ungoverned, informational-only panel, and because the dispatcher already reviewed and could correct the extracted values before saving, making a post-save low confidence score a weaker signal than the panel's existing hard exceptions — folding an uncalibrated threshold into the top-line readiness status would let a soft, unproven number downgrade an otherwise-ready quarter.
**Walkthrough:** `PHASE7_SUSPECT_ENTRIES_WALKTHROUGH_REPORT_v1.md`

---

## 2026-08-21 — Build Matrix adopted; Level 1 defect missions built (M1, M3, M-A)

**PR:** (this change)
**Capability:** Mission-state transition enforcement (`dispatch/services.py`'s `add_milestone()`, `portal/models/conflict.py`, `portal/routes/dispatch_api.py`); Route Risk persistence (`route_risk/engine.py`, `dispatch/route_risk.py`, `dispatch/store.py`, `dispatch/db.py` schema + migration); JSON store durability (`portal/models/__init__.py` and the eleven `portal/models/*.py` stores, `dispatch/email_helper.py`); test isolation (`tests/conftest.py`).
**Approved by:** Mike (owner)
**Approval, verbatim:** "You are now authorized to produce the Build Matrix and implement approved missions in dependency order. Follow repository governance. Follow constitutions. Follow ontology. Follow source-of-truth boundaries. Do not introduce new architecture without review. Do not reactivate Manager. Do not create a second calendar. Do not turn Portal into a source of truth. Do not turn Website into a source of truth. Do not assign judgment to deterministic layers. Document every assumption. continue until completed by pass review checkpoints. use best judgement and conserative preception." — in response to `DISPATCH_REPO_RECONCILIATION_PLAN_v1`, the repository-grounded reconciliation of the proposed context architecture (Ontology, Mission/Scheduling/Orchestration/Outlook constitutions, Driver Portal context, and the startup/shutdown/reset review) against this repository.

**Scope taken, conservatively.** The Build Matrix (`DISPATCH_BUILD_MATRIX_v1.md`) registers eleven missions. Only the four requiring **no doctrine and no new architecture** were built: M0 (documentation only), M1, M3, and M-A — all Level 1 defect fixes or read-only evidence. Every other mission is recorded as **held** or **blocked**, because it would either introduce a new component (BM-01: M2, M5, M6) or depend on doctrine that does not exist (BM-07: M9, M10) or on an unanswered Level 0 adjudication (M4, M7, M8).

**The Level 0 adjudication is NOT resolved by this change and blocks the layer work.** Constitution v3 §6.4 assigns deterministic runtime machinery to **Dispatch Spine**, specified in `DISPATCH_SPINE_SPECIFICATION_v1` (Claude-3 repo); the proposed package divides the same responsibilities across three new layers and does not mention the Spine. None of M1/M3/M-A creates or names a layer, so none of them presumes an answer. Mike must settle it before any mission that does.

**Assumptions requiring confirmation** (BM-08), each argued in its walkthrough report:
1. **M1** — a refused transition still records the milestone; only the status change is refused. The alternative (refuse the whole operation) would discard reported evidence and would break `generate_pod()` on completed/archived loads.
2. **M1** — refusals are raised at severity `warning`, not `critical`.
3. **M3** — no dual write: a persisted event is not also kept in module memory, so `_ROUTE_RISK_EVENTS` is now always empty in Dispatch use.
4. **M3** — one column (`has_map_visual`) added via the existing idempotent migration, judged in-scope for exact round-trip fidelity; adding a table would not have been.
5. **M-A** — `dispatch/email_helper.py` duplicates the atomic-write routine rather than importing it, preserving THE MIKE RULE standalone boundary.

**Behavior change enumerated** (BM-09): M1 refuses **90 of 121** (load status × milestone type) pairs that previously succeeded; 31 remain accepted. The full matrix is in the M1 walkthrough report and the count is pinned by a test so it cannot move silently.

**Incidental fix disclosed:** the test suite was writing into the live `portal/data/` directory (400 accumulated conflict notices, including two types no longer in `CONFLICT_TYPES`). One line added to the existing `tmp_archive` isolation fixture; zero tests changed behavior.

**Tests:** full suite **2771 passed**, from a 2705 baseline — 66 new tests, no test deleted or weakened. Live walkthroughs run against a real Flask server and, for M3, across two separate interpreter processes.

**Walkthroughs:** `M1_MISSION_TRANSITION_GATE_WALKTHROUGH_REPORT_v1.md`, `M3_ROUTE_RISK_DURABILITY_WALKTHROUGH_REPORT_v1.md`, `MA_ATOMIC_STORE_WRITES_WALKTHROUGH_REPORT_v1.md`
**Registers:** `DISPATCH_BUILD_MATRIX_v1.md`, `DISPATCH_TRIGGER_AND_SIDE_EFFECT_INVENTORY_v1.md` (M0)

---

*Format note: new entries are appended below the most recent one, most-recent-last, matching normal changelog convention. Do not edit or remove past entries — this file is a record, not a status board.*
