# DISPATCH_GOVERNANCE_MANIFEST_REPAIR_PLAN_v1

**Document Type:** Governance alignment plan
**Program:** Dispatch
**Authorized by:** Mike Zachary, architectural adjudication of 2026-08-21, Decision 5
**Scope:** Index repair only. **No substantive doctrine change.**
**Status:** Plan. Not executed.

---

## 1. What is wrong

The documents that exist to prevent version ambiguity are themselves ambiguous. Four defects, all
verified by direct comparison of `DISPATCH_REPO_MANIFEST_v3.md` §3 against the files on disk in the
`Claude-3` governance repository.

| # | Defect | Evidence |
|---|---|---|
| R-1 | Manifest names a file that does not exist | §3 item 11 lists `DISPATCH_SPINE_SPEC_v1.md`; the file on disk is `DISPATCH_SPINE_SPECIFICATION_v1.md` |
| R-2 | Manifest names a second file that does not exist | §3 item 16 lists `DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md`; absent from disk |
| R-3 | Six governing documents on disk are unlisted | `DISPATCH_SPINE_SPECIFICATION_v1.md`, `ALERT_GOVERNANCE_DOCTRINE.md`, `DISPATCH_VERSION_DOCTRINE.md`, `ARCHIVE_REVIEW_POLICY.md`, `INTELLIGENCE_VERIFICATION_WORKFLOW.md`, `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` |
| R-4 | The supersession map predates the documents it should govern | `SUPERSESSION_MAP.md` is a "Clean Repo Replacement Draft — Round 2" and never mentions any v3 artifact — not the Constitution, not the manifest, not the Spine Specification |

R-1 and R-3 compound: **the Spine Specification is simultaneously the most load-bearing document in
the current adjudication and absent from the index under its real name.** A reviewer following the
manifest cannot find it.

## 2. Repair actions

Each action is mechanical and changes no doctrine.

### R-1 · Correct the Spine Specification filename
Change manifest §3 item 11 and §4.4 from `DISPATCH_SPINE_SPEC_v1.md` to
`DISPATCH_SPINE_SPECIFICATION_v1.md`.

**Decision required:** none — the file's own title block is authoritative and reads
`DISPATCH_SPINE_SPECIFICATION_v1`.

### R-2 · Account for the missing stress-test prompt
`DISPATCH_FINAL_ARCHITECTURE_STRESS_TEST_PROMPT.md` is listed and absent. Three possibilities, and
the record must state which:

1. It was used and retired → move to Historical, note the outcome.
2. It was never written → strike from the manifest.
3. It exists elsewhere → record its location.

**Decision required: Mike states which.** A builder cannot infer this, and inventing an answer would
be fabrication.

### R-3 · List every governing document on disk
Add the six unlisted documents to §3 with a role line each in §4. Proposed placement:

| Document | Section | Role line |
|---|---|---|
| `DISPATCH_SPINE_SPECIFICATION_v1.md` | 4.4 Deterministic Runtime | Build-readiness specification for the Spine — schemas, states, transitions, routing, validation, audit, approval events |
| `ALERT_GOVERNANCE_DOCTRINE.md` | 4.1 Governance and Authority | No uncontrolled automatic suppression of alerts; Mike is the alert governance authority |
| `DISPATCH_VERSION_DOCTRINE.md` | 4.1 Governance and Authority | Every significant Dispatch object carries a human-readable version marker |
| `ARCHIVE_REVIEW_POLICY.md` | 4.3 Organizational Functions | Archive review and retention handling |
| `INTELLIGENCE_VERIFICATION_WORKFLOW.md` | 4.3 Organizational Functions | Intelligence verification procedure |
| `SECURITY_AND_AUTHENTICATION_SPECIFICATION_v1.md` | 4.1 Governance and Authority | Authentication and access-control specification (the DISPATCH_PIN scope the portal implements) |

**Decision required:** confirm each is current rather than historical. Two —
`ALERT_GOVERNANCE_DOCTRINE` and `DISPATCH_VERSION_DOCTRINE` — carry the status line *"Proposed
Doctrine / Architecture Hardening"*, so they should be listed as **proposed**, not adopted, unless
Mike says otherwise.

### R-4 · State the Round 2 map's status against v3
Add a status block to `SUPERSESSION_MAP.md` recording one of:

- **Current, scope-limited** — it governs Round 2 concept supersession only; v3 artifacts are
  governed by `DISPATCH_REPO_MANIFEST_v3`; **or**
- **Superseded in part** — its §2 "Current Controlling Documents" list is replaced by manifest §3,
  while its §4 "Superseded Concepts" list remains in force.

**Recommended: the second.** Its §4 concept retirements — the 11-agent mesh, Research Scout,
Refinement Analyst, Dispatcher/Automation/Acquisition/Processing as cognitive roles, Controlled
Aggression — are still live and still correct, and nothing in v3 restates them. Its §2 file list is
simply older than v3's. Splitting it that way preserves the useful half without pretending the stale
half is current.

**Decision required: Mike selects.**

### R-5 · Add an adoption-status column
The manifest currently lists files without stating what force each carries. Add one column with a
controlled vocabulary:

| Status | Meaning |
|---|---|
| **AUTHORITATIVE** | Governing now. Conflicts resolve in its favour. |
| **PROPOSED** | Drafted, not adopted. May be cited as proposed, never as governing. |
| **SUPERSEDED** | Replaced. Retained for history only. |
| **DORMANT** | Adopted, deliberately inactive, authorizes no runtime behavior. |
| **UNADOPTED** | Received from outside, under review, carries no force. |

Proposed initial assignment:

| Document | Status |
|---|---|
| `DISPATCH_CONSTITUTION_v3.md` | AUTHORITATIVE |
| `DISPATCH_SPINE_SPECIFICATION_v1.md` | AUTHORITATIVE — with the §21 caveat that it authorizes no implementation by itself |
| `CONTEXT_MASTER.md`, `ARCHITECTURE.md`, `PORTAL_DESCRIPTION.md`, `COGNITIVE_FUNCTIONS.md`, `INTELLIGENCE_ANALYST.md`, `PUBLISHER.md`, `DISPATCH_SPINE_OVERVIEW.md`, `ARCHITECTURAL_DISPOSITION.md` | AUTHORITATIVE |
| `MANAGER.md` (Claude-3) and `Dispatch/docs/MANAGER.md` | **DORMANT** — see the conflict note below |
| `ALERT_GOVERNANCE_DOCTRINE.md`, `DISPATCH_VERSION_DOCTRINE.md` | PROPOSED — per their own status lines |
| `SUPERSESSION_MAP.md` | AUTHORITATIVE in part — pending R-4 |
| `DRIVER_FIRST_DOCTRINE_v2.md` | PROPOSED — pending numbering approval |
| Fable package (Ontology, three layer constitutions, Outlook boundary, Driver Portal context, startup/shutdown review) | **UNADOPTED** — source material; the Spine partition amendment draws on it without adopting it |
| `REFINEMENT_ANALYST_REMOVAL.md` | AUTHORITATIVE (retirement record) |

## 3. One substantive conflict this repair surfaces but must not resolve

`DISPATCH_CONSTITUTION_v3` §6.3 and §7.1 list **Manager** as a current organizational function.
`Dispatch/docs/MANAGER.md` records Manager as **DORMANT / RESERVED / NOT IMPLEMENTED**, authorizing
no code, route, data model or runtime behavior.

Marking Manager DORMANT in the manifest (R-5) is an **index** statement and is within this plan's
scope. Correcting Constitution v3 §6.3/§7.1 is a **doctrine** change and is explicitly **out of
scope** — Decision 5 bars substantive doctrine change.

**Recorded for a separate decision.** No reactivation is proposed, implied, or planned. The risk
being flagged is the opposite one: a builder reading §7.1 as authorization.

## 4. Execution boundary

| In scope | Out of scope |
|---|---|
| Filename corrections | Any doctrine text change |
| Adding unlisted files to the index | Any change to what a document says |
| Adding role lines and status labels | Resolving the Manager conflict |
| Recording the Round 2 map's scope | Retiring or adopting any document |

The repair touches `DISPATCH_REPO_MANIFEST_v3.md` and `SUPERSESSION_MAP.md` in the **Claude-3**
governance repository. It touches **no file in the Dispatch implementation repository** and **no
code anywhere**.

## 5. Decisions required before execution

1. **R-2** — what happened to the stress-test prompt: used and retired, never written, or located elsewhere?
2. **R-3** — confirm the six unlisted documents are current, and confirm the two self-declared "Proposed" doctrines stay PROPOSED.
3. **R-4** — Round 2 map: current-scope-limited, or superseded in part? (Recommendation: superseded in part.)
4. **R-5** — approve the status vocabulary and the initial assignment.

Nothing in this plan executes until these four are answered. Three of the four are single-word
answers; R-2 is the only one requiring recall.
