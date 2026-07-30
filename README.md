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

## Tests

```bash
pip install pytest pytest-cov
python -m pytest --cov=cin_lite --cov-report=term-missing --cov-fail-under=90
```

CI runs the suite with coverage on every push and pull request across Python
3.11–3.13 (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Documentation

- **[cin_lite/README.md](cin_lite/README.md)** — full layer-by-layer guide
  (acquisition, rules, agents, control email, archive, proposal workflow).
- **[CLAUDE.md](CLAUDE.md)** — architecture and constraints (authoritative spec).
