# Hybrid — Build Sequence

Ordered by dependency (build a module only after its dependencies). Status
reflects what exists in `cin-hybrid/` / `cin_lite/` today.

**Schema stance: front-load (frozen after Step 2).** All `data_model/` schemas
land at Step 2 and are immutable thereafter. Horizontal landing points for every
`workflows/`, `data_model/`, and `templates/` artifact are pinned in
`landing_points.md`.

## Phase 0 — Foundation
- `config` (JSON: rules, routes, thresholds, whitelist, settings) — **partial** (Email Helper / cin_lite).
- `audit_log` + `archive` (log-before-act, structured folders) — **exists** (cin_lite, logger).
- `ownership_guard` + `IntelligenceOwner` contract — **exists** (cin-hybrid).
- **Exit criteria:** every action is logged before it acts; config loads at runtime.

## Phase 1 — Intake
- `acquisition` (SAM.gov + local fallback) — **exists** (cin_lite).
- `email_intake` (parse/triage/reputation) — **exists** (Email Helper).
- `vendor_profile` (`load_vendor`) — **exists** (cin-hybrid JSONVendorLoader).
- **Exit:** a normalized opportunity and a vendor profile can be produced offline.

## Phase 2 — Eligibility  ⟵ critical path for SDVOSB
- `set_aside_eligibility`: set-aside detection, NAICS/size, subcontracting, JV/MP —
  **partial** (cin_lite rule modules); **VetCert/CVE + size-standard verification NEW.**
- **Exit:** deterministic `eligibility_verdict` with hard/soft blockers; validated in `qa/`.

## Phase 3 — Intelligence
- `engines` (CINRouter + domain engines) — **exists** (cin-hybrid + cin_lite rules).
- `hybrid_intelligence` (summary → scoring → rules → routing) — **exists** (cin-hybrid).
- `HybridOrchestrator` as sole owner — **exists** (cin-hybrid).
- **Exit:** guarded `run_intelligence` returns a unified product incl. eligibility signals.

## Phase 4 — Decision
- `control` (checkbox email, action→route, delivery) — **exists** (cin_lite).
- **Exit:** human decision recorded before any routing; eligibility gate enforced.

## Phase 5 — Generation
- `proposal_packet` (brief, forms, attachments, outline) — **partial** (cin_lite proposal + cin-hybrid packet builder).
- Requires `templates/` (owned elsewhere).
- **Exit:** a reviewable draft packet with a `pdf_path`.

## Phase 6 — Execution
- `signature` (DocuSign send/wait/retrieve) — **exists** (cin-hybrid DocuSignBridge, untested live).
- `submission` (Outlook `send_packet`; portal adapter **NEW**) — **partial**.
- **Exit:** signed packet delivered to target; receipt archived.

## Phase 7 — Orchestration & QA
- `lifecycle` (state machine + orchestration) — **exists** (cin-hybrid HybridLifecycleController + HybridOps).
- `qa/` (unit tests, eligibility evals, end-to-end fixtures) — **partial** (cin_lite pytest suite as pattern).
- **Exit:** one opportunity flows end-to-end acquire→submit with tests green.

## Critical path
```
Phase 0 ─▶ Phase 1 ─▶ Phase 2 (eligibility) ─▶ Phase 3 ─▶ Phase 4 ─▶ Phase 5 ─▶ Phase 6 ─▶ Phase 7
                         ▲ biggest net-new work (VetCert/size verification)
```

## Sequencing notes
- **Eligibility (Phase 2) is the highest-value gap** — most of Phases 1/3/4/6
  already exist in some form; SDVOSB eligibility verification is the least built.
- Build **integration adapters as leaf nodes** so live SAM/DocuSign/portal wiring
  can proceed in parallel without blocking the core.
- Each phase ends with a `qa/` gate before the next begins.
