# CIN-Lite — Phase 1 skeleton

A runnable implementation of the Hybrid CIN-Lite pipeline described in
`../Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`. Runs with zero setup
on bundled sample data; configure environment variables to switch on the real
integrations (SAM.gov acquisition, Claude summarization + routing, SMTP delivery).
Each integration falls back gracefully when unconfigured, so it always runs
end-to-end. Only the Claude agents need a third-party package (`anthropic`);
everything else is stdlib.

## Run it

From the **project root** (`D:\Hybrid\Hybrid Calude`):

```bash
python -m cin_lite.run                       # interactive: choose an action per contract
python -m cin_lite.run --action approve_proposal   # non-interactive (applies to all)
python -m cin_lite.run --list-actions        # show the five control actions
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
| `run.py` | Automation | Orchestrates the above end-to-end |

## Tests

A deterministic pytest suite lives in `../tests/` (71 tests, ~96% coverage). From
the project root:

```bash
pip install pytest pytest-cov
python -m pytest                                  # just the tests
python -m pytest --cov=cin_lite --cov-report=term-missing --cov-fail-under=90
```

CI runs the suite with coverage on every push and pull request across Python
3.11–3.13 — see `../.github/workflows/ci.yml` (coverage config in `../.coveragerc`,
threshold 90%).

Coverage: all nine rule modules (positive + negative + determinism), the
summarization and routing agents (deterministic fallback **and** the Claude code
path via an injected fake `anthropic`), the proposal-trigger workflow, the archive
layer, and the control email / SMTP delivery (offline `.eml` plus faked SMTP
success/failure). Fixtures (`tests/conftest.py`) provide sample SAM.gov
opportunities; every test scrubs integration env vars and redirects archive/email
writes to a tmp dir, so the suite is offline, deterministic, and side-effect-free.

## Add a rule

Create `rules/your_rule.py` exposing `NAME`, `VERSION`, and `run(contract) -> RuleResult`,
then append the module to `ALL_RULES` in `rules/__init__.py`. Nothing else changes.
Keep rules deterministic (no LLM/network in the rule path).

## What's mocked (and where real services plug in later)

- **Control** renders the checkbox email to console/text and reads the human's
  choice from the CLI (the *inbound* decision). Outbound delivery is real (SMTP,
  below); the `action -> route` mapping is real.

## Acquisition source — SAM.gov (real)

`acquisition.py` pulls live opportunities from the SAM.gov Opportunities API and
maps each into the pipeline's contract shape (set-aside, NAICS/SIN, description,
response date), so real solicitations flow through every rule module. Uses stdlib
`urllib` — no extra dependency.

Get a free key at <https://open.gsa.gov/api/get-opportunities-public-api/> (an
api.data.gov key), then:

```bash
export CIN_LITE_SAM_API_KEY=...           # presence switches acquisition to SAM.gov
export CIN_LITE_SAM_LIMIT=10              # max opportunities (default 10)
export CIN_LITE_SAM_NAICS=541512         # optional NAICS filter
export CIN_LITE_SAM_PTYPE=o              # optional procurement-type filter
python -m cin_lite.run --action approve_proposal
```

By default it pulls the last 7 days (override with `CIN_LITE_SAM_POSTED_FROM` /
`CIN_LITE_SAM_POSTED_TO`, `MM/DD/YYYY`). When the key is unset — or a request
fails — it falls back to local `sample_data/*.json`, so the zero-setup demo still
runs. Note: SAM solicitations rarely publish an estimated value, so a missing
value is treated as informational (not a routing anomaly).

## Phase 2 — proposal-trigger workflow

When the human action is **`approve_proposal`**, `workflows/proposal.py` fires
automatically (Automation Layer). It:

1. Builds a deterministic **proposal brief** — internal milestones computed
   backward from the response deadline (kickoff / draft / review / submit), a
   requirements checklist derived from the rule intelligence (set-aside,
   NAICS/SIN, each cyber framework, bid/no-bid sign-off), priority, and team.
2. Drafts a **proposal outline** via the Claude proposal-writer agent
   (`agents/proposal_writer.py`), with a deterministic standard-GovCon outline as
   fallback.
3. Persists both to `Archive/Proposals/<proposal_id>.{json,md}`.
4. Emails a **kickoff** to the proposal team (reuses the SMTP transport; `.eml`
   fallback offline).

Only `approve_proposal` triggers it; the other four actions do not.

## Summarization agent (Claude — real)

`agents/summarizer.py` is the live Claude summarization agent (one Messages API
call via the `anthropic` SDK, model `claude-opus-4-8`). Rules stay deterministic;
this is the non-deterministic helper that sits outside the rule path.

Enable it:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python -m cin_lite.run --action approve_proposal
```

Without an API key (or without the `anthropic` package), it falls back to a
deterministic summary so the pipeline still runs end-to-end offline. Override the
model with `CIN_LITE_MODEL`.

## Routing-decision agent (Claude — real)

`agents/router.py` consumes all four rule modules' intelligence plus the summary
and produces a structured **routing_decision** recommendation:

```
{ action, reason, priority, recipient, notes }
```

`action` is one of the Control Layer's five action keys. The Claude path uses
**structured outputs** (a JSON schema) to guarantee the shape; it falls back to an
auditable rule-based decision when Claude is unavailable.

This is a *recommendation* — the human still decides. The recommendation is shown
in the control email (marked `<- recommended`; an empty interactive reply accepts
it), and the archive's `Routing/<id>.json` stores both the recommendation and the
human's final action plus a `followed_recommendation` audit flag.

## Outbound email delivery (SMTP — real)

`email_delivery.py` sends each contract's **summary + routing decision** as a real
outbound email via stdlib `smtplib`, so it works with any provider's SMTP relay
(SendGrid, Amazon SES, Mailgun, Postmark, Gmail, …). The email goes to the reviewer
and to the routing queue's address (`<queue>@<domain>`, unless the recipient is
`none`).

Enable it with environment variables:

```bash
export CIN_LITE_SMTP_HOST=smtp.sendgrid.net   # presence enables real sending
export CIN_LITE_SMTP_PORT=587                  # default 587
export CIN_LITE_SMTP_USER=apikey
export CIN_LITE_SMTP_PASSWORD=...              # provider credential
export CIN_LITE_EMAIL_FROM=cin-lite@yourdomain.com
export CIN_LITE_EMAIL_REVIEWER=lead@yourdomain.com
export CIN_LITE_EMAIL_DOMAIN=yourdomain.com    # for queue recipient addresses
```

PowerShell: `$env:CIN_LITE_SMTP_HOST="smtp.sendgrid.net"` (etc.). STARTTLS is on by
default; set `CIN_LITE_SMTP_STARTTLS=0` to disable.

When `CIN_LITE_SMTP_HOST` is unset — or a send fails — the composed message is
written to `Archive/Outbox/<id>.eml` (a standard RFC-822 file) and the pipeline
continues. This keeps the offline, zero-setup path intact.
