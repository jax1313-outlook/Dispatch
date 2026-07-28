# CIN-Lite User Guide

## What CIN-Lite Does

CIN-Lite is a contract intelligence pipeline for federal opportunities. It:

1. **Acquires** solicitations from SAM.gov (or local sample data)
2. **Analyzes** each contract through 9 deterministic rule modules
3. **Summarizes** findings using Claude AI (with offline fallback)
4. **Recommends** a routing action (pursue, reject, flag, etc.)
5. **Presents** a decision email for human review
6. **Archives** the contract, intelligence, and routing decision
7. **Triggers** a proposal workflow when approved for pursuit

## Installation

### Option A: pip install (recommended)

```bash
git clone https://github.com/jax1313-outlook/cin-hybrid.git
cd cin-hybrid
pip install .                    # core (deterministic mode)
pip install ".[claude]"          # with Claude AI support
pip install ".[dev]"             # with test/dev tools
```

### Option B: Docker

```bash
docker build -t cin-lite .
docker run cin-lite --help
```

### Requirements

- Python 3.11 or later
- No external database (filesystem-based in Phase 1)
- Optional: Anthropic API key for Claude-powered summaries

## Quick Start

### 1. Run with sample data (zero setup)

```bash
cin-lite --action approve_proposal
```

This processes the bundled sample contracts through the full pipeline using
deterministic fallbacks for all external services.

### 2. Check system health

```bash
cin-lite --health
```

Output shows the status of each subsystem:

```
CIN-Lite Health Check
==================================================
  [  OK] sample_data          2 sample file(s)
  [  OK] archive              writable
  [  OK] rule_modules         9 rule module(s) registered
  [  OK] claude_api           not configured (deterministic mode)
  [  OK] smtp                 not configured (offline email mode)
  [  OK] sam_api              not configured (local data mode)

Overall: HEALTHY
```

### 3. View pipeline metrics

```bash
cin-lite --metrics
```

### 4. Interactive mode

```bash
cin-lite
```

Each contract is displayed with its analysis. You choose an action:

- `approve_archive` — archive for reference
- `approve_proposal` — pursue this opportunity (triggers proposal workflow)
- `reject` — decline
- `flag_review` — flag for human review
- `deeper_analysis` — request additional analysis

### 5. Batch mode

```bash
cin-lite --action reject          # reject all
cin-lite --action approve_proposal  # pursue all
```

## Configuration

All configuration is via environment variables. Every integration falls back
gracefully when unconfigured, so the pipeline always runs end-to-end.

### SAM.gov Acquisition (live opportunities)

```bash
export CIN_LITE_SAM_API_KEY=your-api-key    # enables live SAM.gov
export CIN_LITE_SAM_LIMIT=10                # max opportunities (default 10)
export CIN_LITE_SAM_NAICS=541512            # optional NAICS filter
export CIN_LITE_SAM_PTYPE=o                 # optional procurement type
export CIN_LITE_SAM_POSTED_FROM=07/01/2026  # date range start
export CIN_LITE_SAM_POSTED_TO=07/28/2026    # date range end
```

Get a free API key at https://open.gsa.gov/api/get-opportunities-public-api/

### Claude AI (summaries and routing)

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # enables Claude-powered analysis
export CIN_LITE_MODEL=claude-opus-4-8  # optional model override
```

Without a key, the pipeline uses deterministic fallbacks for summaries and
routing decisions.

### SMTP Email Delivery

```bash
export CIN_LITE_SMTP_HOST=smtp.sendgrid.net
export CIN_LITE_SMTP_PORT=587
export CIN_LITE_SMTP_USER=apikey
export CIN_LITE_SMTP_PASSWORD=your-password
export CIN_LITE_SMTP_STARTTLS=1              # default: on
export CIN_LITE_EMAIL_FROM=cin-lite@yourdomain.com
export CIN_LITE_EMAIL_REVIEWER=lead@yourdomain.com
export CIN_LITE_EMAIL_DOMAIN=yourdomain.com
```

Without SMTP configuration, emails are written to `Archive/Outbox/*.eml`.

## Rule Modules

Each contract is analyzed by 9 independent rule modules:

| Module | What It Detects |
|--------|----------------|
| Set-aside detection | SBA set-aside types (8(a), HUBZone, SDVOSB, etc.) |
| NAICS/SIN extraction | NAICS codes and GSA Schedule SINs |
| Pricing anomaly | Missing values, out-of-band estimates, round numbers |
| Past performance | PP requirements, CPARS, recency windows |
| Vendor network | Limited competition, teaming, POC email anomalies |
| Subcontractor dominance | Pass-through risk, limitations on subcontracting |
| JV/MP structure | Joint venture and mentor-protege arrangements |
| Foreign influence | ITAR/EAR, FOCI, Section 889, clearance requirements |
| Cyber compliance | CMMC, NIST 800-171, DFARS, FedRAMP, CUI handling |

Rules are deterministic — same input always produces the same output.

## Archive Structure

Each processed contract is stored under a unique ID (`CIN-YYYYMMDD-XXXXXXXX`):

```
Archive/
  Raw/              original contract data
  Processed/        contract + metadata bundle
  Intelligence/     rule module JSON outputs
  Summaries/        generated summaries
  Routing/          routing decisions (human + agent recommendation)
  Outbox/           unsent emails (offline mode)
  Proposals/        triggered proposal briefs and outlines
```

## Proposal Workflow

When you choose `approve_proposal`, the system automatically:

1. Builds a **proposal brief** with milestones computed from the deadline
2. Generates a **requirements checklist** from rule intelligence
3. Drafts a **proposal outline** (Claude-generated or deterministic fallback)
4. Persists both to `Archive/Proposals/`
5. Emails a **kickoff notice** to the proposal team

## Adding a New Rule Module

1. Create `cin_lite/rules/your_rule.py` with:
   - `NAME = "your_rule_name"`
   - `VERSION = "1.0.0"`
   - `def run(contract: dict) -> RuleResult`
2. Add the module to `ALL_RULES` in `cin_lite/rules/__init__.py`
3. Write tests in `tests/`
4. Keep rules deterministic — no LLM or network calls

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No contracts acquired" | Add JSON files to `cin_lite/sample_data/` or set `CIN_LITE_SAM_API_KEY` |
| Claude summary says "flag(s)" | `ANTHROPIC_API_KEY` not set — using deterministic fallback (expected) |
| Email says "written to..." | `CIN_LITE_SMTP_HOST` not set — emails saved to `Archive/Outbox/` |
| Health check shows FAIL | Run `cin-lite --health` and check the failing component's detail message |
| SAM.gov returns errors | Verify API key at https://api.data.gov; check `CIN_LITE_SAM_POSTED_FROM` format (MM/DD/YYYY) |
