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

```bash
pip install .                              # core (deterministic mode)
pip install ".[claude]"                    # with Claude AI support

cin-lite --health                          # verify installation
cin-lite --action approve_proposal         # non-interactive demo
cin-lite                                   # interactive mode
cin-lite --metrics                         # view pipeline metrics
```

Runs with zero setup on bundled sample data; configure environment variables to
switch on the real integrations (each falls back gracefully when unconfigured).

## Tests

```bash
pip install ".[dev]"
python -m pytest --cov=cin_lite --cov-report=term-missing --cov-fail-under=90
```

280 tests, 100% code coverage. CI runs the suite on every push and pull request
across Python 3.11–3.13 (see [.github/workflows/ci.yml](.github/workflows/ci.yml)).

## Docker

```bash
docker build -t cin-lite .
docker run cin-lite --health
docker run cin-lite --action approve_proposal
```

## Documentation

- **[User Guide](docs/user-guide.md)** — installation, configuration, rule modules, archive structure, proposal workflow, troubleshooting.
- **[Deployment Guide](docs/deployment.md)** — pip, Docker, Docker Compose, cron, systemd, environment variables reference, security.
- **[Operations Guide](docs/operations.md)** — monitoring, logging, health checks, metrics, scalability, backup/recovery, incident response.
- **[cin_lite/README.md](cin_lite/README.md)** — layer-by-layer technical reference.
- **[CLAUDE.md](CLAUDE.md)** — architecture and constraints (authoritative spec).
