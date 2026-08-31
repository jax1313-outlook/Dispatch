# Dispatch

[![CI](https://github.com/jax1313-outlook/Dispatch/actions/workflows/ci.yml/badge.svg)](https://github.com/jax1313-outlook/Dispatch/actions/workflows/ci.yml)

**Dispatch** is the freight-operations platform of Level 1 Transport — a small
owner-operator trucking business. It exists to reduce the owner/operator's cognitive load:
see what is true now, lay out what could become true, let a human choose, then help execute
the mission that was chosen.

It also carries a second, smaller program: **CIN-Lite**, a government-contracting pipeline
that acquires solicitations, runs deterministic rule modules over them, and emails a human a
checkbox decision. CIN-Lite is additionally Dispatch's only mail transport.

> **New here? Read [`CLAUDE.md`](CLAUDE.md) first.** It is the cold-start brief: program,
> mission, authority, boundaries, working rules, and current build status — written so
> somebody arriving with no prior context can be useful in one reading.

---

## Status

`0.1.0` · suite green on Python 3.11–3.13 · **nothing has been run on the target machine.**

Everything in this repository is `IMPLEMENTED`. **Nothing is `OPERATIONALLY PROVEN`** — the
distinction is load-bearing here and is explained in
[`docs/readiness/OPERATIONAL_PROOF.md`](docs/readiness/OPERATIONAL_PROOF.md). The repository
test suite is evidence of software behaviour, never of operational deployment.

Current gaps, assumptions and the next blocker:
[`docs/readiness/KNOWN_LIMITATIONS.md`](docs/readiness/KNOWN_LIMITATIONS.md).

---

## Never run Dispatch before? Start here

**[docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md](docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md)**
— install Python, download this repository, put it in `C:\Dispatch`, double-click one file.
Written for somebody who is not a developer, including the Windows warnings you will hit on
the way (SmartScreen will stop you once; the guide says what to click).

## Running it

**On Windows** — double-click **`DISPATCH_START_HERE.cmd`**. That is the whole answer. It
creates this machine's security settings, installs Flask if it is missing, starts Dispatch,
opens your browser, and puts a Dispatch icon on your Desktop so you never have to open this
folder again.

`dispatch.bat` opens the Control Center menu instead — Start, Stop, Restart, Settings,
Version, Reset Session. Use it once Dispatch is working.

[`docs/readiness/LAUNCH_PATH.md`](docs/readiness/LAUNCH_PATH.md) is the evidence for both:
every launcher in the repository, which are current, which are superseded, and the exact
output each produces.
[`DISPATCH_FIRST_START_GUIDE.md`](DISPATCH_FIRST_START_GUIDE.md) covers a first start in detail.

**From a shell:**

```bash
pip install flask                      # the only hard dependency
python -m dispatch_launcher status     # what this machine is configured with
python -m dispatch_launcher start      # start Dispatch
python portal/app.py                   # or start the portal directly
```

Opens at `http://127.0.0.1:8080`.

**CIN-Lite, on bundled sample data:**

```bash
python -m cin_lite.run --action approve_proposal   # non-interactive demo
python -m cin_lite.run                              # interactive
```

## Tests

```bash
pip install pytest pytest-cov flask
python -m pytest -q
```

CI runs the suite with coverage on every push and pull request across Python 3.11–3.13
(see [.github/workflows/ci.yml](.github/workflows/ci.yml)). The gate is 90% over
`cin_lite`, `dispatch` and `portal`. The suite must stay at **0 failed / 0 skipped /
0 warnings**.

## Pipeline API

The portal exposes a JSON API at `/api/pipeline/` for external automation (n8n, cron,
webhooks):

```bash
curl -X POST http://127.0.0.1:8080/api/pipeline/run          # trigger pipeline
curl http://127.0.0.1:8080/api/pipeline/pending               # list pending decisions
curl -X POST http://127.0.0.1:8080/api/pipeline/decide \
  -H 'Content-Type: application/json' \
  -d '{"contract_id":"CIN-...","action":"approve_archive"}'   # decide
curl http://127.0.0.1:8080/api/pipeline/archive               # browse archive
```

---

## Documentation

The repository has a lot of documents. These are the ones that bind — everything else is
history, and [`docs/architecture/DISPATCH_ARCHITECTURE.md`](docs/architecture/DISPATCH_ARCHITECTURE.md) §1
is the full map.

| | |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Start here.** Cold-start brief |
| [`DISPATCH_PURPOSE_STATEMENT.md`](DISPATCH_PURPOSE_STATEMENT.md) | Why Dispatch exists; the guiding principles |
| [`DRIVER_FIRST_DOCTRINE_v2.md`](DRIVER_FIRST_DOCTRINE_v2.md) | D1–D15, including the 70 MPH Test |
| [`DECISION_LOG.md`](DECISION_LOG.md) | Every decision, in order. Authority of last resort |
| [`docs/architecture/DISPATCH_ARCHITECTURE.md`](docs/architecture/DISPATCH_ARCHITECTURE.md) | Subsystems, data flow, boundaries, document map |
| [`docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md`](docs/governance/DISPATCH_AUTHORITY_AND_BOUNDARIES.md) | Who decides what; what software may never do |
| [`DISPATCH_FIRST_START_GUIDE.md`](DISPATCH_FIRST_START_GUIDE.md) | Never started it before |
| [`docs/operations/DISPATCH_OPERATOR_GUIDE.md`](docs/operations/DISPATCH_OPERATOR_GUIDE.md) | Day-to-day operation |
| [`docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md`](docs/maintenance/DISPATCH_MAINTENANCE_GUIDE.md) | Backups, restores, upgrades, moving machines |
| [`docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md`](docs/operations/GET_DISPATCH_ONTO_YOUR_LAPTOP.md) | **Step one.** Getting Dispatch onto a Windows laptop from scratch |
| [`docs/readiness/LAUNCH_PATH.md`](docs/readiness/LAUNCH_PATH.md) | What to click, and why that file |
| [`docs/readiness/OPERATIONAL_PROOF.md`](docs/readiness/OPERATIONAL_PROOF.md) | What is proven, and what is not |
| [`docs/readiness/KNOWN_LIMITATIONS.md`](docs/readiness/KNOWN_LIMITATIONS.md) | What is broken, missing or assumed |
| [`docs/connectors/PROVIDER_INSERTION.md`](docs/connectors/PROVIDER_INSERTION.md) | Adding an external provider |
| [`docs/DISPATCH_CAPACITY_PLAN_DOCTRINE.md`](docs/DISPATCH_CAPACITY_PLAN_DOCTRINE.md) | Day plans stay recommendations; locking is not immutability; BOOK IT DANO |
| [`docs/DISPATCH_ACCESSORIAL_POLICY_DOCTRINE.md`](docs/DISPATCH_ACCESSORIAL_POLICY_DOCTRINE.md) | Accessorials are versioned Library policies, not settings |
| [`cin_lite/README.md`](cin_lite/README.md) | CIN-Lite, layer by layer |

---

## Two things to know before changing anything

**Mike Zachary is the final authority.** Software, automation and AI in this repository hold
zero decision authority. No record may claim he verified, approved, accepted, authorized or
confirmed anything unless he personally performed an authenticated action that produced it —
not as a default, a seed, or a test fixture.

**Status words are fixed.** `LIVE`, `CONFIGURED`, `UNCONFIGURED`, `SIMULATED`, `UNAVAILABLE`,
`MANUAL`, `ABSENT`, `UNVERIFIED`. No synonyms, no invented variants — several modules
validate this and will raise on one.

### Lineage recovery and the evaluation foundation

Recovered from the L1-COS v1 lineage (v1.0 / v1.0.1 / v1.1 / v1.3 / v1.3.1 / v1.3.3 /
v1.3.2 GOLD) and specified against it. **No single v1 build is complete** — Dispatch inherits
the constitution, the business matrix and the workflow chassis from different builds.

[Sweep and the opportunity board](docs/DISPATCH_SWEEP_AND_OPPORTUNITY_BOARD.md) — settled
design direction for the Operations Portal: qualified opportunities, not freight listings.

Acceptance criteria the engine is built against and judged by:
[scoring acceptance criteria](docs/DISPATCH_SCORING_ACCEPTANCE_CRITERIA.md) — fifteen
categories, three of them hard stops.

Findings: [recovery findings](docs/DISPATCH_GOLD_RECOVERY_FINDINGS.md) ·
[scoring lineage](docs/DISPATCH_SCORING_LINEAGE_AND_RECOVERY.md) ·
[component register](docs/DISPATCH_COMPONENT_RECOVERY_REGISTER.md) (61 entries) ·
[build sequence](docs/DISPATCH_AGGRESSIVE_BUILD_SEQUENCE.md)

Doctrine: [deterministic chassis](docs/DISPATCH_DETERMINISTIC_CHASSIS.md) ·
[system independence](docs/DISPATCH_SYSTEM_INDEPENDENCE_DOCTRINE.md) ·
[configurable business policy](docs/DISPATCH_CONFIGURABLE_BUSINESS_POLICY_DOCTRINE.md) ·
[fact and provenance](docs/DISPATCH_FACT_AND_PROVENANCE_DOCTRINE.md) ·
[state transitions](docs/DISPATCH_STATE_TRANSITION_RULES.md) ·
[adapter boundaries](docs/DISPATCH_EXTERNAL_ADAPTER_BOUNDARIES.md)

Specification, not implemented: [policy profile](docs/DISPATCH_POLICY_PROFILE_SPEC.md) ·
[load arrangement](docs/DISPATCH_LOAD_ARRANGEMENT_SPEC.md) ·
[evaluation engine](docs/DISPATCH_EVALUATION_ENGINE_SPEC.md) ·
[decision matrix](docs/DISPATCH_DECISION_MATRIX_SPEC.md) ·
[filter/score/sort](docs/DISPATCH_FILTER_SCORE_SORT_SPEC.md) ·
[recommendation](docs/DISPATCH_RECOMMENDATION_MODEL_SPEC.md) ·
[confidence](docs/DISPATCH_CONFIDENCE_MODEL_SPEC.md) ·
[override rules](docs/DISPATCH_OVERRIDE_RULES_SPEC.md) ·
[profile examples](docs/DISPATCH_POLICY_PROFILE_EXAMPLES.md) ·
[PR summary](docs/DISPATCH_POLICY_FOUNDATION_PR_SUMMARY.md)

