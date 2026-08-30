# DISPATCH

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

### Doctrine

Governing principles. Binding on all code in this repository.

- **[Deterministic Chassis](docs/DISPATCH_DETERMINISTIC_CHASSIS.md)** — the five stages
  (filter, score, sort, recommendation, decision) and why they never merge.
- **[System Independence](docs/DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md)** — Dispatch
  remains operable when every external system is down.
- **[Configurable Business Policy](docs/DISPATCH_CONFIGURABLE_BUSINESS_POLICY_DOCTRINE.md)** —
  Dispatch owns the engine; the operator owns the settings.
- **[Fact and Provenance](docs/DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md)** — no
  fabrication; every fact carries its origin; UNKNOWN is a value.
- **[State Transition Rules](docs/DISPATCH_STATE_TRANSITION_RULES.md)** — one record, one
  identity; atomic human gates.
- **[Capacity Plan Doctrine](docs/DISPATCH_CAPACITY_PLAN_DOCTRINE.md)** — day plans stay
  recommendations until a human approves; locking is not immutability; the BOOK IT DANO
  rule.
- **[Accessorial Policy Doctrine](docs/DISPATCH_ACCESSORIAL_POLICY_DOCTRINE.md)** —
  accessorials are versioned Company Library policies, not application settings; the
  detention formula and its approval workflow.
- **[External Adapter Boundaries](docs/DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md)** — the
  UNAVAILABLE contract, and what an adapter may never do.

### Lineage recovery

Findings from the recovered L1-COS v1 lineage (v1.0 / v1.0.1 / v1.1 / v1.3 / v1.3.1 /
v1.3.3 / v1.3.2 GOLD). **No single v1 build is complete** — Dispatch inherits the
constitution, the business matrix and the workflow chassis from different builds.

- **[Recovery Findings](docs/DISPATCH_GOLD_RECOVERY_FINDINGS.md)** — what each build
  holds, what GOLD gained, and what it cost.
- **[Scoring Lineage and Recovery](docs/DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md)** — the
  history of the score, and three regressions in current Dispatch.
- **[Component Recovery Register](docs/DISPATCH_COMPONENT_RECOVERY_REGISTER.md)** — 61
  components: source, status, action.
- **[Aggressive Build Sequence](docs/DISPATCH_AGGRESSIVE_BUILD_SEQUENCE.md)** — the order
  of work, and why it is that order.

### Policy foundation

Specification only. Not implemented.

- **[Policy Profile Spec](docs/DISPATCH_POLICY_PROFILE_SPEC.md)**
- **[Load Arrangement Spec](docs/DISPATCH_LOAD_ARRANGEMENT_SPEC.md)** — load, stops, cargo,
  utilization, accessorials.
- **[Evaluation Engine Spec](docs/DISPATCH_EVALUATION_ENGINE_SPEC.md)**
- **[Decision Matrix Spec](docs/DISPATCH_DECISION_MATRIX_SPEC.md)**
- **[Filter / Score / Sort Spec](docs/DISPATCH_FILTER_SCORE_SORT_SPEC.md)**
- **[Recommendation Model Spec](docs/DISPATCH_RECOMMENDATION_MODEL_SPEC.md)**
- **[Confidence Model Spec](docs/DISPATCH_CONFIDENCE_MODEL_SPEC.md)**
- **[Override Rules Spec](docs/DISPATCH_OVERRIDE_RULES_SPEC.md)**
- **[Policy Profile Examples](docs/DISPATCH_POLICY_PROFILE_EXAMPLES.md)**
- **[Policy Foundation PR Summary](docs/DISPATCH_POLICY_FOUNDATION_PR_SUMMARY.md)**
