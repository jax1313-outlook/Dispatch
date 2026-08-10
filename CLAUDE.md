# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Phase 1 is **implemented**. The authoritative specification is
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx` — read it before generating code.
The sections below describe the architecture all code must follow.

`docs/` also now mirrors the platform governance package from `jax1313-outlook/Claude-3` — see the next section before generating code that touches approval, security, Library, or Archive behavior.

## Platform Governance (Claude-3)

This repository's application code operates under the governance package mirrored at `docs/` (refreshed from `jax1313-outlook/Claude-3` — see `docs/README.md`, do not edit those files here). `docs/DISPATCH_CONSTITUTION_v3.md` is the controlling governance law for all Dispatch development work in this repository; if anything below conflicts with it, the Constitution controls until Mike approves a replacement.

**Two different "five layers" — not a conflict, different scope.** The five layers in the Architecture section below (Acquisition / Processing / Control / Archive / Automation) describe *this repository's CIN-Lite contract pipeline* specifically. `docs/DISPATCH_FINAL_BLUEPRINT_v1.md` defines a separate, platform-wide five-layer model (Authority / Presentation / Organizational / Deterministic / Cognitive) that CIN-Lite operates inside, not against. Reconciliation:

| CIN-Lite Layer (this file) | Platform Function (`docs/DISPATCH_FINAL_BLUEPRINT_v1.md`) |
|---|---|
| Acquisition Layer | Intelligence Analyst's Sweepers/Acquisition sub-layer (§7.1) |
| Processing Layer (rule modules) | Intelligence Analyst's Parsing/Scoring sub-layers (§7.1) — deterministic, matches doctrine exactly |
| Control Layer (email decision gate) | Portal-mediated Approval Event (§3, §14) — today authenticates link possession via HMAC token, not an authenticated identity; closing this gap is Stage 7 (Security Foundation) of the Migration Plan |
| Archive Layer | Archive Blueprint (§9) — this layer's SHA-256 fail-closed hash verification already satisfies platform doctrine |
| Automation Layer | Dispatch Spine automation hooks (§10) |

Core platform rules that apply to every layer below, without exception: Mike Zachary is final authority; AI decides nothing (assists, drafts, recommends — never approves, submits, books, or invents facts); Unknown means Unknown (no fabrication). See `docs/DISPATCH_CONSTITUTION_v3.md` §3–4, §10 for the full text.

Full governance detail, including the staged Migration Plan reconciling this codebase against platform doctrine, lives in Claude-3 (`DISPATCH_INTEGRATED_BLUEPRINT_v1.md`, `DISPATCH_REPO_RECONCILIATION_MATRIX_v1.md`, `DISPATCH_STAGE_LAUNCH_PACKAGES_v1.md`) and is not duplicated here.

## What this is

**DISPATCH** is a contract-locating, intelligence-processing, and
archive-building platform. It runs autonomously but keeps a human in the loop: contracts are
acquired, passed through deterministic rule modules that extract intelligence as JSON, then the
user is emailed a checkbox prompt to decide the contract's fate before it is archived or routed.
It is deliberately lightweight and modular, intended to expand later into the full "CIN" and "AZP"
platforms.

## Architecture (subsystem boundaries are load-bearing)

Code must respect these five layers — keep their responsibilities separate:

1. **Acquisition Layer** — fetches contracts from designated sources.
2. **Processing Layer** — applies rule modules to extract intelligence.
3. **Control Layer** — email-based approval/rejection/routing (the human decision gate).
4. **Archive Layer** — stores structured outputs and raw files.
5. **Automation Layer** — orchestrates acquisition → processing → email → archive.

Data flow: `acquire → process (rule modules) → email user with checkboxes → user selects action →
archive / route / escalate`.

### Rule module framework

Each rule module is a **standalone logic unit** that outputs **structured JSON** for downstream use.
Rules must be **deterministic** (no nondeterministic LLM calls inside the deterministic rule path).
Specified modules: set-aside detection, NAICS/SIN extraction, past-performance relevance, pricing
anomalies, vendor network indicators, subcontractor dominance, JV/MP structure flags, foreign
influence indicators, cyber compliance readiness. Add new rules as separate modules — do not fold
logic into a monolith.

### Email control system

Checkbox-driven HTML email interface. The five actions are: Approve for archive, Approve for
proposal, Reject, Flag for review, Request deeper analysis. Each action renders as a styled
button linking to the portal's decision endpoint (`/api/decision/<id>/<action>?token=…`).
Tokens are HMAC-SHA256 signed. Keep this logic **clean and deterministic** — the email response
maps directly to an archive/routing action.

Flow: pipeline stores a pending decision → sends HTML email → reviewer clicks action →
portal archives + routes → confirmation page.

### Archive structure

Each contract gets a unique ID and a full metadata bundle. Folder layout:

```
/Archive
  /Raw            raw fetched files
  /Processed      processed contract data
  /Intelligence   rule-module JSON outputs
  /Summaries      generated summaries
  /Routing        routing decisions
  /Pending        decisions awaiting reviewer action (transient)
```

## Tech stack

- Python 3.11
- Local filesystem (no external DB in Phase 1)
- Claude API (intelligence extraction / summarization / routing-decision agents — the *non*-deterministic helpers)
- Email API (control system)
- Automation platform: n8n or equivalent

## Constraints (do not violate)

- Must remain lightweight.
- Must be locally controllable.
- Must support future expansion into full CIN.
- Rule logic must remain deterministic.

## Roadmap

- **Phase 1 (current):** DISPATCH acquisition, rule modules, email control system, archive engine.
- **Phase 2:** proposal-trigger workflows, deeper intelligence modules.
- **Phase 3:** integrate into full CIN, add AZP compatibility.

## Rules for code generation (from the architecture doc)

- Follow subsystem boundaries.
- Maintain the archive folder structure.
- Use modular rule files (one concern per module).
- Keep email control logic clean and deterministic.
- Support future expansion.
