# JULES_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05. Default branch `main` at `b624d7e`; **all 9 branches examined**.
Repository was **not attached to this session** at start; added via `add_repo` and cloned
read-only from https://github.com/jax1313-outlook/Jules.

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Jules` | `list_repos` / clone URL |
| Repository URL | https://github.com/jax1313-outlook/Jules | `list_repos` |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-10 13:09:04 -0400 — **the same second as `Claude-3` and `Library`** | `git log --reverse` |
| Last commit date (`main`) | 2026-08-24 00:57:31 -0400 (`b624d7e`, "Merge pull request #7 — record where the Dispatch implementation is") | `git log -1` |
| Last push | 2026-08-29T14:18:24Z | `list_repos` |
| Branch count | **9** | `git ls-remote --heads` |
| Commit count (`main`) | **21** | `git rev-list --count HEAD` |
| Default branch | `main` (`origin/HEAD → origin/main`) | `git symbolic-ref` |
| Contributors | `jax1313-outlook` (10), `google-labs-jules[bot]` (7), `Claude <noreply@anthropic.com>` (4) | `git shortlog -sne` |
| README status | Present — `README.md` | `git ls-files` |
| Tracked files (`main`) | 41 | `git ls-files` |
| Python (`main`) | 3 files, **717 lines** (+3 committed `.pyc`) | `wc -l` |
| Markdown (`main`) | 24 files, 4,957 lines | `wc -l` |
| HTML templates | 8 | `git ls-files '*.html'` |
| Files unique to branches | **70** | branch scan |

### Branches, measured

| Branch | Files | `.md` | `.py` | Note |
|---|---|---|---|---|
| `main` | 41 | 24 | 3 | the Flask presentation layer |
| `claude/dispatch-tri-department-build-899qjm` | 61 | 60 | 1 | tri-department reconciliation docs |
| `claude/dispatch-final-blueprint-v1-1vlkkc` | 43 | 43 | 0 | **holds `DISPATCH_FINAL_BLUEPRINT_v1.md`** |
| `claude/dispatch-repo-context-reconcile-7mblbb` | 41 | 24 | 3 | |
| `claude/jules-w0-1-debugger-pin-removal` | 40 | 23 | 3 | |
| `dispatch-presentation-layers-10085523953725471670` | 40 | 23 | 3 | the Jules-bot presentation-layer build |
| `revert-2-dispatch-presentation-layers-…` | 21 | 21 | 0 | the revert of that build |
| `jules-13086465147654077201-fa7a7009` | 21 | 21 | 0 | Jules-bot session branch |
| `claude/e-ingestion-setup-bz23tm` | 28 | 28 | 0 | |

**Finding:** a `revert-2-dispatch-presentation-layers-…` branch exists alongside the
`dispatch-presentation-layers-…` branch it reverts. The reverted state (21 files, no Python) and
the built state (40 files, 3 Python) both persist as branches. `main` carries the built state.

---

## SECTION 2 — PURPOSE

**Evidence source:** `README.md`.

Jules' `README.md` is **byte-identical to `Claude-3`'s**:

> # Dispatch Repo-3
> This repository is the clean source-of-truth package for creating
> **DISPATCH_FINAL_BLUEPRINT_v1.md**.

So the repository's stated purpose is the same as Claude-3's — the two were created in the same
second, from the same document set, for the same mission.

Its **actual, differentiating** content is the Flask presentation layer. `app.py`:

> """Dispatch Presentation Layer Flask Application
> Integrates Driver Portal, Operations Portal, External Stakeholder Portal, and Public Website.
> """

with positioning recorded in the code as *"Jacksonville Regional Micro-Response Carrier™"*.

The name comes from **Google Labs Jules**, an agent that authored 7 of the 21 commits and holds
two branches. Jules-bot branches also appear in `Dispatch` (3) and `L2-intelligence-agent.` (1).

---

## SECTION 3 — DIRECTORY MAP

```
Jules/                                (main)
├── app.py                    Flask app — 4 portals + public website + legacy redirects
├── dispatch_spine.py         Spine engine & data models (consequence-level model)
├── run_portal.sh             Launch script
├── templates/                8 Jinja templates
│   ├── base.html
│   ├── index.html            Public website home
│   ├── about.html  capabilities.html  contact.html
│   ├── driver.html           Driver Portal
│   ├── operations.html       Operations Portal
│   └── stakeholder.html      External Stakeholder Portal
├── static/style.css
├── tests/test_portals.py     8 test functions
├── __pycache__/              3 committed .pyc files
├── DEPLOYMENT.md             ← unique
├── PORTAL_WIRING.md          ← unique
├── DISPATCH_IMPLEMENTATION_STATUS.md   ← unique variant
└── (20 further doctrine documents, shared with Claude-3 / Library / Claude / Claude-2)
```

**Folder purposes** — this is a single-file Flask application with a template directory. There
is no package structure, no database, and no persistence layer beyond `dispatch_spine.py`'s
in-memory `spine_store`.

---

## SECTION 4 — CODE INVENTORY

### Applications
| Application | Entry point | Evidence |
|---|---|---|
| Dispatch Presentation Layer | `app.py`, `run_portal.sh` | `DEPLOYMENT.md`, `PORTAL_WIRING.md` |

### Entry points
`app.py` (Flask), `run_portal.sh`.

### Modules (2)
- **`app.py`** — Flask application. Imports `spine_store`, `CONSEQUENCE_LABELS` and
  `LEVEL_0_SILENT_LOG` from `dispatch_spine`. Uses `werkzeug.utils.secure_filename`
  (file upload handling).
- **`dispatch_spine.py`** — *"Dispatch Spine Engine & Data Models for Level 1 Transport.
  Aligned with `DISPATCH_SPINE_SPECIFICATION_v1.md`, `ALERT_GOVERNANCE_DOCTRINE.md`, and
  `PORTAL_DESCRIPTION.md`."* Dataclass-based, `uuid` identifiers, in-memory.

### APIs / Routes
Four portals plus a public website, and a legacy-alias redirect group:

```python
@app.route("/portal")  @app.route("/cos")  @app.route("/l2-cos")
@app.route("/dashboard")  @app.route("/admin")
def legacy_portal_redirect():
    """Redirects legacy portal URLs seamlessly to the Dispatch Operations Portal."""
```

Public website: `/`, `/about`, `/capabilities`, `/contact`.
Portals: driver, operations, stakeholder (per `app.py`'s docstring and templates).

### Database models
None. `dispatch_spine.py` holds an in-memory `spine_store`.

### Contracts — the consequence-level model
`dispatch_spine.py` defines a six-level consequence scale found nowhere else in the ecosystem:

```python
LEVEL_0_SILENT_LOG = 0   LEVEL_1_STATUS = 1   LEVEL_2_REVIEW = 2
LEVEL_3_DECISION = 3     LEVEL_4_CONFLICT = 4  LEVEL_5_AUTHORITY = 5

CONSEQUENCE_LABELS = {0:"Silent Log", 1:"Status", 2:"Review",
                      3:"Decision", 4:"Conflict", 5:"Authority"}

REQUIRED_CARD_CLOSING = ("This is a recommendation only. "
                         "No action is authorized. Mike decides.")
```

`REQUIRED_CARD_CLOSING` is the authority rule of `CLAUDE.md` §4 enforced as a **string constant
required on every Portal Card**.

### CLI tools / Background services / Connectors / Adapters
None.

### Tests
`tests/test_portals.py` — **8 `def test_` functions**. *Not run during this inventory.*

### Scripts
`run_portal.sh`.

### Committed build artefacts
`__pycache__/app.cpython-312.pyc`, `__pycache__/dispatch_spine.cpython-312.pyc`,
`tests/__pycache__/test_portals.cpython-312-pytest-9.1.1.pyc`. Their presence records the
Python (3.12) and pytest (9.1.1) versions the code was last run under.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Public website (home, about, capabilities, contact) | Yes | 4 routes + 4 templates | `app.py`, `templates/{index,about,capabilities,contact}.html` | IMPLEMENTED |
| Driver Portal | Yes | `templates/driver.html`; `app.py` docstring | those files | IMPLEMENTED — a different, earlier design from Dispatch's |
| Operations Portal | Yes | `templates/operations.html` | those files | IMPLEMENTED |
| External Stakeholder Portal | Yes | `templates/stakeholder.html` | those files | IMPLEMENTED |
| Legacy URL redirects (`/portal`, `/cos`, `/l2-cos`, `/dashboard`, `/admin`) | Yes | `legacy_portal_redirect()` | `app.py` | IMPLEMENTED |
| Spine engine (consequence-level model) | Yes | `dispatch_spine.py` | that file | IMPLEMENTED — in-memory; a **different** engine from `Dispatch/dispatch/spine/` |
| Six-level consequence scale | Yes | `LEVEL_0_SILENT_LOG` … `LEVEL_5_AUTHORITY`, `CONSEQUENCE_LABELS` | `dispatch_spine.py` | IMPLEMENTED — unique in the ecosystem |
| Portal Card required closing | Yes | `REQUIRED_CARD_CLOSING` constant | `dispatch_spine.py` | IMPLEMENTED — unique in the ecosystem |
| File upload handling | Yes | `secure_filename` import | `app.py` | IMPLEMENTED |
| Persistence | **No** | in-memory `spine_store` only | — | ABSENT |
| Authentication / CSRF | **No** | no auth module, no CSRF | — | ABSENT |
| Freight domain (loads, drivers, IFTA, settlement) | **No** | no such module | — | ABSENT |
| Connectors | **No** | — | — | ABSENT |

---

## SECTION 6 — DOCUMENT INVENTORY

24 markdown files on `main`; ~45 more across branches.

**Constitutions** — `DISPATCH_CONSTITUTION_v3.md`.

**Architecture documents** — `ARCHITECTURE.md`, `ARCHITECTURAL_DISPOSITION.md`,
`CONTEXT_MASTER.md`, `DISPATCH_SPINE_OVERVIEW.md`, `PORTAL_DESCRIPTION.md`,
`COGNITIVE_FUNCTIONS.md`, **`PORTAL_WIRING.md`** (unique).

**Specifications** — `DISPATCH_SPINE_SPECIFICATION_v1.md`,
`SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md`, `DISPATCH_DECISION_MATRIX.md`,
`INTELLIGENCE_VERIFICATION_WORKFLOW.md`.

**Governance / doctrine** — `ALERT_GOVERNANCE_DOCTRINE.md`, `ARCHIVE_REVIEW_POLICY.md`,
`DISPATCH_VERSION_DOCTRINE.md`, `SUPERSESSION_MAP.md`, `REFINEMENT_ANALYST_REMOVAL.md`,
`DISPATCH_REPO_MANIFEST_v3.md`.

**Department descriptions** — `MANAGER.md`, `PUBLISHER.md`, `INTELLIGENCE_ANALYST.md`.

**Operational documents** — **`DEPLOYMENT.md`** (unique).

**Status** — `DISPATCH_IMPLEMENTATION_STATUS.md` (a variant of Claude-3's).

**On branches** — `DISPATCH_FINAL_BLUEPRINT_v1.md`, `DISPATCH_SHARED_OBJECT_CONTRACTS_v1.md`,
`LIBRARY_INGESTION_RULE.md`, `CLONE_MAP.md`, `RECOVERY_REPORT.md`,
`SOURCE_ARTIFACT_INDEX.md`, `SURVIVES_EVOLVES_RETIRES.md`, `OPEN_QUESTIONS_FOR_MIKE.md`,
`DISPATCH_V0_BLUEPRINT.md`, `DISPATCH_V0_BUILD_PLAN.md`, the 16 stage designs, the department
completeness reviews, `integration/CROSS_REPO_WALKTHROUGH_REPORT.md` — the same branch corpus as
Claude-3, minus the `dispatch_build/` package. Also `flask_app.log`.

---

## SECTION 7 — UNIQUE ASSETS

**20 of 41 `main` files (48.8%) are unique by content** — the lowest ratio of any code-bearing
repository, because the 21 doctrine documents are byte-identical copies shared with `Claude-3`,
`Claude`, `Claude-2` and `Library`.

### 1. The four-portal presentation layer
`app.py`, 8 templates, `static/style.css`, `run_portal.sh`, `tests/test_portals.py`.
This is a **complete, different, earlier presentation design** from Dispatch's: a public
marketing website plus Driver, Operations and External Stakeholder portals in one Flask app.
Dispatch has a Driver Portal and a stakeholder view but **no public website** and no
Operations Portal by that name. The `index.html`, `about.html`, `capabilities.html` and
`contact.html` templates are the only public-facing marketing pages in the ecosystem outside
the design prompts in `premium-logistics-platform-`.

### 2. `dispatch_spine.py` — a second, unrelated Spine implementation
717 lines total across the three Python files. Declares alignment with
`DISPATCH_SPINE_SPECIFICATION_v1.md`, `ALERT_GOVERNANCE_DOCTRINE.md` and
`PORTAL_DESCRIPTION.md`. This is **not** the same engine as `Dispatch/dispatch/spine/` —
Dispatch's is SQLite-backed with `state.transition()` / `store.apply_transition()`; this one is
in-memory and organised around consequence levels. A **third** unrelated Spine prototype exists
in `Claude/proposal/spine_prototype/`.

### 3. The six-level consequence model
`LEVEL_0_SILENT_LOG` through `LEVEL_5_AUTHORITY` with `CONSEQUENCE_LABELS`
(Silent Log / Status / Review / Decision / Conflict / Authority). **This scale exists in no
other repository.** It is a graded model of how much human attention an event demands — a
different idea from Dispatch's scoring (which sorts opportunities) and from Hold's queue states.

### 4. `REQUIRED_CARD_CLOSING`
```
"This is a recommendation only. No action is authorized. Mike decides."
```
The only place in the ecosystem where the authority doctrine of `CLAUDE.md` §4 is enforced as a
**required string constant on every Portal Card**, rather than as prose in a document.

### 5. Legacy URL preservation
`/portal`, `/cos`, `/l2-cos`, `/dashboard`, `/admin` → Operations Portal. The only artefact
anywhere that preserves the **L2-COS-era URL space**, which `L2-intelligence-agent./README.md`
records as retired terminology. It is a working record of what the old system's addresses were.

### 6. `PORTAL_WIRING.md` and `DEPLOYMENT.md`
The wiring document for this presentation layer and its deployment guide. Unique.

### 7. The `"Jacksonville Regional Micro-Response Carrier™"` positioning
Recorded in `app.py` as a code comment on the public-website route group. The only place this
market positioning appears in code.

### 8. Both sides of a reverted build
`dispatch-presentation-layers-10085523953725471670` (40 files, the build) and
`revert-2-dispatch-presentation-layers-10085523953725471670` (21 files, the revert) both
persist. The ecosystem's only preserved build-and-revert pair.

### 9. Google Labs Jules authorship
7 of 21 commits and two bot branches. Jules-bot commits also appear in `Dispatch` (11 commits,
3 branches) and `L2-intelligence-agent.` (1 commit, 1 branch); this repository is named for it.

### 10. `flask_app.log` (on a branch)
A committed application log — a runtime record.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 306 | throughout |
| Library | 127 | shared doctrine set |
| Publisher | 122 | `PUBLISHER.md` |
| Manager | 129 | `MANAGER.md`, branch stage designs |
| Route Risk | 28 | doctrine documents |
| COMI | 26 | doctrine documents |
| Jules | 15 | branch names, bot commits |
| Mission Visibility | 5 | doctrine documents |
| SAM | 3 | doctrine documents |
| Joe | 0 | — |

**Duplication relationship with Claude-3.** Jules and Claude-3 were created in the same second
(2026-08-10 13:09:04 -0400) with identical READMEs and an overlapping document set; `Library`
shares that creation timestamp too. Jules and Claude-3 both carry
`claude/dispatch-final-blueprint-v1-1vlkkc` with the **identical** blueprint blob, and both
carry near-identical `DISPATCH_IMPLEMENTATION_STATUS.md` pointer documents. Their divergence is
that Claude-3 gained the recovery-mission corpus and `dispatch_build/`, while Jules gained the
Flask presentation layer.

**Legacy system reference.** The `/cos` and `/l2-cos` redirect targets name the L2-COS system,
whose successor repository is `L2-intelligence-agent.`.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code
A four-portal Flask presentation layer (public website, Driver, Operations, External
Stakeholder) with 8 templates and a stylesheet · legacy URL redirects preserving the L2-COS
address space · an in-memory Spine engine with a six-level consequence model and a required
Portal Card closing · file-upload handling · 8 test functions · a launch script.

### Partially Built
- **The Spine** — `dispatch_spine.py` declares alignment with the spine specification but is
  in-memory with no persistence. It is a presentation-layer spine, not a lifecycle authority.
- **The portals** — templates and routes exist; there is no data source behind them.

### Documented Only
The 21-document doctrine corpus shared with Claude-3, and (on branches) the Final Blueprint,
shared object contracts, library ingestion rule, V0 blueprint and build plan, 16 stage designs
and the department completeness reviews.

### Referenced But Missing
- **Persistence** — `spine_store` is in-memory; nothing survives a restart.
- **Authentication** — `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` is present as
  doctrine; no authentication code exists.
- **The stated mission's deliverable on `main`** — `DISPATCH_FINAL_BLUEPRINT_v1.md` is the
  README's stated purpose and is on a branch only.

### Unknown
- Whether the 8 test functions pass — **not run** during this inventory.
- Why the presentation-layer build was reverted on one branch and kept on `main`.
- Whether Jules and Claude-3 were intended as duplicates or diverged by accident.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Jules presents itself, in a README byte-identical to Claude-3's, as "Dispatch Repo-3" — the
source-of-truth package for assembling the Final Blueprint. The two repositories were created
in the same second from the same documents. What actually distinguishes Jules is a working
**Flask presentation layer**: a public marketing website plus Driver, Operations and External
Stakeholder portals in one application. It is named for Google Labs Jules, an agent that
authored 7 of its 21 commits.

**What is actually implemented?**

717 lines of Python across three files, 8 Jinja templates and a stylesheet. `app.py` serves a
four-route public website (`/`, `/about`, `/capabilities`, `/contact`), three portals, and a
legacy-redirect group that maps `/portal`, `/cos`, `/l2-cos`, `/dashboard` and `/admin` onto
the Operations Portal. `dispatch_spine.py` is an in-memory Spine engine organised around a
six-level consequence scale. Eight test functions cover the portals. There is no persistence,
no authentication, no CSRF, and no freight domain model.

**What unique value does it contain?**

Just under half its files are unique, and four things exist nowhere else. First, the **public
marketing website and Operations Portal** — Dispatch has neither. Second, the **six-level
consequence model** (Silent Log, Status, Review, Decision, Conflict, Authority), a graded scale
for how much human attention an event demands, which appears in no other repository. Third,
`REQUIRED_CARD_CLOSING` — *"This is a recommendation only. No action is authorized. Mike
decides."* — the only place the authority doctrine is enforced as a required string constant on
every card rather than stated as prose. Fourth, the **legacy L2-COS URL space**, preserved as
working redirects; it is the only surviving record of the old system's addresses.

It also holds a second, unrelated Spine implementation — the ecosystem contains three
(`Dispatch/dispatch/spine/`, this one, and `Claude/proposal/spine_prototype/`), none of them
copies of the others — a preserved build-and-revert branch pair, and a copy of
`DISPATCH_FINAL_BLUEPRINT_v1.md` identical to Claude-3's, likewise on a branch and not on `main`.
