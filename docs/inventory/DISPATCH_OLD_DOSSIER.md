# DISPATCH_OLD_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05 from the repository at commit `be6c593` (`origin/main`).

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Dispatch-Old` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Dispatch-Old | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | **2026-07-30 21:10:04 -0400** — the oldest first commit of any repository except `L2-intelligence-agent.` | `git log --reverse` |
| Last commit date | 2026-08-12 20:24:48 +0000 (`be6c593`, "Add .env to .gitignore") | `git log -1` |
| Last push | 2026-08-12T20:24:53Z | `list_repos` |
| Branch count | **1** (`main` only) | `git ls-remote --heads` |
| Commit count | **4** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (2), `Claude <noreply@anthropic.com>` (1), `Your Name <your-email@domain.com>` (1) | `git shortlog -sne` |
| README status | Present — `README.md` at root, plus `cin_lite/README.md` | `git ls-files` |
| Tracked files | 86 | `git ls-files \| wc -l` |
| Python | 56 files, **3,906 lines** | `git ls-files '*.py'` + `wc -l` |
| Markdown | 13 files, 979 lines | same |

**Note on the third contributor.** One commit is authored by `Your Name <your-email@domain.com>`
— an unconfigured git identity, not a distinct person.

---

## SECTION 2 — PURPOSE

**Evidence sources:** `README.md`, `CLAUDE.md`, `CURRENT_STATE.md`, `REPO_TO_DISPATCH_MAP.md`,
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`.

`README.md` names it:

> **Hybrid CIN-Lite System** — A contract-locating, intelligence-processing, and
> archive-building platform for federal opportunities. It acquires solicitations, runs
> deterministic rule modules that extract intelligence as JSON, emails a human a checkbox
> decision, and archives or routes the result.

`CLAUDE.md` (this repository's own) states its status:

> This repository is already implementing an end-to-end workflow. It is now being stabilized
> as a Dispatch-oriented system rather than rebuilt from scratch.

`REPO_TO_DISPATCH_MAP.md` records the department mapping this repository used — the clearest
statement anywhere of how the CIN-Lite vocabulary maps to Dispatch's department vocabulary:

> - Intell = acquisition + processing + rules + summarizer
> - **Manager = router + control + workflows + human decision routing**
> - Publisher = proposal_writer + email drafts + packet generation helpers
> - Library = approved reusable knowledge and templates
> - Archive = historical records, routing decisions, and outputs

`CURRENT_STATE.md` records what was added late in its life: "A lightweight Library department…
A lightweight Manager ticket layer for human-controlled workflow tracking."

This is the **predecessor of the `cin_lite/` half of Dispatch**. Dispatch's `CLAUDE.md` §1
describes that half as "Implemented and passing; not the focus of current work. It is also
Dispatch's **only** mail transport."

---

## SECTION 3 — DIRECTORY MAP

```
Dispatch-Old/
├── cin_lite/                  The Hybrid CIN-Lite system
│   ├── run.py                 Orchestrator — the end-to-end flow
│   ├── acquisition.py         Fetch solicitations (SAM.gov)
│   ├── processing.py          Apply rule modules
│   ├── control.py             Checkbox email — the human decision gate
│   ├── archive.py             Archive layer
│   ├── email_delivery.py      Outbound mail
│   ├── rules/                 9 deterministic rule modules + base
│   ├── agents/                3 Claude helpers: summarizer, router, proposal_writer
│   ├── workflows/proposal.py  Proposal-trigger workflow
│   ├── manager.py       ★     Manager department — ticketing / human-control workflow
│   ├── library.py       ★     Library department — approved reusable facts
│   ├── publisher.py     ★     Publisher department
│   ├── dashboard.py     ★     Dashboard (222 LOC) + dashboard.html
│   ├── portal.py        ★     Portal command (70 LOC) + portal_refresh.html
│   ├── Library/               Seeded library: Company/company_profile.json,
│   │                          Templates/proposal_outline.md
│   └── sample_data/           2 sample contracts
├── tests/                     25 test files, 93 test functions
├── Portal Deploy/       ★     VPS DEPLOYMENT PACKAGE
│   ├── nginx.conf             nginx site configuration
│   ├── portal.service         systemd unit
│   ├── setup_certbot_nginx.sh / _custom.sh   TLS provisioning
│   ├── .env.example
│   ├── DNS_records_for_Namecheap.md / DNS_ready_to_paste_for_Namecheap.txt
│   ├── 01_Deployment_Plan.md, DEPLOY_STEP_BY_STEP.md,
│   └── Deployment_Checklist.md, README_DEPLOY.md, Required Items.md
├── .github/workflows/ci.yml   CI
├── CONSTITUTION.md            Constitution
├── CURRENT_STATE.md           State record
├── REPO_TO_DISPATCH_MAP.md    Department mapping
├── CLAUDE.md                  Cold-start brief for this repository
├── pytest.ini, setup.py, .coveragerc
└── Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx
```

★ = present here and **absent from Dispatch**. See Section 7.

**Folder purposes** — `CLAUDE.md` names five load-bearing layers whose responsibilities must
stay separate: Acquisition, Processing, Control, Archive, Automation. Data flow:
`acquire → process (rule modules) → email user with checkboxes → user selects action →
archive / route / escalate`. Archive folder layout is specified as
`/Archive/{Raw,Processed,Intelligence,Summaries,Routing}`.

---

## SECTION 4 — CODE INVENTORY

### Applications
| Application | Entry point | Evidence |
|---|---|---|
| CIN-Lite pipeline | `cin_lite/run.py` | `python -m cin_lite.run` (README quick start) |
| Dashboard (server + CLI) | `cin_lite/dashboard.py` + `dashboard.html` | `tests/test_dashboard_server.py`, `test_dashboard_cli.py` |
| Portal command | `cin_lite/portal.py` + `portal_refresh.html` | `tests/test_portal_command.py`, `test_portal_env_config.py` |

### Entry points
`python -m cin_lite.run` (interactive), `python -m cin_lite.run --action approve_proposal`
(non-interactive demo), `setup.py`.

### Services / modules — `cin_lite/` (14 top-level)
`acquisition`, `processing`, `control`, `archive`, `email_delivery`, `run`,
**`manager`**, **`library`**, **`publisher`**, **`dashboard`**, **`portal`**, plus packages
`rules/`, `agents/`, `workflows/`.

### Rule modules — `cin_lite/rules/` (9 + base)
`set_aside`, `naics_sin`, `past_performance`, `pricing_anomaly`, `vendor_network`,
`subcontractor_dominance`, `jv_mp_structure`, `foreign_influence`, `cyber_compliance`.
`CLAUDE.md`: each is "a **standalone logic unit** that outputs **structured JSON**" and must
be **deterministic**.

### Agents — `cin_lite/agents/` (3)
`summarizer`, `router`, `proposal_writer`. These are the *non*-deterministic Claude helpers.
(Dispatch's `cin_lite/agents/` additionally has `extractor` and `receipt_vision`.)

### Workflows
`cin_lite/workflows/proposal.py` — the proposal-trigger workflow.

### Manager department — `cin_lite/manager.py` (101 LOC)
Docstring: *"Manager department — lightweight ticketing and human-control workflow."*
Persists tickets as JSON under `Archive/ManagerTickets/`, ticket IDs `MGR-<UTC timestamp>`.
`create_ticket(source_contract_id, assigned_department, recommended_action, *,
human_decision_required=True)` — the human-decision flag defaults to `True`.

### Library department — `cin_lite/library.py` (67 LOC)
Approved reusable facts and templates. Seeded with `cin_lite/Library/Company/company_profile.json`
and `cin_lite/Library/Templates/proposal_outline.md`.

### Publisher department — `cin_lite/publisher.py` (84 LOC)
Tested by `test_publisher.py`, `test_publisher_approval_state.py`, `test_publisher_work_orders.py`,
`test_manager_publisher_handoff.py`.

### Database models
None. `CLAUDE.md`: "Local filesystem (no external DB in Phase 1)." Persistence is JSON files
under the Archive tree.

### Contracts
The email control system is the contract: five fixed actions — *Approve for archive, Approve
for proposal, Reject, Flag for review, Request deeper analysis* — mapping "directly to an
archive/routing action."

### Adapters / Connectors
No connector package. External touchpoints are `acquisition.py` (SAM.gov) and
`email_delivery.py` (Email API), each documented as falling back gracefully when unconfigured.

### Tests
25 files, **93 `def test_` functions**, `pytest.ini`, `.coveragerc`, CI at
`.github/workflows/ci.yml`. *Not run during this inventory.*

Test files with no counterpart in Dispatch (17): `test_dashboard.py`,
`test_dashboard_actions.py`, `test_dashboard_cli.py`, `test_dashboard_html.py`,
`test_dashboard_latest_run.py`, `test_dashboard_quick_actions.py`, `test_dashboard_refresh.py`,
`test_dashboard_server.py`, `test_dashboard_status_banner.py`, `test_library.py`,
`test_manager.py`, `test_manager_publisher_handoff.py`, `test_portal_command.py`,
`test_portal_env_config.py`, `test_publisher.py`, `test_publisher_approval_state.py`,
`test_publisher_work_orders.py`.

### Scripts / utilities
`Portal Deploy/setup_certbot_nginx.sh`, `setup_certbot_nginx_custom.sh`.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Acquisition (SAM.gov) | Yes | `README.md` flow diagram; `tests/test_acquisition.py` | `cin_lite/acquisition.py` | IMPLEMENTED; provider `UNCONFIGURED` (falls back to sample data) |
| Deterministic rule processing (9 rules) | Yes | `cin_lite/rules/` + `tests/` | `cin_lite/processing.py`, `rules/` | IMPLEMENTED |
| Summarization | Yes | Claude agent | `cin_lite/agents/summarizer.py` | IMPLEMENTED (labelled non-deterministic) |
| Routing recommendation | Yes | `tests/test_routing.py` | `cin_lite/agents/router.py` | IMPLEMENTED (labelled non-deterministic) |
| Email control gate (5 checkbox actions) | Yes | `tests/test_control_email.py` | `cin_lite/control.py` | IMPLEMENTED |
| Email delivery | Yes | `cin_lite/email_delivery.py` | that file | IMPLEMENTED; `UNCONFIGURED` |
| Archive | Yes | `tests/test_archive.py`; `/Archive/{Raw,Processed,Intelligence,Summaries,Routing}` | `cin_lite/archive.py` | IMPLEMENTED |
| Proposal workflow | Yes | `tests/test_proposal_trigger.py` | `cin_lite/workflows/proposal.py`, `agents/proposal_writer.py` | IMPLEMENTED |
| **Manager (ticketing / human control)** | **Yes** | `tests/test_manager.py`, `test_manager_publisher_handoff.py`; `MGR-` ticket IDs; `human_decision_required=True` default | `cin_lite/manager.py` | **IMPLEMENTED — the only Manager implementation in the ecosystem** |
| **Library (approved reusable facts)** | **Yes** | `tests/test_library.py`; seeded `Library/Company/`, `Library/Templates/` | `cin_lite/library.py` | IMPLEMENTED |
| **Publisher** | **Yes** | 4 test files incl. approval state and work orders | `cin_lite/publisher.py` | IMPLEMENTED |
| **Dashboard** (server, CLI, HTML, status banner, quick actions, refresh) | **Yes** | 9 dedicated test files | `cin_lite/dashboard.py`, `dashboard.html` | IMPLEMENTED |
| **Portal command** | **Yes** | `test_portal_command.py`, `test_portal_env_config.py` | `cin_lite/portal.py`, `portal_refresh.html` | IMPLEMENTED |
| **VPS deployment (nginx + systemd + certbot + DNS)** | **Yes** | `Portal Deploy/` — 10 files | `nginx.conf`, `portal.service`, `setup_certbot_nginx.sh` | IMPLEMENTED; deployment itself UNVERIFIED |
| Driver Portal / freight operations | **No** | No freight code of any kind | — | ABSENT |
| Load / driver / equipment models | **No** | — | — | ABSENT |
| IFTA | **No** | — | — | ABSENT |
| Spine lifecycle engine | **No** | — | — | ABSENT |
| Connector boundary | **No** | — | — | ABSENT |
| Route Risk / COMI / Mission Visibility | **No** | 2 incidental Route-Risk string matches; no code | — | ABSENT |

---

## SECTION 6 — DOCUMENT INVENTORY

13 markdown files plus one `.docx`.

**Constitutions** — `CONSTITUTION.md`.

**Architecture documents** — `Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx`
(the source architecture; byte-identical copy also in Dispatch), `cin_lite/README.md`.

**Governance documents** — `CLAUDE.md` (this repository's cold-start brief; states the five
load-bearing subsystem boundaries and the "do not violate" constraints:
lightweight, locally controllable, expandable to full CIN, deterministic rule logic).

**Decision logs** — none.

**Specifications** — the archive folder layout, the five email actions, and the nine named
rule modules are specified inside `CLAUDE.md`.

**Roadmaps** — `CLAUDE.md` §Roadmap: Phase 1 stabilize acquisition/rules/email/archive/proposal;
Phase 2 expand the Dispatch department model with **Library, Publisher, and Manager** workflow
refinements; Phase 3 integrate into broader Portal and operations tooling.

**Research reports** — none.

**Handoffs / mapping** — **`REPO_TO_DISPATCH_MAP.md`** (the CIN-Lite→Dispatch department
mapping), **`CURRENT_STATE.md`** (what exists / what was added).

**Operational documents** — `Portal Deploy/01_Deployment_Plan.md`,
`DEPLOY_STEP_BY_STEP.md`, `Deployment_Checklist.md`, `README_DEPLOY.md`,
`Required Items.md`, `DNS_records_for_Namecheap.md`,
`DNS_ready_to_paste_for_Namecheap.txt`.

**Prompts** — none.

---

## SECTION 7 — UNIQUE ASSETS

**66 of 86 files (76.7%) have content found in no other repository.**

### 1. The only Manager implementation in the ecosystem — `cin_lite/manager.py`

This is the single most consequential finding in this dossier. Dispatch's `CLAUDE.md` §5.6
states:

> **There is no Manager component in the current architecture. Do not create, restore,
> reference, or infer a Manager component, Manager agent, or Manager authority.**
> `docs/MANAGER.md` is the permanent record of a capability that was *named* in planning and
> *never built*.

That is true of **Dispatch**. It is not true of the ecosystem. `Dispatch-Old/cin_lite/manager.py`
is 101 lines of working Manager code — "lightweight ticketing and human-control workflow" —
persisting `MGR-<timestamp>` tickets to `Archive/ManagerTickets/`, with
`human_decision_required` defaulting to `True`. It is exercised by `tests/test_manager.py` and
`tests/test_manager_publisher_handoff.py`. `REPO_TO_DISPATCH_MAP.md` defines Manager as
"router + control + workflows + human decision routing".

Manager also appears as *documentation* in nine other repositories (`MANAGER.md`,
`MANAGER_CONSTITUTION_v1.md`, `MANAGER_DESCRIPTION_v2.md`) and as three unmerged Dispatch
branches (`stage12-manager-foundation`, `stage12-manager-archive-wiring`,
`stage12-manager-m7-policy-hook`). **Only here does Manager exist as running, tested code.**

Recorded as fact. No recommendation is offered, and none should be read into this entry.

### 2. Five `cin_lite` modules absent from Dispatch (544 LOC) and their 17 tests
| File | LOC | In Dispatch? |
|---|---|---|
| `cin_lite/dashboard.py` (+ `dashboard.html`) | 222 | No |
| `cin_lite/manager.py` | 101 | No |
| `cin_lite/publisher.py` | 84 | No |
| `cin_lite/portal.py` (+ `portal_refresh.html`) | 70 | No |
| `cin_lite/library.py` | 67 | No |

Verified by `comm -23` over `git ls-files 'cin_lite/*'` in both repositories.

### 3. The seeded CIN-Lite Library
`cin_lite/Library/Company/company_profile.json` and
`cin_lite/Library/Templates/proposal_outline.md`. Not in Dispatch.

### 4. The VPS deployment package — `Portal Deploy/` (10 files)
`nginx.conf`, `portal.service` (systemd), `setup_certbot_nginx.sh` and a `_custom` variant,
`.env.example`, Namecheap DNS records in two formats, and five deployment documents.
Dispatch has `DEPLOY_VPS.md` and `DEPLOY_LOCAL.md` — **prose only**. Dispatch contains no
`nginx`, `systemd`, or `certbot` artefact of any kind (verified by filename search). These
are the ecosystem's only concrete hosting configuration files.

### 5. `REPO_TO_DISPATCH_MAP.md`
The only document in the ecosystem that maps CIN-Lite's module vocabulary onto Dispatch's
department vocabulary. It is the Rosetta stone between the two naming systems.

### 6. `CURRENT_STATE.md` and this repository's `CLAUDE.md`
The CIN-Lite-era cold-start brief, superseded in Dispatch but preserved intact here — with the
five-layer boundary statement, the archive folder layout, the five email actions, and the
three-phase roadmap.

### 7. Oldest continuous history of the CIN-Lite program
First commit 2026-07-30, three days before Dispatch's (2026-08-02).

### What it shares (20 files)
`Final_Architecture_for_Hybrid_CIN-Lite_System (1).docx` and the `cin_lite/` files that were
carried into Dispatch (rules, agents, acquisition, processing, control, archive,
email_delivery, run, sample data).

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 34 | `REPO_TO_DISPATCH_MAP.md`, `CLAUDE.md`, `CURRENT_STATE.md` |
| Publisher | 58 | `cin_lite/publisher.py`, 4 test files, `REPO_TO_DISPATCH_MAP.md` |
| Library | 51 | `cin_lite/library.py`, `cin_lite/Library/`, `test_library.py` |
| Manager | 36 | `cin_lite/manager.py`, `test_manager.py`, `test_manager_publisher_handoff.py` |
| SAM / SAM.gov | 28 | `cin_lite/acquisition.py`, `README.md` |
| Route Risk | 2 | incidental; no code |
| COMI | 0 | — |
| Mission Visibility | 0 | — |
| Jules | 0 | — |
| Joe / Assistant | 0 | — |

**Direction of reference.** This repository refers *forward* to Dispatch as its successor
("being stabilized as a Dispatch-oriented system", `CLAUDE.md`). Dispatch refers *back* to it
only obliquely; Dispatch's `CLAUDE.md` §1 describes the CIN-Lite half without naming this
repository. **No document in Dispatch records that `Dispatch-Old/cin_lite/manager.py`,
`library.py`, `publisher.py`, `dashboard.py`, `portal.py` and their 17 tests exist here and
not there.**

The CI badge in `README.md` points at `jax1313-outlook/cin-hybrid` — a repository name that
appears in neither the session's repository list nor `list_repos`. Recorded as a stale
reference.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
Acquisition · 9 deterministic rule modules · processing · summarization · routing
recommendation · checkbox email control gate with 5 actions · email delivery · archive with
the specified folder tree · proposal-trigger workflow · **Manager ticketing** · **Library** ·
**Publisher** · **Dashboard** (server, CLI, HTML, status banner, quick actions, refresh) ·
**Portal command** · 93 test functions · CI workflow · **complete VPS deployment package**
(nginx, systemd, certbot, DNS).

### Partially Built
- **Acquisition and email delivery** — implemented with graceful fallback; both external
  providers `UNCONFIGURED`. `README.md`: "Runs with zero setup on bundled sample data."

### Documented Only
- **Automation Layer** — `CLAUDE.md` names it as one of the five layers and specifies "n8n or
  equivalent". No n8n artefact exists in the repository.
- **Phase 2 and Phase 3** of the roadmap (department-model expansion; Portal/operations
  integration).
- **Full CIN** — named as the future expansion target; not present.

### Referenced But Missing
- **`jax1313-outlook/cin-hybrid`** — the CI badge in `README.md` targets it; the repository is
  not in the account listing.
- The Archive tree itself is created at runtime, not committed.

### Unknown
- Whether the 93 test functions currently pass — **the suite was not run** during this inventory.
- Whether the `Portal Deploy/` package was ever used against a live VPS. No deployment record
  exists in the repository.
- Whether the deltas in Section 7 were deliberate omissions from Dispatch or unmigrated work.
  Nothing in either repository records the decision.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Dispatch-Old is the **Hybrid CIN-Lite System** — the government-contracting pipeline that
became the `cin_lite/` half of Dispatch. It has the oldest history in the freight-side lineage
(first commit 2026-07-30) but only 4 commits, 1 branch, 86 files and 3,906 lines of Python.
It went quiet on 2026-08-12. Its own `CLAUDE.md` describes it as a working end-to-end workflow
"being stabilized as a Dispatch-oriented system rather than rebuilt from scratch."

**What is actually implemented?**

A complete, tested contract pipeline: acquire a solicitation, run nine deterministic rule
modules that emit structured JSON, summarize and recommend a route with Claude helpers, email a
human five checkbox actions, and archive or route the result — with a proposal-trigger workflow
behind "Approve for proposal". On top of that sit five department modules — Manager, Library,
Publisher, Dashboard and Portal — and 93 test functions across 25 files. Separately, a complete
VPS deployment package: nginx configuration, a systemd unit, certbot provisioning scripts,
Namecheap DNS records, and five deployment documents.

It contains no freight code at all: no loads, drivers, equipment, IFTA, Spine, connectors,
Route Risk, COMI or Mission Visibility.

**What unique value does it contain?**

Three-quarters of its files exist nowhere else, and two holdings are singular in the ecosystem.

First, **`cin_lite/manager.py` is the only Manager implementation that exists as running,
tested code anywhere in the fourteen repositories.** Manager appears as documentation in nine
repositories and as three unmerged Dispatch branches; Dispatch's `CLAUDE.md` §5.6 states there
is no Manager component and that `docs/MANAGER.md` records "a capability that was *named* in
planning and *never built*". That statement is accurate about Dispatch and incomplete about the
ecosystem — 101 lines of Manager code, with `human_decision_required` defaulting to `True`, run
and are tested here.

Second, **`Portal Deploy/` is the only concrete hosting configuration in the ecosystem** —
Dispatch documents VPS deployment in prose but contains no nginx, systemd or certbot artefact.

Alongside these: four further `cin_lite` modules absent from Dispatch (Library, Publisher,
Dashboard, Portal — 443 more lines) with 17 tests that have no counterpart there, the seeded
CIN-Lite Library, and `REPO_TO_DISPATCH_MAP.md` — the only document that translates CIN-Lite's
module names into Dispatch's department names.
