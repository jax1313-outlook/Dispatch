# Hybrid CIN-Lite System

[![CI](https://github.com/jax1313-outlook/cin-hybrid/actions/workflows/ci.yml/badge.svg)](https://github.com/jax1313-outlook/cin-hybrid/actions/workflows/ci.yml)

A contract-locating, intelligence-processing, and archive-building platform for
federal opportunities. It acquires solicitations, runs deterministic rule modules
that extract intelligence as JSON, emails a human a checkbox decision, and
archives or routes the result — with Claude agents handling the non-deterministic
helpers (summarization, routing recommendation, proposal drafting).

```
acquire (SAM.gov) -> process (9 rule modules) -> summarize + recommend route
        -> control email -> human decides -> archive + route + email
        -> [if approved for proposal] proposal-trigger workflow
```

## Quick start

Runs with zero setup on bundled sample data; configure environment variables to
switch on the real integrations (each falls back gracefully when unconfigured).

```bash
python -m cin_lite.run --action approve_proposal   # non-interactive demo
python -m cin_lite.run                              # interactive
```

## L2-COS Operations Portal v1

Local-first operations cockpit combining SAM/government contract and
Dispatch/load board workflows into one unified portal.

```bash
pip install -r portal/requirements.txt
python portal/app.py
# Opens at http://127.0.0.1:8080
```

On Windows/PowerShell: `.\run_portal.bat`

## Tests

```bash
pip install pytest pytest-cov flask
python -m pytest --cov=cin_lite --cov-report=term-missing --cov-fail-under=90
```

CI runs the suite with coverage on every push and pull request across Python
3.11–3.13 (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Pipeline API

The portal exposes a JSON API at `/api/pipeline/` for external automation
(n8n, cron, webhooks). Key endpoints:

```bash
curl -X POST http://127.0.0.1:8080/api/pipeline/run          # trigger pipeline
curl http://127.0.0.1:8080/api/pipeline/pending               # list pending decisions
curl -X POST http://127.0.0.1:8080/api/pipeline/decide \
  -H 'Content-Type: application/json' \
  -d '{"contract_id":"CIN-...","action":"approve_archive"}'   # decide
curl http://127.0.0.1:8080/api/pipeline/archive               # browse archive
```

See **[cin_lite/README.md](cin_lite/README.md)** for the full API reference and
n8n integration guide.

## Documentation

- **[cin_lite/README.md](cin_lite/README.md)** — full layer-by-layer guide
  (acquisition, rules, agents, control email, archive, proposal workflow,
  API reference, n8n integration).
- **[CLAUDE.md](CLAUDE.md)** — architecture and constraints (authoritative spec).
