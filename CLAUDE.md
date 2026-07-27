# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Two systems now live in this repository:

- **`cin_lite/`** — the CIN-Lite pipeline described below, fully implemented with a deterministic
  test suite (see `cin_lite/README.md`).
- **`l2_cos/`** — a clone-and-repurpose of the cin_lite pipeline for freight dispatch instead of
  federal contracts, including an Operations Portal UI (see `l2_cos/README.md` and the "L2-COS
  (Dispatch)" section below).

The authoritative specification for **cin_lite** is
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx` — read it before changing that
subsystem's architecture. The sections below, through "Rules for code generation," describe
cin_lite specifically; see "L2-COS (Dispatch)" at the end of this file for the second system.

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

## L2-COS (Dispatch)

A clone-and-repurpose of the cin_lite pipeline (`l2_cos/`) for freight dispatch. Same five-layer
shape (acquisition → processing/rules → control → archive → automation) as cin_lite above, plus:

- **State model lock** — `Load.stage` (`l2_cos/models/state.py`) is one of 11 stages: Available →
  Booked → Planned → En Route → At Pickup → Loaded → In Transit → At Delivery → Delivered →
  Invoiced → Closed. Transitions are forward-only, one stage at a time; `Load.advance()` raises on
  any skip or reversal.
- **Operational Intelligence Libraries** — `LocationIntelligence` and `BrokerIntelligence`
  (`l2_cos/models/intelligence.py`) are captured once (`l2_cos/intelligence_store.py`) and reused
  across the rule modules, the publisher workflow, and the dashboard, rather than re-derived per
  load.
- **Publisher / auto-contact workflow** (`l2_cos/workflows/publisher.py`) — the one workflow that
  fires without a human decision gate: once a load's overall rule-module score reaches
  `PUBLISH_THRESHOLD` (90), it emails the broker automatically if the carrier's `InquiryArtifacts`
  packet is complete.
- **Sandbox hold duration** — `SANDBOX_HOLD_HOURS = 3` (`l2_cos/ui/sandbox.py`) is the default hold
  period the Operations Portal uses to track a published load before flagging it
  `expiring_soon` / `expired`. It's a configurable constant, not a fixed architectural invariant —
  change it in that one file if the real operating hold period differs.

### Operations Portal (local UI)

A FastAPI/HTML dashboard (`l2_cos/ui/`) over the Archive (the system of record): Cards — with the
`✅ HIGH VALUE MATCH | Score ##` badge and a 🟥/🟩 risk indicator driven by the two Intelligence
Libraries — link through to a Brief, Draft, and raw Source per load, plus Location/Broker library
views, Publisher Alerts & Sandbox Tracking, and manual Lifecycle stage controls.

Run it locally:

```bash
pip install -r l2_cos/requirements.txt
uvicorn l2_cos.ui.app:app --reload
```

Then open <http://127.0.0.1:8000/>. `--reload` is for local development only. There is no
authentication layer yet — do not expose this beyond localhost without adding one, since the
Lifecycle controls can advance a load's stage with no login required.

### Tests

```bash
pip install pytest pytest-cov
python -m pytest --cov=cin_lite --cov=l2_cos --cov-report=term-missing --cov-fail-under=90
```

See `l2_cos/README.md` for the full layer-by-layer guide.
