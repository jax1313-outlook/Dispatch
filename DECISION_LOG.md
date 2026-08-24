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

## 2026-08-23 — W0-3: Portal adjudication; W0-1 security cleanup; packaging repair

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** Process/governance — names the operational portal; plus two contained repairs.
**Approved by:** Mike (owner)

**Approval, verbatim (this entry):** "You are authorized to proceed with:\n\n1. Portal adjudication recording\n2. Packaging repair (Path B)\n3. Recovery Wave 1 planning\n\nDo not begin broad repairs yet."

**Prior approval, verbatim (W0-1):** "MISSION: W0-1 SECURITY CLEANUP … Mike Zachary authorizes W0-1. … Delete Jules/flask_app.log if and only if the file contains a Werkzeug debugger PIN or similar runtime debug secret as identified in the cross-repository audit."

### Decision recorded — W0-3, Portal adjudication

**`Dispatch/portal/` is Dispatch.** `jax1313-outlook/Jules` is a design archive, read-only and not
maintained as a product. Its presentation design (the driver cockpit and the public site) may be
harvested into Dispatch later, as a separate, separately-approved mission; its runtime is not
recovered.

**Basis, from `W0-3_PORTAL_ADJUDICATION_BRIEF.md`:** Dispatch/portal/ has 218 routes, 26 SQLite
tables, a fail-closed PIN gate with three disjoint session namespaces, and 2,817 passing tests, and
its persistence was proven across a real process restart during the W0-2 rehearsal. Jules has 13
routes, no persistence (a module singleton seeded by `_bootstrap_sample_data()`), no authentication
on any route, and a POD endpoint that returns `"POD uploaded successfully"` when no file was posted.

**Interpretation flag — read this.** The authorization above says "portal adjudication recording"
without naming a portal. This entry records the **recommendation** the brief made. That is an
interpretation, not Mike's verbatim words, and it is marked as such deliberately rather than
presented as a quotation. **If a different portal was intended, this entry is corrected by a new
appended entry — it is not edited.** Nothing downstream has been built on it yet; W0-4 (governance
home) is the first unit that depends on it.

### W0-1 — security cleanup (executed under its own authorization)

`Jules/flask_app.log` removed: a committed Werkzeug runtime log containing `Debugger PIN:
631-326-424`, for an app that `run_portal.sh` binds to `0.0.0.0` and that has no authentication.
Verified before removal as not source code (a `>`-recreated artifact of `run_portal.sh:28`) and not
an operational record (16 lines, five GETs, zero state-changing requests, against an app that
persists nothing). A `.gitignore` with `*.log` was added; the repository had none.
**Jules commit `2aeb2beb0950c370e6f557858c1fb5a38eeb5052`.**
**Disclosed:** the blob remains reachable in history at `cadc0de`. History was not rewritten.

### Packaging repair — Path B

**Defect:** `pyproject.toml` declared four console scripts and no package configuration, with no
`setup.py` or `setup.cfg`. `pip install -e .` — the documented Quick Start in `DEPLOY_LOCAL.md` —
failed on a clean clone with *"Multiple top-level packages discovered in a flat-layout"*, so
`cin-portal-init-admin` could never be installed. `DEPLOY_LOCAL.md` states that without that step
"the app runs but nothing past the login page is reachable." **The documented install path was
unusable.** Found by rehearsing W0-2 against a fresh clone, not by reading the file.

**Fix:** a `[tool.setuptools.packages.find]` block with six `include` patterns. `find` rather than a
literal `packages = [...]` list on purpose — six of the twelve packages are subpackages, and a
literal list omits them silently: the install succeeds and `import portal.routes` then fails from
the installed distribution. That trap was hit and backed out during this change.

**Evidence:** a real wheel builds; installed into a clean venv with the working directory outside
the repository, **all 19 module imports succeed** and all four console scripts install;
`pip install -e .` on the repository exits 0; `cin-portal-init-admin` runs and prompts.
**Full suite: 2,817 passed, exit 0 — unchanged.** One file, +26 lines, no application code touched.

**Not done here:** Recovery Wave 1 remains planning only — see
`DISPATCH_RECOVERY_WAVE_1_REPORT.md`. No Spine, Driver Transformation or Archive Review Queue code
was recovered, and no broad repair was begun.

## 2026-08-23 — Driver Transformation recovered and repaired (campaign W5)

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** Driver Portal write surface — milestone progression, POD/evidence capture, dock
exception logging, fuel-receipt intake. Recovered from an unmerged branch and repaired before landing.
**Approved by:** Mike (owner)
**Approval, verbatim:** "Proceed with Driver Transformation repairs and recovery"

**Source:** `origin/jules-driver-transformation-missions-1-4-12863749728267333928` @ `afd6e00`,
built 2026-08-22 and never merged. Recovered **by path, not by commit** — the commit also
re-implements the whole of PR #111, which is already on `main`.

**Why it mattered:** before this, the Driver Portal had exactly one interactive control (Sign Out).
The whole-program audit named that the largest gap in the program, measured against Driver-First §0.

**Five defects fixed before landing, two of them High:**

1. **A refused transition never reached the driver.** `add_milestone()` does not raise on refusal —
   it returns `status_transition_refused` — and the branch discarded the return value entirely, with
   a bare `except Exception: pass` on top. A driver tapped, was redirected, and could not tell
   whether anything was recorded. That is the 70 MPH test failing, not passing.
2. **Exception logging swallowed failures** the same way.
3. **The fuel scanner had no ownership check of any kind** — the only write endpoint on the branch
   without one. Any authenticated driver could post arbitrary gallons, dollars and a jurisdiction
   into the company IFTA fuel ledger, unattached to anything. **IFTA is a quarterly tax filing.**
   Now scoped to a load the driver holds, via the same `_verify_driver_load()` the other routes use,
   with `driver:<id> load:<id>` recorded on the ledger row.
4. **Non-numeric form fields were a 500.**
5. **A rejected POD file was a 500** — `attach_evidence()` raises `ValueError` for a disallowed
   extension or an oversize file, and nothing caught it. This defect was **missed by the Wave 1
   report** and is recorded here.

**Two truth defects fixed inside the fuel route**, same class as the audit's optimistic-default
findings but in a tax record: the jurisdiction no longer defaults to `"FL"` when the scan cannot read
a state (an unknown stays unknown), and it is validated against `IFTA_JURISDICTIONS`.

**The accepted ruling is preserved:** a refused status transition still retains the reported
milestone evidence, and a test asserts it.

**Assumption requiring confirmation (BM-08):** requiring an *active load* to log fuel is the
conservative reading. **Fuelling between loads is normal**, and under this rule a driver with no
active mission cannot log a receipt. Relaxing it is one condition — but only ever to another
driver-scoped check, never back to unscoped. **Open decision for Mike.**

**Also open, and not silently assumed away:** CSRF (W2-5) and session expiry/cookie flags (W2-3) were
listed in the campaign as preceding this unit. Neither was authorized; this work proceeded on the
explicit instruction. These four endpoints are no worse than the other 105 mutating routes, and no
better.

**Tests: 6 → 24.** The branch's six proved the happy paths and asserted nothing about refusals,
rejected files, or scoping. Every negative test added asserts both that the driver is told and that
the store is unchanged. Two Mission 4 tests were rewritten to the new scoping rule; both gained
assertions. **No test was deleted or weakened.**

**Full suite: 2,841 passed, exit 0** (baseline 2,817). Files changed: 3. Conflicts against `main`: 0.

**Walkthrough:** `DRIVER_TRANSFORMATION_RECOVERY_WALKTHROUGH_REPORT_v1.md`

## 2026-08-23 — CF-04 adjudicated: Spine is the lifecycle authority; Opportunity advises

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** Architecture — names the single lifecycle authority and the standing of every
advisory subsystem.
**Approved by:** Mike (owner)

**Approval, verbatim:** "CF-04 ADJUDICATION\n\nThis is not a Spine-versus-Opportunity decision.\n\nDispatch Spine shall become the authoritative lifecycle engine and single source of lifecycle truth.\n\nDispatch Opportunity shall remain the authoritative opportunity-analysis, scoring, Dynamic Capacity, Scheduler, Route Risk, Special Requirements, and decision-support subsystem.\n\nOpportunity recommends.\n\nSpine records reality.\n\nOpportunity may request transitions.\n\nSpine owns transitions.\n\nOpportunity may not maintain a competing lifecycle authority.\n\nScheduler, Dynamic Capacity, Route Risk, and Intelligence remain advisory systems and do not become lifecycle authorities.\n\nProceed with updating the CF-04 decision brief using this architecture model and identify recovery work required to align Opportunities with Spine authority."

**The framing this repository had was wrong, and the ruling says so.** Both the conflict register and
the Wave 1 report put CF-04 as "Spine versus Opportunity" — a choice between two implementations.
It is not a choice. They are different offices, and both are retained.

**BM-10 is refined, not repealed.** BM-10 forbade a third state authority and held the load-status
and work-item models coexist. The ruling satisfies it by removing the third model from Opportunity
rather than blessing it.

**Eight competing-authority surfaces identified by line** in `dispatch/opportunities.py`: the second
state list (25–35), the second transition table (37–47), the stored `stage` (87), `transition_to()`
itself (111–131), construction-time validation (102–103), auto-advance as a side effect of analysis
(182, 216, 252, 254), `commit_opportunity_to_reality()` walking four stages and then **creating the
Load and confirming the rate itself** (261–297), and the human-authority rule living on a dataclass
string (124–129) instead of at Spine's approval gate.

**Two of the nine stages were never lifecycle states.** `Filtered` is a query over scores.
`Calendar Event` is an external side effect of an approval — Outlook is the scheduling source of
truth and there is no integration in any repository. Seven of nine map directly onto Spine's 25
states. That is corroboration of the ruling, not a coincidence: Opportunity's stage list was a
pipeline narrative wearing a state machine's clothes.

**Nine alignment units identified** (SPINE-R, OPP-01…OPP-09), dependency-ordered, in
`DISPATCH_CF04_LIFECYCLE_AUTHORITY_MODEL_v1.md`. **None is authorized by this entry** — the
instruction was to identify the work.

**Open sub-question, referred back to Mike:** does "single source of lifecycle truth" absorb
`loads.status` — 11 values, live, gated, audited, behind roughly 1,800 tests — or does it cover the
review/decision lifecycle only? **Reading A (narrow) recommended**, on the ruling's own words: the
competing authority it names is Opportunity's stage machine, and `loads.status` is a different
subject, not a duplicate. Reading B would be the largest change ever proposed to this program, over
its most production-capable part. **Blocks exactly one unit, OPP-04.**

**No code was changed by this adjudication.**

## 2026-08-23 — Fuel-receipt ownership chain; Recovery Wave 1 (R-01…R-04)

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** IFTA fuel-receipt ownership; Dispatch Spine recovery; Archive Review Queue model;
Route Risk ordering; CI coverage scope; governance-document recovery.
**Approved by:** Mike (owner)

**Approval, verbatim (ownership):** "DECISION\n\nFuel receipt ownership shall remain scoped.\n\nFuel receipts shall never be anonymous.\n\nMinimum ownership chain:\n\nDriver Identity\nTruck Identity\nTimestamp\nJurisdiction\nReceipt Evidence\n\nAssociation with an active load is preferred but not required.\n\nOwner/Operator workflows must support reporting fuel receipts when no active load exists.\n\nWhen no active load exists:\n- receipt remains linked to Driver and Truck;\n- receipt remains auditable;\n- receipt remains available for IFTA reporting;\n- no artificial load association may be created.\n\nDispatch must enforce ownership,\nbut must not require a mission when operational reality does not. continue with R1-R4"

**My earlier reading was too strict and is corrected here.** The Driver Transformation repair
required an *active load* to log fuel. The ruling is that ownership is required and a mission is
not. The scanner is now offered whenever active fleet equipment exists; a load rides along only when
one is present; **no artificial load association is created**, and a test asserts its absence.

All five links are mandatory and a receipt that cannot supply all five is refused rather than filed
thin. Because the chain requires evidence, the receipt is validated **before** any record is
written, and if the attach still fails the purchase is deleted — a fuel row with no receipt is
exactly what "never anonymous" forbids.

**Recovery Wave 1, R-01…R-04:**

- **R-02a** CI coverage widened to `cin_lite`, `dispatch`, `portal`. **The threshold did not need
  lowering** — measured coverage is **93.77 %**, already above the existing 90 % gate. The gate was
  never too strict; it was pointed at one seventh of the program.
- **R-02b** `dispatch/spine/` recovered and wired — 835 lines, 25 states, six tables, five
  hand-written lines, **23 tests**. Per CF-04 it is now the authoritative lifecycle engine.
  `dispatch/opportunities.py` is untouched and still unwired; OPP-01…OPP-09 were not authorized and
  were not started.
- **R-02c** Archive Review Queue **model** recovered. Its decision route was **not** — it depends on
  `dispatch/security/`, superseded by main's PIN gate (CF-03). Nine of the branch's 21 tests went
  with the route; the file records exactly what was left and why. **11 tests.**
- **R-02d** portal card levels — **BLOCKED, not forced.** The branch's `conflict.py` uses
  `path.write_text` and would regress M-A's atomic writes; its `sandbox.py` collides with the open
  C1 corrective mission. Recover after C1 closes, as a patch.
- **R-03** Route Risk `ORDER BY created_at DESC, rowid DESC`. `created_at` is second precision, so
  which condition a driver saw could flip between runs. The branch's test targeted an
  implementation main does not have; a new one was written against the real design.
- **R-04** `governance/PORTAL_AUTHENTICATION_DISPATCH_PIN_SCOPE_v1.md` recovered (177 lines) and its
  ten citations corrected — they named the wrong repository.

**Two regressions caught during recovery, both of which a file-level copy would have shipped
silently.** The branch's `portal/models/archive.py` is from an older base: taking it whole dropped
**58 lines of main's work** (`ArchiveApprovalError`, `RESERVED_SYSTEM_IDENTITIES`, the intelligence
section, `archive_from_intelligence()`) and replaced `atomic_write_json()` with a bare
`path.write_text()`. Reverted to main; the Review Queue re-applied as a patch. The same
`write_text` regression sits in the branch's `conflict.py` and is part of why R-02d is blocked.

**Assumptions and open items (BM-08):** `REVIEW_AGE_DAYS = 180` is **not doctrine** — the policy's
literal "Current + 3 Previous" trigger is unimplementable because Archive records have no version
history; Mike sets the number or approves version history. **17 further cross-repository citations**
were found and left for OWN-02. **CSRF (W2-5) and session expiry (W2-3) remain open.** Three state
machines now exist in the tree, expected and temporary — nothing consumes `opportunities.py`.

**Full suite: 2,882 passed, exit 0** (baseline 2,817). **+65 tests, none removed or weakened.**

**Report:** `DISPATCH_RECOVERY_WAVE_1_COMPLETION_REPORT.md`

## 2026-08-23 — Repair, Connection, Security and Durability Campaign (Workstreams A–F)

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** Dynamic Capacity truth and integration; Opportunity lifecycle alignment; secret
refusal; backup and restore; token expiry and revocation; CSRF protection.
**Approved by:** Mike (owner)

**Approval, verbatim:** "CLAUDE CODE MISSION: DISPATCH MAXIMUM-CAPACITY REPAIR, CONNECTION, AND COMPLETION CAMPAIGN … The authorized work package includes: 1. Dynamic Capacity integration and truth hardening 2. Opportunity lifecycle alignment with Spine 3. Security hardening 4. Backup and restore 5. Token expiration and revocation 6. CSRF protection … Continue until the entire authorized campaign is complete, all unblocked units are implemented, the completion report is published, and one integrated review package is ready for Mike Zachary's final review."

**Result: all six workstreams COMPLETE. No unit blocked.**
**Tests 2,882 → 3,087, exit 0. Coverage 93.73 % against the 90 % gate.**

**Implied Mike authority removed.** `apply_asset_profile` no longer defaults `verified_by="Mike
Zachary"`; `set_verified_hos` no longer defaults `source="ELD_LOG"`; a commitment refuses an empty
or reserved-system actor and records a real `ApprovalEvent`. Nothing in Dispatch now stamps Mike's
name on a decision he did not make.

**Competing lifecycle authority removed.** Opportunity's second state list, second transition
table, `transition_to()`, stored `stage` and construction-time validation are gone. Stage is read
through the correlated Spine work item. `Filtered` became a query; `Calendar Event` left the
lifecycle entirely. `commit_opportunity_to_reality()` — which walked four stages and then created
the load and confirmed the rate itself — is replaced by a request that Spine answers, with the load
created on the Spine side against a recorded human approval. A structural test fails if a competing
table or a stored lifecycle position reappears.

**The three highest-rated security findings are closed.** An operational deployment now **refuses
to start** on the published default secret rather than warning; development mode is explicit and
**pins the bind to loopback**; tokens carry purpose, object, issue time, expiry and a nonce, and can
be revoked individually or per load with a full audit trail; CSRF protects every mutating route.

**Backup and restore exist for the first time.** The acceptance test deletes the entire live estate
and recovers the load, the milestone and the POD bytes from the archive, hash-verified. Secrets are
proven absent from every byte of it.

**On the brief's explicit warning about test bypass:** CSRF is NOT disabled under TESTING, and the
suite is not exempted from the secret check. A CSRF-carrying test client and real test secrets in
`conftest.py` mean all ~1,160 HTTP tests run through the protected path; the dedicated CSRF tests
send raw unprotected requests and assert refusal.

**Three tests were rewritten, each to a stronger assertion, and none weakened** — token determinism
(which was inseparable from the never-expires defect), two page assertions that compared a
separately-minted token instead of verifying the one actually rendered, and one that relied on no
secret being configured. All three are itemised in §11 of the report.

**Schema:** two additive tables, `operational_tokens` and `token_audit`. **No existing table
altered. `loads.status` untouched**, per the narrow CF-04 reading Mike specified.

**Still unverified, stated plainly:** the `D:` delivery path (no session has ever written to that
drive); HOS readings (no ELD exists, and the code now refuses to imply one); Route Risk feeds
(`is_live_data: False` on every event); fuel and drive-hour constants; scheduler fit (there is no
scheduler, and Outlook remains the schedule); backup point-in-time consistency across stores.

**Report:** `DISPATCH_REPAIR_CONNECTION_COMPLETION_REPORT.md`

## 2026-08-24 — Operational Readiness Mission (Tasks 1–4)

**PR:** (this change) · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`
**Capability:** Windows launcher and control centre; rehearsal mode and the twenty-step
operational-proof system; read-only Sandbox survey tooling; the connector boundary and its
eight connector definitions; HOS/ELD language corrections.
**Approved by:** Mike (owner)

**Approval, verbatim:** "DISPATCH — OPERATIONAL READINESS MISSION … This is one mission with four
tasks. Run every independent task at once. Respect the dependency map in Section 7. Do not stop to
ask for approval on anything Section 8 does not reserve for Mike. Do not stop between tasks. Deliver
one consolidated pull request for application changes, one completion report, and the local-machine
artifacts described in Section 10. … Work at maximum practical capacity. Prefer the boring, proven,
inspectable implementation over the clever one. When you are uncertain whether something is proven,
it is not. When you are uncertain whether a decision is Mike's, it is. Everything else, proceed."

**Result: all four tasks IMPLEMENTED. Nothing OPERATIONALLY PROVEN.**
**Tests 3,087 → 3,577, exit 0. Coverage 94.37 % against the 90 % gate (floor 93.73 %).**

**The Sandbox was not read, and the output folder was not created.** `D:\Sandbox\Play Pen` is a
Windows path; this build environment is an isolated Linux container with no mount, network path or
credential that reaches it — checked at `/d`, `/mnt/d` and every entry under `/mnt`. That is an
environment boundary, not a permission that could have been granted. Not one file under it has been
read, listed, hashed, sampled, classified, moved, renamed, copied, deleted or executed, and no
statement in any deliverable describes its contents. What shipped instead is what Section 5.2
anticipates: the read-only tooling in the repository, 77 tests proving it performs no write against
its input path, the exact commands Mike runs, and all nine outputs in template form marked `ABSENT`.

**No Mike attribution was manufactured anywhere.** Rehearsal sessions require an explicit actor and
refuse reserved system identities; every proof step defaults to `not performed` and accepts only
`Mike`, `Code-automated`, `not performed`; two tests assert the five forbidden phrases appear in
neither the rendered proof report nor its JSON.

**The launcher has no path to Current Reality.** It never imports `dispatch.services`,
`dispatch.store` or `dispatch.spine.*` and never opens the operational database; a test asserts the
boundary against a real interpreter. It reads configuration through the application's own resolvers
in a subprocess, so it cannot report a database location or port the portal does not actually use.

**The connector boundary is structural, not conventional.** An AST pass follows transitive
first-party imports and extracts SQL table names, refusing Spine, services, store and any write to a
Current Reality table; `verify_package()` reports no violations. All eight connectors report
`UNCONFIGURED`; only the mock reports `SIMULATED`. Existing Outlook, email and accounting code was
wrapped, not duplicated, and Outlook still creates no event.

**HOS/ELD: fourteen corrections.** Three in code, three in templates, eight in architecture
documents. Dispatch is not an ELD, holds no duty-clock data, and no surface now implies it does.

**Coverage stated honestly rather than gamed.** `dispatch_launcher/` sits at 84.46 %, below the
90 % gate, and is deliberately outside the gated set: the uncovered lines are Windows-only branches
that cannot execute on the Linux CI. Adding it would have measured how much Windows code exists;
lowering the gate would have weakened it for everything else. Every one of those branches is
recorded `UNVERIFIED` in `LAUNCHER_PROOF.md`.

**Still unverified, stated plainly:** everything the mission asked to be proven on Mike's machine.
The launcher has never started a Windows process. No load has moved through a running portal on his
hardware. The Sandbox has never been read. Both proof documents carry `UNVERIFIED` on every item and
say so on their first line by construction.

**Report:** `docs/readiness/COMPLETION_REPORT.md`

---

*Format note: new entries are appended below the most recent one, most-recent-last, matching normal changelog convention. Do not edit or remove past entries — this file is a record, not a status board.*
