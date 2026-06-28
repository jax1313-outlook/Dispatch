# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repository is in the **planning stage**. The authoritative specification is
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx` — read it before generating code.
There is no application code yet; the sections below describe the architecture all code must follow.

## What this is

The **Hybrid CIN-Lite System** is a contract-locating, intelligence-processing, and
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

Checkbox-driven email interface. The five actions are: Approve for archive, Approve for proposal,
Reject, Flag for review, Request deeper analysis. Keep this logic **clean and deterministic** — the
email response maps directly to an archive/routing action.

### Archive structure

Each contract gets a unique ID and a full metadata bundle. Folder layout:

```
/Archive
  /Raw            raw fetched files
  /Processed      processed contract data
  /Intelligence   rule-module JSON outputs
  /Summaries      generated summaries
  /Routing        routing decisions
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

- **Phase 1 (current):** CIN-Lite acquisition, rule modules, email control system, archive engine.
- **Phase 2:** proposal-trigger workflows, deeper intelligence modules.
- **Phase 3:** integrate into full CIN, add AZP compatibility.

## Rules for code generation (from the architecture doc)

- Follow subsystem boundaries.
- Maintain the archive folder structure.
- Use modular rule files (one concern per module).
- Keep email control logic clean and deterministic.
- Support future expansion.
