# Dispatch — Operational Readiness Mission: Completion Report

**Program:** Dispatch · **Executed by:** Claude Code (implementation engineer)
**Date:** 2026-08-24 · **Branch:** `claude/dispatch-repo-context-reconcile-7mblbb`

---

## 1. Readiness statement

Dispatch now has a Windows-native way to start, stop, restart and inspect itself
(**IMPLEMENTED**); a rehearsal mode whose records cannot pass for a live mission and a
twenty-step operational-proof system that generates its own evidence document
(**IMPLEMENTED**); a read-only tool that will inventory and classify your Sandbox without
touching a byte of it (**IMPLEMENTED**); and a governed boundary through which every future
external system must pass, with all eight connectors reporting `UNCONFIGURED` honestly and
one mock reporting `SIMULATED` (**IMPLEMENTED**). Fourteen places that stated or implied
Dispatch knows a driver's hours of service were corrected (**IMPLEMENTED**). **Nothing in
this mission is OPERATIONALLY PROVEN.** Not one step has run on your machine: the launcher
has never started a Windows process, no load has moved through a running portal on your
hardware, and `D:\Sandbox\Play Pen` was never read — it is unreachable from this build
environment, which is an isolated Linux container. Everything the mission asked to be
proven on your machine is therefore **`UNVERIFIED`**, and the two proof documents say so on
their first line by construction rather than by convention.

## 2. Commit, version, tests and coverage

| | Before | After |
|---|---|---|
| Commit | `609f4c4e8348b42881a8694da4dbe29df3c1fec1` | the merge commit of this pull request; the last commit before it is recorded in the PR |
| Version | `0.1.0` | `0.1.0` (unchanged) |
| Tests passed | 3,087 | **3,577** |
| Failed / skipped / warnings | 0 / 0 / 0 | **0 / 0 / 0** |
| Coverage (gated: `cin_lite`, `dispatch`, `portal`) | 93.73% | **94.37%** |

New tests by task: Task 1 — 103 · Task 2 — 123 · Task 3 — 77 · Task 4 — 187.
No test was skipped, weakened, removed, or marked expected-to-fail. No warning was
introduced or suppressed.

**One coverage figure deserves stating plainly rather than burying.** `dispatch_launcher/`
is at **84.46%**, below the repository's 90% gate, and it is deliberately **not** in the
gated set. The uncovered lines are Windows-only branches — `taskkill`, `tasklist`,
`Get-CimInstance Win32_Process`, `py.exe` resolution, detached process creation — that
cannot execute on the Linux CI that runs this suite. Adding the package to the gate would
have measured how much Windows code exists rather than how well it is tested, and lowering
the gate to accommodate it would have weakened the gate for everything else. The honest
position is the one taken here: measure it, report it, and record every one of those
branches as `UNVERIFIED` in `LAUNCHER_PROOF.md`.

---

## 3. Task 1 — Dispatch Launcher and Control Center

### Implementation choice, and what was rejected

A Python control core (`dispatch_launcher/`) with thin wrappers over it — `dispatch.bat`
to double-click, `Dispatch.ps1` for a PowerShell console, `python -m dispatch_launcher` for
everything else — presenting a numbered text menu: Start, Stop, Restart, Open Portal,
Refresh status, Quit. A desktop GUI was rejected because it means a framework dependency
the mission forbids, a second thing to keep working across Python upgrades, and a control
surface that cannot be driven from a scheduled task or read aloud over the phone. A pure
batch or PowerShell launcher was rejected because a script in this repository cannot be
tested, and every interesting decision here — is that process actually the Dispatch server,
did Stop really work, what does this failure mean in plain language — is exactly the kind
that must be tested. A local control web page was rejected because a control that only
works when the thing it controls is already running cannot start it. So the wrappers hold
no logic at all, and the package that holds all of it is exercised by 103 tests.

### It is a control, not a second Dispatch

Enforced, not merely intended: the package never imports `dispatch.services`,
`dispatch.store` or `dispatch.spine.*`, never opens the operational database, and has no
code path that could create or modify a load, milestone, settlement or any other
operational record. `tests/test_launcher.py::TestNoPathToCurrentReality` asserts this
against a real interpreter, so a future edit that crosses the line breaks the build. It
observes two things only — operating-system process state and what the portal *would*
resolve if it started right now — and it reads the second through the application's own
resolvers in a subprocess, never re-implementing them, so it cannot drift into reporting a
database location or a port the portal does not actually use.

### Proof summary

`proof/launcher/LAUNCHER_PROOF.md` (committed copy: `docs/readiness/LAUNCHER_PROOF_TEMPLATE.md`)
carries all eight Section 3.5 acceptance items. **Every one is `UNVERIFIED`**, each with the
exact command you run and a blank Observed column to paste real output into.

The document also carries an appendix recording a **container exercise on Linux**, which
moves no item off `UNVERIFIED` and says so: Start created one process; a second Start
refused and named how it identified the process — *"confirmed by process start time and
command line"*, identity rather than a bare PID; the portal answered HTTP 200; Restart
stopped the old PID and stood up a new one with the old confirmed dead; Stop left no
`portal/app.py` process and a port that refuses connections; and the launch log recorded
the environment as `{"DISPATCH_EMAIL_SECRET": "[REDACTED]", "PORTAL_SECRET_KEY":
"[REDACTED]"}` with zero occurrences of either real value anywhere in the logs.

**A real bug was found and fixed in the launcher during its own testing**, and it is the
same class of defect as the one below. When the menu process stays open, the server it
started is its child — so a stopped server becomes a zombie, `os.kill(pid, 0)` still
succeeds, and `/proc/<pid>` still exists. A naive liveness check reports "Dispatch did not
stop" for a stop that worked, then refuses to restart. `processes.pid_alive` now reaps its
own children and treats a zombie as gone. This is why the exercise above could observe a
"still alive" PID moments after a successful Stop and a fully absent one seconds later.

That appendix also records a mistake worth keeping. The first liveness check used
`ps -p <pid> && echo ALIVE` and reported a stopped process as still running; that `ps`
build exits 0 whether or not the PID matches, so the check was meaningless. The launcher's
own report was correct throughout. This is the exact failure mode Section 4.3 step 16
warns about — a false pass on the one thing the step exists to prove — encountered in the
harness rather than the product, and it is why the proof procedure tells you to believe the
PID rather than the browser.

### Unverified items, and the command for each

| # | Item | Command |
|---|---|---|
| 1 | The launcher opens without typing a Python command | Double-click `dispatch.bat` |
| 2 | Every display is read from this machine's real configuration | `python -m dispatch_launcher status` |
| 3 | Start creates exactly one server process | `dispatch.bat` → `1`, then `python -m dispatch_launcher status` |
| 4 | A second Start does not create a duplicate | Run Start twice; the second must say "already running" |
| 5 | Open Portal reaches the running portal | `dispatch.bat` → `4` |
| 6 | Stop terminates the real process and confirms it is gone | `dispatch.bat` → `2`, then check the PID yourself |
| 7 | Restart proves the old PID dead before the new one exists | `dispatch.bat` → `3` |
| 8 | Displayed storage paths match what Dispatch actually uses | `python -m dispatch_launcher status` beside `python portal\app.py` |

`run_portal.bat` is left in place — it is referenced by `README.md`, `DEPLOY_LOCAL.md` and
the W0-2 procedure — but its banner no longer calls the program "L2-COS", and it now points
at `dispatch.bat`. The portal's own UI chrome still says "L2-COS Operations Portal" in
around twenty templates and several test assertions; renaming that is a separate change with
real blast radius and was not made here. It is recorded in Section 10 as a known gap rather
than done quietly as part of this mission.

Six Windows-only unknowns — `py.exe` presence, `Get-CimInstance` permission, `taskkill`
availability, whether the `D:` environment variables reach a double-clicked `.bat`,
Defender/SmartScreen interference with a detached process, and console code-page rendering
— are listed in the proof document as questions rather than assumptions.

---

## 4. Task 2 — Real-Load Operational Proof System

### Result line

> **REHEARSAL NOT YET RUN ON TARGET MACHINE**

This is generated, not written by hand. `ProofRun.headline` returns `REHEARSAL PASSED` only
when every step was performed **and** the machine is named; a test asserts that a
fully-performed run on an unnamed machine still reads NOT YET RUN.

### What Mike performed / Code verified / remains unverified

- **Mike performed:** nothing. `ABSENT`.
- **Code verified** — in this container, against a throwaway database, and therefore
  evidence of software behaviour only: steps **3–8, 11–15, 18–20**, end to end. That
  includes a real backup and a real restore into an isolated destination, with record
  identifiers and evidence SHA-256 hashes compared side by side and coming back matching.
- **Remains `UNVERIFIED`:** steps **1, 2, 9, 10, 16, 17** — start, authenticate, Outlook,
  driver receives the mission on the phone, stop, restart. Those six are precisely the ones
  that make a proof operational, which is why `automated_rehearsal` structurally cannot
  print PASSED no matter how well it runs.

### Rehearsal mode

A `rehearsal_session` column on seven tables — loads, drivers, equipment, milestones,
evidence, exceptions, POD packages. One TEXT column rather than a boolean plus a join
table, because purge needs to know *which* rehearsal, and a join is how exclusion quietly
stops happening. Tagging occurs **in the write path**, on the caller's open transaction, so
a record created through the portal during a rehearsal is tagged by the same mechanism as
one created by the proof script and is never committed unlabeled.

Two labels, doing different jobs: a **banner** on every portal and driver page while a
session is active, and a **badge** on the record that outlives the session — so a rehearsal
load opened six months later, with rehearsal mode long off, still says what it is. Sessions
require an explicit actor, refuse an empty one, and refuse reserved system identities.
Activation is a `ContextVar` or an environment variable and deliberately **not** an HTTP
endpoint: a surface that can be clicked into rehearsal can be clicked out of one, and the
second direction is the dangerous one.

Purge is implemented, gated behind an explicit actor and `confirm=True`, and called by
nothing in this repository. It defers foreign-key enforcement to COMMIT rather than
disabling it, and finds dependent rows from the schema itself, so a table added next year is
purged correctly without that function changing.

### Exact paths (this container — **not** your machine)

| | |
|---|---|
| Database | `/home/user/Dispatch/portal/data/dispatch.db` |
| Evidence store | `/home/user/Dispatch/portal/data/uploads` |
| Backup destination | supplied per run; never defaulted |
| Restore destination | supplied per run; never defaulted |

Dispatch will not choose a backup or restore destination on your behalf, and the readiness
check refuses any destination that overlaps a live path after resolving `..` and symlinks.

### Outlook status

**`ABSENT`.** Dispatch creates no calendar event and holds no Outlook credential. Step 9 is
a human action in Outlook, recorded as `LIVE`, `SIMULATED`, `MANUAL` or `ABSENT` and
validated against exactly those four words.

### Real-load readiness checklist

Twelve conditions, in `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md` Part 2. **All twelve
read `UNVERIFIED`**, because none has been executed on your machine. Part 3 of that document
is the live-load procedure: written, and explicitly not authorized — running a live revenue
load is your decision (Section 8 item 3).

Pointer: `proof/load/OPERATIONAL_LOAD_PROOF.md`, committed copy
`docs/readiness/OPERATIONAL_LOAD_PROOF_TEMPLATE.md`.

---

## 5. Task 3 — Sandbox knowledge recovery

### Files inventoried: **zero**. Class counts: **none**. Sensitive material found: **none**.

Not because the Sandbox is empty — because it was never read, and could not be.

`D:\Sandbox\Play Pen` is a Windows path on your machine. This build environment is an
isolated Linux container: `/d`, `/mnt/d` and every entry under `/mnt` were checked and none
is a Windows volume. There is no mount, no network path and no credential here that reaches
it. That is an environment boundary, not a permission that could have been granted.

**Read-only pass confirmation:** vacuously true, and stated plainly rather than dressed up.
Not one file under that path has been read, listed, hashed, sampled, classified, moved,
renamed, copied, deleted or executed. **The output folder `D:\Sandbox\Play Pen\Dispatch`
was not created.** No statement anywhere in this mission's output describes the Sandbox's
actual contents.

**No organization action was taken, and none could have been.** There is no move, rename,
or merge code path anywhere in the survey package — not behind a flag, not behind a
confirmation prompt. An AST test over the package's own source proves it.

### What shipped instead

Section 5.2 anticipates exactly this case: *"If the tooling you build for this task … lives
in the repository, it ships in the PR with tests proving it performs no write operation
against its input path."*

- `dispatch/sandbox_survey/` — scanner, deterministic rule-based classifier over the closed
  eleven-class vocabulary, exact **and** near-duplicate detection with the evidence for each
  match, 17 sensitive-material detectors, report generators, and a single write choke-point.
- `scripts/sandbox_survey.py` — the CLI, with `--dry-run` that creates nothing at all.
- All **nine** required outputs in template form, every content claim marked `ABSENT`:
  `docs/readiness/sandbox_templates/` (committed) and `proof/sandbox/` (gitignored).
- `docs/readiness/SANDBOX_SURVEY_PROCEDURE.md` — the PowerShell commands you run.

**How read-only is enforced in code, not documentation:** every input read is
`open(..., "rb")`; the only non-`"rb"` open in the whole package is one `open(target, "x")`
inside the choke-point, and mode `"x"` cannot truncate; `mkdir` exists in exactly one place;
the writer rejects any destination whose *resolved* path is outside the output root, so a
symlinked subfolder cannot smuggle a write out; and the run refuses outright if the output
root is not inside the input root.

**Proven by**, among 77 tests: a byte-identity snapshot of a temporary input tree — type,
size, `st_mtime_ns`, SHA-256, symlink targets — taken before and after a full run, asserting
every pre-existing path is unchanged and every new path is inside the output folder; AST
proofs that no move, rename, merge or delete exists and that exactly one write call exists
package-wide; a sentinel proving a `.py` and a `.sh` found in the tree are never executed;
a proof that no socket is opened; that a symlink out of the root is recorded but never
followed; and that a fabricated credential planted in the tree appears in **none** of the
eleven generated outputs — while the detectors still fire, so the test cannot pass vacuously.

`SensitiveFinding` carries four fields — path, category, detector id, hit count. There is no
fifth field, no `context` argument and no `--show-matches` flag, so no report can quote file
content even by accident.

The tool's behaviour against your real Sandbox is `UNVERIFIED` until you run it.

---

## 6. Task 4 — Connector architecture

### The eight connectors and their honest statuses

| Connector | Status | Provider |
|---|---|---|
| Route Risk | `UNCONFIGURED` | no provider selected |
| Accounting | `UNCONFIGURED` | no provider selected |
| Scanner | `UNCONFIGURED` | no provider selected |
| Outlook | `UNCONFIGURED` | no provider selected |
| Email Transport | `UNCONFIGURED` | Archive/Outbox `.eml` fallback (no relay configured) |
| Load Board | `UNCONFIGURED` | no provider selected |
| Mapping and Routing | `UNCONFIGURED` | no provider selected |
| Future External Intelligence | `UNCONFIGURED` | no provider selected |
| *Mock Route Risk* | `SIMULATED` | mock, used only by tests |

Read live from `registry.status_board()` while writing this report, not transcribed.

### The boundary is structural

`dispatch/connectors/boundary.py` parses the package's own source: it follows **transitive**
first-party imports and extracts SQL table names, then refuses `dispatch.spine`,
`dispatch.services` and `dispatch.store` and any write to a Current Reality table.
`verify_package()` returns no violations and `assert_package_clean()` passes — run directly
against the shipped code while writing this section, not merely asserted in a test file.
A runtime `sealed()` guard covers the case AST analysis cannot see.

A connector may never own a lifecycle transition, a human decision, pricing authority,
acceptance authority, scheduling truth or operational doctrine. Every connector declares
that in its own capability block, and the boundary enforces it.

### Existing integrations were wrapped, not duplicated

The Email Transport Connector reports on `cin_lite/email_delivery.py` — the program's sole
mail transport — without changing its behaviour, and maps its two real states honestly: a
configured SMTP relay would be `CONFIGURED`, and the `.eml`-to-Outbox fallback that is
actually in force reports as such rather than as a working mail system. The Outlook
Connector wraps the scheduling-fit code in `dispatch/opportunities.py` and creates no event;
Outlook remains the single source of scheduling truth. The Accounting Connector fronts
`dispatch/accounting_export.py`. Nothing was reimplemented.

### Resilience proof (Section 6.7): **passes**

`tests/test_connectors.py::TestCoreOperationSurvivesEveryConnectorBeingUnconfigured` asserts
every connector is `UNCONFIGURED`, then drives a load from creation through driver
assignment, seven milestones, evidence upload and delivery — with no transition refused —
and asserts the connectors are still exactly as honest afterwards. A second test proves a
function that *needs* a connector fails with a labeled refusal naming the connector, its
status and the missing setting, rather than degrading silently. A third proves an
`UNAVAILABLE` connector (mock in timeout mode, retries exhausted) does not stop a load
moving.

### Audit

Every connector attempt writes one row to `connector_audit` — including attempts that never
left the building — recording connector, provider, operation, truth word, outcome
(`ok` / `refused` / `failed`), the labeled refusal sentence with secrets redacted at
construction, attempt count, and on a `LIVE` row the SHA-256 of the response. A blank field
beside an empty table is indistinguishable from a provider that answered with nothing; this
table exists so that sentence can be written instead.

Provider insertion: `docs/connectors/PROVIDER_INSERTION.md` — six steps, identical for all
eight, with the Mike decisions that gate activation collected in its Section 7.

---

## 7. HOS / ELD corrections (Section 1.6)

Dispatch is not an ELD. It holds no duty-clock data, has no telematics feed, and has no
GPS. The driver is responsible for legal HOS compliance. Every location below stated or
implied otherwise and was corrected in this mission.

| # | Location | Before | After |
|---|---|---|---|
| 1 | `dispatch/scoring.py::compute_hos_risk` | No docstring; the function's name and key read as an hours-of-service reading | Docstring states plainly that it is a drive-time estimate from distance and appointment window, that Dispatch is not an ELD and holds no duty-clock data, and that the `hos_` names are kept only so no caller or stored record changes shape |
| 2 | `dispatch/scoring.py::compute_hos_risk` return | `"Critical — 9.2h exceeds single-day HOS limit"` | `"Critical — 9.2h estimated drive time exceeds a single driving day. Estimated from distance; Dispatch holds no ELD reading."` |
| 3 | `dispatch/scoring.py::compute_hos_risk` return | `"High — 7.1h estimated drive time"` | `"High — 7.1h estimated drive time (no ELD reading)"` |
| 4 | `portal/templates/dispatch.html` opportunity card | `HOS Risk: {value}` | `Drive-Time Risk (estimated, no ELD): {value}` |
| 5 | `portal/templates/brief.html` heading | `Position / HOS Assessment` | `Position / Drive-Time Assessment (estimated — Dispatch is not an ELD)` |
| 6 | `portal/templates/brief.html` field | `HOS Risk:` | `Drive-Time Risk (estimated):` |
| 7 | `DISPATCH_DYNAMIC_CAPACITY_ARCHITECTURE.md` §"Reality Bound" | "must be rooted in verified asset states (driver HOS log, truck GPS, assigned load weight/volume)" | "must be rooted in asset states whose provenance is recorded… Driver HOS and truck GPS are listed here as *intended future inputs from a live trusted external source*; no such source exists" — plus the refusal behaviour `capacity.py` already enforces |
| 8 | `CURRENT_REALITY_VS_POSSIBLE_FUTURES_ARCHITECTURE.md` Current Reality box | `Truck / Asset Position (Verified GPS / HOS)` | `Truck / Asset Position (no GPS or HOS feed exists)` |
| 9 | `WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md` "Available Capacity" | "available driver HOS" | "estimated drive-time headroom (not a duty-clock reading — Dispatch holds none)" |
| 10 | `WEEK_VIEW_CAPACITY_VISUALIZATION_ARCHITECTURE.md` "Reserve Capacity" | "2 hours HOS reserve" | "a 2-hour drive-time reserve… a planning allowance, not a measured remaining duty clock" |
| 11–14 | The four architecture documents above **and** `DISPATCH_OPERATIONAL_INTELLIGENCE_PLAYBOOK_v1.md` | No boundary statement; the Playbook's worked examples describe HOS telematics as though a feed existed | A standing **HOS / ELD boundary** note immediately under each title, stating that Dispatch is not an ELD, that no ELD/GPS/telematics integration exists or is configured, that every HOS reference is either an estimate or a future capability requiring a source that does not exist, and that the driver is responsible for legal compliance |

**Already correct, verified not regressed:** `dispatch/capacity.py` — `set_verified_hos` requires
an explicit source and a timezone-aware `observed_at`; `hos_status` of `UNKNOWN` or `UNAVAILABLE`
makes the drive-hours comparison **unavailable**, not optimistic; `ESTIMATED` is reported as
"an estimate from {source}, not a verified reading"; `STALE` is flagged rather than passed.

**Section 1.6's operational-visibility requirement is met.** The driver portal has the five
required buttons: `AT PICKUP` (arrival), `IN TRANSIT` (departure), `DELIVERED` / `MARK
DELIVERED`, POD photo upload, and `Report Exception` — `portal/templates/driver_home.html`,
lines 151–180.


---

## 8. Mike-only decisions (Section 8) — recommendations, marked as recommendations

Each of these is yours. None was resolved, defaulted, or worked around. Everything that did
not depend on the answer was completed.

| # | Decision | Status | **My recommendation — a recommendation only** |
|---|---|---|---|
| 1 | Executing `PROPOSED_ORGANIZATION_ACTIONS` from Task 3 | **Not applicable yet.** The Sandbox was never read (Section 5), so no actions were proposed. | Run the survey yourself first with `--dry-run`, read the nine outputs, then decide. There is no code path in the tool that can execute a move, rename, or merge — even behind a flag — so this decision cannot be taken by accident. |
| 2 | Accepting any `Doctrine` or `Decision` candidate as actual doctrine or decision | **Open, and nothing to accept yet.** | Keep the rule the classifier already enforces: architecture research is not accepted architecture, notes are not doctrine, AI-generated reports are not human decisions. Accept candidates one at a time, into `DECISION_LOG.md`, with your words quoted verbatim. |
| 3 | Running a live revenue load through Dispatch | **Open — and the readiness checklist for it is 12 lines, all `UNVERIFIED`.** | Do not, until the rehearsal reads **REHEARSAL PASSED** on your own machine. `docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md` Part 2 is the list; Part 3 is the procedure, written and deliberately not authorized. |
| 4 | Activating any real external provider behind any connector | **Open.** Every connector reports `UNCONFIGURED` except the mock, which reports `SIMULATED`. | Activate at most one at a time, and read `docs/connectors/PROVIDER_INSERTION.md` for that connector first. A connector that starts returning real data changes what the portal shows without changing a single line of portal code — that is the point of the boundary, and also the risk of it. |
| 5 | Any live Outlook event creation not already governed by existing authorized code paths | **Open — and nothing was added.** Dispatch creates no calendar event today. | Leave it that way for now. Outlook stays the single source of scheduling truth, and a Dispatch that can write to it is a Dispatch that can create a second one by accident. |
| 6 | Any change to `loads.status` semantics or Spine transition rules | **Open — nothing changed.** | No change is needed for anything in this mission. Revisit only alongside the still-open question of whether `loads.status` should ever be absorbed by Spine. |
| 7 | Any change to the authoritative-portal decision | **Open — nothing changed.** `Dispatch/portal/` remains Dispatch; the Jules portal remains a read-only design archive, and nothing of its runtime, security, state, or upload behaviour was adopted. | Leave the adjudication as it stands. |
| 8 | Any HOS/ELD input, now or later | **Open.** No feed exists; 14 places that implied one were corrected. | If you ever add one, it enters through the Route Risk Connector or a new HOS connector and reports `LIVE` only on an evidenced exchange. Until then `capacity.py` must keep refusing to call a reading `VERIFIED` without a named source. |
| 9 | Any deletion or purge of data, including rehearsal data, on your machine | **Open — and nothing was purged.** | Use `dispatch_proof.py purge-plan <session>`, which reports and deletes nothing. Purging is optional: rehearsal records stay labeled forever, so leaving them is safe. |
| 10 | Any change to the designated Task 3 paths (`D:\Sandbox\Play Pen`, `D:\Sandbox\Play Pen\Dispatch`) | **Unchanged.** Both remain the defaults; both are CLI flags so a change needs no code edit. | Keep them. |
| 11 | Any Windows-environment fact the repository could not establish | **Seven, listed below. None was assumed.** | Answer them once and the launcher's status panel will report most of them back to you thereafter. |

### 11 — the seven Windows facts the repository cannot establish

1. Which Python interpreter is on `PATH`, and whether `python` or `py -3.11` is the working invocation.
2. Whether Dispatch is installed with `pip install -e .` or run from the repository directory.
3. Whether the five `DISPATCH_*` / `PORTAL_*` environment variables are actually set on the machine.
4. Whether port 8080 is free.
5. Whether `D:` exists and is writable, and whether `setup_dispatch_folders.ps1` has been run.
6. Whether real values for `PORTAL_SECRET_KEY` and `DISPATCH_EMAIL_SECRET` are set — without them, operational mode refuses to start at all.
7. Whether the Authority PIN identity has been bootstrapped (`cin-portal-init-admin`).

---

## 9. Doctrine compliance check (one line per Section 1 item)

| Item | Compliance |
|---|---|
| **1.1** Mike is final authority | **Complies.** No artifact in this mission bears a Mike attribution. `rehearsal.start_session` requires an explicit `actor_id`, refuses an empty one and refuses reserved system identities; `proof.StepResult` defaults every performer to `not performed` and accepts only `Mike`, `Code-automated`, `not performed`; two tests assert the five forbidden phrases appear in neither the rendered report nor the run's JSON. |
| **1.2** Spine + Opportunity | **Complies.** Nothing in this mission computes or persists a lifecycle transition. The rehearsal walks `services.add_milestone`, whose status cascade is already gated by `validate_status_transition`; the launcher cannot import the lifecycle modules and a test enforces it; connectors are structurally barred from Spine and from Current Reality. |
| **1.3** Current Reality vs Possible Future | **Complies.** Rehearsal records are Current Reality that is *labeled*, not Possible Future silently promoted — which is why the badge outlives the session. Connector payloads carry status and provenance and cannot write Current Reality. The launcher observes process and configuration only. |
| **1.4** Driver-First / 70 MPH | **Complies.** The driver surfaces gained one full-width banner and one badge on the Active Mission card; no tap was added, no screen was moved, no refusal was made quieter. The banner is the fastest possible answer to "is this real". |
| **1.5** Scheduling truth | **Complies.** Dispatch creates no Outlook event anywhere in this mission. Proof step 9 is a human action in Outlook, recorded as `LIVE`, `SIMULATED`, `MANUAL`, or `ABSENT` and validated against exactly those four words. |
| **1.6** HOS / ELD boundary | **Complies, with 14 corrections** — Section 7 above. |
| **1.7** Fuel receipts | **Complies — untouched.** The five-link ownership chain (driver, truck, timestamp, jurisdiction, receipt evidence) and the rule that an active load is optional and never fabricated were landed earlier and are unchanged by this mission. |
| **1.8** Truth vocabulary | **Complies, and is enforced in code.** `readiness.CheckResult.__post_init__` and `proof.StepResult.__post_init__` raise on any word outside the eight; `ProofRun` restricts step 9 to the four Section 4.3 permits. No synonym or softer variant appears. |
| **1.9** Application code vs local-machine proof | **Complies.** Every readiness statement in this report is tagged. The proof report says in its own header that repository test results are not cited as operational proof, and `ProofRun.headline` structurally cannot print PASSED without every step performed *and* a named machine — a test asserts that a fully-performed run on an unnamed machine still reads NOT YET RUN. |

---

## 10. Known gaps and risks — plain language

1. **Nothing in this mission has been run on your machine.** Not one step. The launcher has
   never started a Windows process, the rehearsal has never moved a load through a running
   portal, and the Sandbox has never been read. Everything is `IMPLEMENTED`; nothing is
   `OPERATIONALLY PROVEN`. The proof documents say so on their first line, by construction.

2. **The Sandbox could not be reached, and this is not a permission that can be granted.**
   This session runs in an isolated Linux container. `D:\Sandbox\Play Pen` is on your Windows
   machine; there is no mount, no network path, and no credential here that reaches it.
   Task 3 therefore shipped the tooling and the command, not the survey. You have to run it.

3. **Repository tests are not operational proof, and this report does not treat them as any.**
   The suite is large and it passes. That tells you the software behaves as written. It tells
   you nothing about whether Dispatch starts on your machine, finds your `D:` drive, or keeps
   a load across a restart.

4. **The launcher runs a development server.** `app.run()` is Flask's built-in server. There
   is no WSGI server, no Windows service, and no supervisor anywhere in the repository. For a
   single-operator local install that is defensible; it is not what you would put on a VPS.

5. **A backup is not proven good until it is restored.** The launcher's backup display refuses
   to call a backup valid without a restore verification record, and the proof path makes the
   restore step 20 rather than an optional extra. Take that seriously: an unverified backup is
   a hope, and you will find out which at the worst possible time.

6. **Rehearsal records are labeled, not quarantined.** They live in the same tables as live
   records — deliberately, since travelling the same code path is the whole point. The label
   is on the record and shows on every surface that displays it, and operational queries can
   exclude it. But a report someone writes later that forgets to pass `include_rehearsal=False`
   will count a rehearsal load. The badge is the backstop; the discipline is still yours.

7. **Every external system is `UNCONFIGURED`.** Route Risk has no feed. There is no ELD, no
   GPS, no traffic, no weather, no load board, no mapping provider, no accounting provider,
   no scanner, and no Outlook client. The connector boundary means adding one is now a small,
   governed change rather than a rewrite — but nothing is connected today, and no surface
   claims otherwise.

8. **The fuel and drive-hour constants are still assumptions.** `_DRIVE_SPEED_MPH`, the fleet
   MPG fallback, and the average fuel price are defaults, not measurements from your trucks.
   Everything derived from them is an estimate and is labeled as one, but the numbers
   themselves have never been checked against a real settlement.

9. **The rehearsal exercised in this container used a throwaway database on Linux.** Windows
   path handling, drive letters, long paths, file locking, and antivirus interference are all
   real and all `UNVERIFIED`. The most likely place for a first-run surprise is a path, not
   the logic.

10. **The portal still calls itself "L2-COS Operations Portal" in its own chrome.** The
    program is Dispatch and this mission's header says so explicitly. The sidebar heading,
    around twenty page titles and several test assertions still carry the old name. The new
    launcher and `run_portal.bat` were corrected; the portal's UI was not, because renaming
    it touches templates and tests together and that is a change worth making deliberately
    rather than as a side effect of a readiness mission. It is cosmetic, and it is wrong.

11. **`DISPATCH_LEGACY_TOKENS_UNTIL` is still an open question from the previous campaign.**
    Whether it must be set before deployment was never decided. It is unrelated to this
    mission and remains open.

---

*Nothing in this report is accepted doctrine or a Mike decision. No record produced by this
mission bears a Mike attribution that was not produced by an explicit authenticated human
action — and no such action has occurred.*
