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
python -m pytest --cov=cin_lite --cov=l2_cos --cov-report=term-missing --cov-fail-under=90
```

CI runs the suite with coverage on every push and pull request across Python
3.11–3.13 (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

## L2-COS (Dispatch)

`l2_cos/` is a clone-and-repurpose of the cin_lite pipeline (Rule 15: reuse
the deterministic rule-module pattern rather than redesigning it) for freight
dispatch instead of federal contracts:

```
acquire (load board) -> look up Location/Broker intelligence (capture once)
        -> process (6 dispatch rule modules) -> dispatch control email
        -> human confirms stage -> archive + advance the 11-stage lifecycle
        -> [if Intelligence Score >= 90] publisher/auto-contact workflow
```

```bash
python -m l2_cos.run --action BOOKED   # non-interactive demo
python -m l2_cos.run                    # interactive
```

See **[l2_cos/README.md](l2_cos/README.md)** for the full layer-by-layer guide.

## Documentation

- **[cin_lite/README.md](cin_lite/README.md)** — full layer-by-layer guide
  (acquisition, rules, agents, control email, archive, proposal workflow).
- **[l2_cos/README.md](l2_cos/README.md)** — L2-COS Dispatch layer-by-layer guide.
- **[CLAUDE.md](CLAUDE.md)** — architecture and constraints (authoritative spec).
