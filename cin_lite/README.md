# CIN-Lite — Technical Reference

A runnable implementation of the Hybrid CIN-Lite pipeline described in
`../Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`. Runs with zero setup
on bundled sample data; configure environment variables to switch on the real
integrations (SAM.gov acquisition, Claude summarization + routing, SMTP delivery).
Each integration falls back gracefully when unconfigured, so it always runs
end-to-end.

## Run it

```bash
pip install .                                     # install as CLI
cin-lite                                          # interactive mode
cin-lite --action approve_proposal                # non-interactive
cin-lite --list-actions                           # show the five control actions
cin-lite --health                                 # system health check
cin-lite --metrics                                # pipeline run history
```

Each run flows one or more contracts through:

```
acquire -> process (rule modules) -> summarize + recommend route
        -> control email -> human decides -> archive + route + email
        -> [if approved for proposal] proposal-trigger workflow
```

and writes artifacts into `Archive/{Raw,Processed,Intelligence,Summaries,Routing}/`,
one file per contract, keyed by a unique ID like `CIN-20260627-D0ED1187`.

## Layout (maps 1:1 to the architecture layers)

| File | Layer | Responsibility |
|------|-------|----------------|
| `acquisition.py` | Acquisition | Fetches opportunities from SAM.gov (falls back to `sample_data/`) |
| `rules/` + `processing.py` | Processing | Deterministic rule modules -> JSON intelligence |
| `agents/summarizer.py` | Processing (non-deterministic) | Claude-backed contract summary |
| `agents/router.py` | Processing (non-deterministic) | Claude-backed routing recommendation |
| `agents/proposal_writer.py` | Processing (non-deterministic) | Claude-backed proposal outline |
| `workflows/proposal.py` | Automation (Phase 2) | Proposal-trigger workflow |
| `control.py` | Control | Renders checkbox email; maps action -> route |
| `email_delivery.py` | Control | Sends the decision + summary as outbound email (SMTP) |
| `archive.py` | Archive | Unique ID, metadata bundle, folder-tree persistence |
| `metrics.py` | Operations | Pipeline run metrics (JSONL persistence) |
| `health.py` | Operations | System health checks (6 subsystems) |
| `log_config.py` | Operations | Structured logging with rotation |
| `run.py` | Automation | Orchestrates the above end-to-end |

## Tests

280 tests at 100% code coverage. From the project root:

```bash
pip install ".[dev]"
python -m pytest --cov=cin_lite --cov-report=term-missing --cov-fail-under=90
```

CI runs the suite with coverage on every push and pull request across Python
3.11–3.13 — see `../.github/workflows/ci.yml`.

Coverage includes: all nine rule modules (positive + negative + determinism), the
summarization and routing agents (deterministic fallback and the Claude code path
via an injected fake `anthropic`), the proposal-trigger workflow, the archive
layer, control email / SMTP delivery (offline `.eml` plus faked SMTP
success/failure), pipeline metrics, health checks, integration/e2e tests, and
performance benchmarks.

## Add a rule

Create `rules/your_rule.py` exposing `NAME`, `VERSION`, and `run(contract) -> RuleResult`,
then append the module to `ALL_RULES` in `rules/__init__.py`. Nothing else changes.
Keep rules deterministic (no LLM/network in the rule path).

## Acquisition source — SAM.gov

`acquisition.py` pulls live opportunities from the SAM.gov Opportunities API and
maps each into the pipeline's contract shape (set-aside, NAICS/SIN, description,
response date). Uses stdlib `urllib` — no extra dependency.

Get a free key at <https://open.gsa.gov/api/get-opportunities-public-api/>, then:

```bash
export CIN_LITE_SAM_API_KEY=...
export CIN_LITE_SAM_LIMIT=10
cin-lite --action approve_proposal
```

When the key is unset — or a request fails — it falls back to local
`sample_data/*.json`, so the zero-setup demo still runs.

## Summarization agent (Claude)

`agents/summarizer.py` is the Claude summarization agent (one Messages API call
via the `anthropic` SDK). Enable it:

```bash
pip install ".[claude]"
export ANTHROPIC_API_KEY=sk-ant-...
cin-lite --action approve_proposal
```

Without an API key (or without the `anthropic` package), it falls back to a
deterministic summary. Override the model with `CIN_LITE_MODEL`.

## Routing-decision agent (Claude)

`agents/router.py` consumes rule intelligence plus the summary and produces a
structured routing recommendation (`action, reason, priority, recipient, notes`).
Uses structured outputs (JSON schema) to guarantee the shape; falls back to an
auditable rule-based decision when Claude is unavailable.

## Proposal-trigger workflow

When the human action is `approve_proposal`, `workflows/proposal.py` fires
automatically. It builds a proposal brief with milestones, a requirements
checklist, and a proposal outline (Claude or deterministic fallback), persists
both to `Archive/Proposals/`, and emails a kickoff notice.

## Outbound email delivery (SMTP)

`email_delivery.py` sends each contract's summary + routing decision via
stdlib `smtplib`. Enable with:

```bash
export CIN_LITE_SMTP_HOST=smtp.sendgrid.net
export CIN_LITE_SMTP_PORT=587
export CIN_LITE_SMTP_USER=apikey
export CIN_LITE_SMTP_PASSWORD=...
export CIN_LITE_EMAIL_FROM=cin-lite@yourdomain.com
export CIN_LITE_EMAIL_REVIEWER=lead@yourdomain.com
export CIN_LITE_EMAIL_DOMAIN=yourdomain.com
```

When unconfigured, emails are written to `Archive/Outbox/<id>.eml`.

## Pipeline metrics

Every pipeline run records structured JSON to `logs/metrics/pipeline.jsonl`:
contracts acquired/processed, action distribution, timing, errors.

```bash
cin-lite --metrics
```

## Health checks

Six subsystem checks: sample data, archive, rule modules, Claude API, SMTP, SAM.gov.

```bash
cin-lite --health
```

Returns exit code 0 (healthy) or 1 (degraded).
