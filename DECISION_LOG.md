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

## 2026-08-21 — Architectural adjudication: Spine ownership partitions, state models, load identity, Driver-First

**PR:** (this change)
**Capability:** Governance only. No code changed. Documents added: `DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1.md`, `DRIVER_FIRST_DOCTRINE_v2.md`, `DISPATCH_GOVERNANCE_MANIFEST_REPAIR_PLAN_v1.md`, `DISPATCH_OWNERSHIP_MATRIX_v1.md`, `DISPATCH_BUILD_MATRIX_v2.md`.
**Approved by:** Mike (owner)
**Approval, verbatim:**

> "MIKE ZACHARY ARCHITECTURAL ADJUDICATION — The reconciliation findings are accepted for the next governance-alignment stage.
>
> DECISION 1: SPINE AND OWNERSHIP PARTITIONS. Dispatch Spine remains the single deterministic runtime element named by Constitution v3 and governed by DISPATCH_SPINE_SPECIFICATION_v1. Mission, Scheduling, and Orchestration are adopted as named deterministic ownership partitions inside Dispatch Spine. They are not departments. They are not agents. They are not independent systems. They do not replace Dispatch Spine. They exercise no judgment or discretion. Their ownership questions are: Mission: Where does this load stand, and what evidence supports that standing? Scheduling: Does this proposed commitment fit approved time, capacity, reserve, conflict, and repositioning rules? Orchestration: What approved deterministic action happens next, and where is the work handed? The Scheduling ownership partition adds capacity responsibilities not currently present in Spine. Amendment of Spine §3 and §15 to include capacity is approved in principle but remains blocked from implementation until Reserve Capacity Doctrine and Jacksonville Repositioning Doctrine are supplied and adopted.
>
> DECISION 2: STATE MODELS. The existing repository load-status model remains authoritative for freight execution through physical space. The Spine work-item-state model remains the governing model for review, routing, approval, conflict, and processing state. These models describe different subjects and may coexist. Fable's proposed transition vocabulary shall not become a third parallel state model. Its useful evidence and transition requirements shall be mapped into the appropriate existing load-status or Spine work-item-state model. No builder may merge these models, replace either model, or create a third state authority without Mike Zachary's explicit approval.
>
> DECISION 3: LOAD IDENTITY. The existing SBX, LOAD, and CIN identifiers may remain where their separate record classes require them. The governing requirement is one answerable retrieval chain, not forced migration to one physical identifier. Every related opportunity, load, communication, document, mission event, and archived record must remain retrievable through explicit correlation. No identifier migration is authorized in this mission.
>
> DECISION 4: DRIVER-FIRST DOCTRINE. DRIVER_FIRST_DOCTRINE_v1 is substantively accepted as governing doctrine subordinate to Constitution v3, but it is not yet adopted because its clause numbering conflicts with existing repository citations. Produce a clause reconciliation that: 1. Preserves the existing intended meanings of D6, D9, and D11. 2. Adds the missing external-disclosure doctrine explicitly. 3. Produces one authoritative citation map. 4. Identifies every code, test, docstring, and governance reference affected. 5. Does not modify code until the doctrine numbering is approved.
>
> DECISION 5: GOVERNANCE MANIFEST. Repair of the repository manifest and supersession records is authorized as governance alignment. The repair must: 1. Correct the Spine Specification filename. 2. account for the missing stress-test prompt. 3. list all governing documents currently on disk. 4. state the status of the Round 2 SUPERSESSION_MAP against v3 artifacts. 5. identify authoritative, proposed, superseded, dormant, and unadopted documents clearly. 6. make no substantive doctrine changes.
>
> DECISION 6: CURRENT IMPLEMENTATION CONFLICTS. Record the following as bounded corrective missions, not architectural redesign: 1. Retire the duplicate sandbox mission-state copy through an approved read-through design. 2. Reconcile or retire the current /calendar page so Outlook remains the only calendar and the Driver Portal presents a Visual Capacity Board. 3. Correct status-change audit asymmetry between update_load() and add_milestone(). 4. Continue replay-protection work before authorizing unattended scheduled operations. Do not combine these into one mission.
>
> DECISION 7: OVERNIGHT BOUNDARY. Pending formal Overnight Operations Doctrine, the provisional safe boundary is: The VPS may serve existing read-only surfaces and perform approved detection. It may not automatically send externally, make commitments, change mission state, consume reserve, purge records, or execute unapproved workflows. Detection may accumulate cards for review at the next local session. This provisional boundary authorizes planning only, not implementation of a scheduler or overnight worker."

**Also, verbatim, the standing instruction that opened the mission:** "Renumber DRIVER_FIRST_DOCTRINE_v1 to match existing code citations."

**What was produced.** Six deliverables, all governance documents. **No code was modified**, per Decision 4.5. The full test suite was re-run to confirm the repository is unchanged: 2771 passing, identical to the prior commit.

**Findings recorded during production, requiring Mike's attention:**

1. **The Driver-First renumbering is clean.** D6 (Operational Retrieval), D9 (Retrieval Is Not Modification) and D11 (External Disclosure Chain) are pinned to their established code meanings. Nine of v1's twelve clauses keep their number; three relocate to D13/D14/D15. **17 clause citations across 8 files remain correct with no edit.** One reference — `portal/models/operations_feed.py:18`, which cites Driver-First "§0" rather than a clause — goes stale because v2 restructured §0; the posture it names is now D10. That is the only invalidated reference in the repository.

2. **A second collision layer exists that the adjudication did not cover.** The repository contains at least three separate `D<n>` registers cited in bare form: Driver-First (D6, D9, D11), a deployment decision register (D1), and a requirements register (D3, D4, D10). A bare "D3", "D4" or "D10" is ambiguous today, and adopting Driver-First D1–D15 widens the overlap. A `DF-` citation prefix is recommended and **not** performed — Decision 4.5 bars code change until numbering is approved.

3. **Corrective mission C2 must split.** Decision 6.2 requires both retiring `/calendar` and presenting a Visual Capacity Board. The Board displays capacity, and capacity is blocked on Reserve Capacity Doctrine. C2a (retire or rename, available now) and C2b (build the Board, blocked) are registered separately so C2a cannot silently become C2b.

4. **Manifest repair needs four answers before it can execute**, one of which requires recall rather than judgment: what became of `DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md`, which the manifest lists and which is absent from disk.

**Recommended first executable mission:** C3 (status-change audit asymmetry) — the only corrective mission needing neither doctrine nor a design decision, with the smallest blast radius, and a direct Spine §8 compliance fix that closes a gap M1 exposed.

**Deliverables:** `DISPATCH_SPINE_OWNERSHIP_PARTITION_AMENDMENT_v1.md`, `DRIVER_FIRST_DOCTRINE_v2.md`, `DISPATCH_GOVERNANCE_MANIFEST_REPAIR_PLAN_v1.md`, `DISPATCH_OWNERSHIP_MATRIX_v1.md`, `DISPATCH_BUILD_MATRIX_v2.md`

---

## 2026-08-21 — C3: status-change audit symmetry

**PR:** (this change)
**Capability:** Mission-state audit trail (`dispatch/services.py` — new `_record_status_change()` helper plus four call sites: `update_load()`, `add_milestone()`, `_try_auto_dispatch()`, `archive_load()`).
**Approved by:** Mike (owner)
**Approval, verbatim:** "MISSION: C3 STATUS-CHANGE AUDIT SYMMETRY — Mike Zachary authorizes implementation of corrective mission C3 only. … Correct the status-change audit asymmetry between the repository's approved status-transition paths. … Required outcome: Every accepted status change, regardless of approved entry path, must produce one consistent audit event containing the required transition evidence. … Do not begin C1, C2a, C2b, C4, or any other Build Matrix mission without separate authorization."

**Analysis before editing found four status-change paths, not two.** The brief named `update_load()` (audited) and `add_milestone()` (unaudited). Two further unaudited paths were found and included on the strength of "regardless of approved entry path": `_try_auto_dispatch()` (`created → dispatched`) and `archive_load()` (`… → archived`). Both were moving loads between states with no audit trail at all.

**Narrowest implementation point: the service layer, not the store layer.** `store.update_load()` is the single point every path passes through, and was rejected for two reasons — it is deliberately the raw unvalidated write (M1 asserts this), and, decisively, **it cannot satisfy the audit requirement**: only the service call sites know which operation moved the status, and the originating operation must be recorded.

**No schema change.** The existing `activities` table carries the event. Load id, timestamp and actor land in real columns; previous state, new state and originating operation land in the message, which is the format this repository already used.

**Assumptions requiring confirmation** (BM-08), argued in the walkthrough:
1. The existing `activities` shape is the "approved repository equivalent" for previous/new state. Spine §8 wants structured `previous_state`/`new_state` fields — that is the Spine Event-schema mission, which C3 was not authorized to begin.
2. `source="user"` when an actor is known, `"system"` otherwise, because `ACTIVITY_SOURCES` admits only those two. A milestone's own source vocabulary is preserved in the operation string instead. Actor is never fabricated.
3. Paths 3 and 4 are in scope. If a strictly two-path fix was intended, they are two lines each and trivially removable.

**The no-op divergence is preserved, not resolved.** `update_load()` has always written an event when previous == new — `"Status changed from dispatched to dispatched"` — which is a false statement in an audit log. Current behavior was identified by probe before editing, as the mission required, and then **left alone**, because changing it would alter existing repository policy. The three paths C3 added fire only on a real change. Both behaviors are asserted by tests so neither can drift. **Recommendation for Mike: stop auditing no-ops on `update_load()` too — a one-line guard that removes only false entries and makes all four paths identical.** Not done here.

**Behavior change enumerated** (BM-09): every `status_change` message now carries a `(via …)` suffix naming the originating operation. Additive; these messages render on the load detail pages; no existing test broke.

**Disclosed:** analysis probe scripts ran outside the test harness and wrote two Conflict Notices into the working copy's live `portal/data/conflicts.json` (400 → 402 entries). Not cleaned up deliberately — unresolved conflict notices are classified protected, and purge is an Archive function under a retention policy that does not exist. `portal/data/` is gitignored; nothing entered the repository.

**Tests:** full suite **2804 passed**, from a 2771 baseline — 33 new, none deleted or weakened. Test isolation proven by mtime rather than asserted: `portal/data/conflicts.json` is byte-identical before and after the refusal-heavy test modules.

**Files changed: 2** — `dispatch/services.py` and the new `tests/test_status_change_audit.py`. No schema, migration, template, route or dependency change.

**Walkthrough:** `C3_STATUS_CHANGE_AUDIT_WALKTHROUGH_REPORT_v1.md`

---

*Format note: new entries are appended below the most recent one, most-recent-last, matching normal changelog convention. Do not edit or remove past entries — this file is a record, not a status board.*
