# Dispatch — Known Limitations

**Current as of:** 2026-08-25. **This is a living document.** When something on it is fixed,
the entry moves to §6 with a date rather than being deleted — an entry that quietly vanishes
teaches nobody anything.

Companion documents: `docs/readiness/OPERATIONAL_PROOF.md` (what is proven) and
`docs/architecture/DISPATCH_ARCHITECTURE.md` §7 (where code conflicts with doctrine).

---

## 0. Dispatch is operating on Mike's Windows laptop — 2026-08-25

Sections 1 and 7 below were written when nothing had ever run on his machine. They are left
in place rather than rewritten, so the change is visible.

**It launches, signs in, and renders.** Double-click, first-run setup (idempotent on a
second run), server started with a real process ID, browser opened, PIN accepted, `/home`
rendering with the sidebar reading "Dispatch — Operations Cockpit". Every Control Center
control reported working.

**The cause of the earlier 500s is known and was never what I claimed.** Not a damaged
database — his `dispatch.db` passes `integrity_check` — and nothing to do with the D: drive.
He had **three copies of Dispatch**, and the one holding port 8080 all day was
`C:\Dispatch\Dispatch\Dispatch-main`, whose extraction was incomplete: `dispatch\connectors`
was missing entirely. `ModuleNotFoundError: No module named 'dispatch.connectors'`, on every
page that opens the database. `/login` worked because it opens none.

Deleting the broken copies and starting from the complete one fixed it.

**Two lessons worth keeping.** A launcher that correctly refuses to start a second server
will happily leave a *broken* first server running — the refusal is about the port, not about
whether the running code is sound. And three rounds were spent on a corrupt-database theory
that reproduced the symptom exactly; a truncated database and a missing module produce an
identical page, and only the log distinguished them. The log existed from the first attempt.

Detail: `docs/readiness/OPERATIONAL_PROOF.md`.

## 0b. Second operating session — 2026-09-05

Dispatch was started and stopped nine times from `D:\Dispatch` at commit `d831b7e`, on Mike's
machine, to record acceptance evidence. Nine of the fifteen items in
`LAUNCHER_PROOF_TEMPLATE.md` now carry real output: **2, 3, 4, 5, 6, 7, 11, 12, 13**.

### The open defect this session found: graceful shutdown never succeeds

Every stop — all nine — reported the same thing:

> `The operating system refused the request to close the process.`
> `Process ID NNNNN did not close within 10 seconds, so the launcher escalated to a forced stop.`

The outcome is correct every time. The process does die, `tasklist` confirms it, and the launcher
states plainly what it did rather than claiming a clean stop. **But a ten-second wait and a forced
kill on every single stop is not the intended path.** No test can see this: the suite never spawns
a real Windows process, so the graceful path has never been exercised anywhere but here.

Not yet diagnosed. Recorded so the next reader does not rediscover it.

### Two test-method traps, recorded because both looked like defects

**A hand-written PID record is not a stale record.** A synthetic `dispatch-portal.pid` carrying only
`pid`, `recorded_at`, `command`, `host` and `port` was **ignored** and Dispatch started normally —
no stale-record message at all. That is correct behaviour: an unparseable record is not a stale one.
But from outside it is indistinguishable from the feature being broken. A synthetic record must
carry `created_token`, `command_line` and `log_path`. With a genuine record whose `pid` was rewritten
to `999999`, the launcher said exactly what it should: *"The stale record was cleared."*

**Blanking a secret is not unsetting it.** `PORTAL_SECRET_KEY=""` did not reach the refusal path —
start proceeded normally. The variable had to be genuinely removed (`env -u`) before the launcher
said *"Dispatch cannot start because PORTAL_SECRET_KEY is not set."*

Both traps produce a false negative that reads as a false defect. Anyone re-running these items
should know.

### Reported from use 2026-09-05, FIXED 2026-09-06: the document checklist could not be ticked

**Mike's report:** the check mark in Document Status in the Driver Portal does not work.
**Confirmed.** It is wider than the arrival notice, and it blocks the delivery completion chain.

**What does work.** The Arrival Notice line ticks correctly. It is driven by `arrived_at`, and on
`SBX-DISPATCH-LOAD-20260729-001` that field is set — Mike pressed ARRIVE on 2026-09-02 at 20:39:41,
`arrival_notice_drafted_at` was written, and no error was recorded. Rendering that real record
produces `[X] Arrival Notice`.

**What does not.** Every other item on both checklists ticks only when `artifacts_held` contains its
name. **Nothing in the running application ever writes that field.**

| `artifacts_held` | Where |
|---|---|
| Read | `portal/cockpit.py:428` — one site |
| Written | `tests/test_driver_cockpit.py` — lines 119, 124, 128, 262, 297, 367 |
| Written in application code | **nowhere** |

The checklist rows in `portal/templates/joe_portal.html` are plain `<li>` elements carrying a
`<span class="box">`. There is no `<input>`, no `<button>` and no click handler, so a tap on the box
does nothing. `UPLOAD DOCUMENTS - PHOTOS` carries `data-action="upload"` with **no JavaScript
handler and no route behind it** — a dead control.

**Consequences, in order of seriousness:**

1. `document_status(...)["complete"]` requires every item done, so it **can never be `True`** in the
   running application. The tick beside `DOCUMENT STATUS:` can never appear, and neither checklist
   can ever read `COMPLETE`.
2. `completion_effect()` — Publisher packet → JOE review → Outlook draft — fires only on completion.
   **That chain is unreachable from the user interface.**
3. A driver reading the screen is shown four or five boxes he has no way to satisfy.

**Why the suite does not see it.** `TestDocumentStatus` builds `artifacts_held` by hand and then
asserts on the result. The logic it proves is correct; what no test asserts is that any code path
can *produce* that state. This is the third defect of this shape found in two sessions, after the
graceful-shutdown escalation and the two test-method traps above. **A test that constructs its own
precondition cannot tell you the precondition is reachable.**

**FIXED 2026-09-06, commit `f7d5304`.** Mike ruled: *a tick means I have it in hand, or it was
created by the arrival notice when I hit arrived.* Built to that ruling —

- `POST /portal/mission/<id>/artifact` writes `artifacts_held`, so the field now has a writer
  outside the tests and `document_status(...)["complete"]` is reachable.
- The checklist rows are buttons where they may be ticked. The **whole 52px row** is the target,
  not the box — a gloved thumb on a moving tablet.
- **The Arrival Notice is refused by the route**, `400`. It is stamped from `arrived_at` because it
  is evidence Dispatch sent something, not a claim the driver makes.
- Unticking is allowed; a wrong tap at a dock must be reversible.
- C.O.D. writes `payment_collected_at`, not the artifact list. A collected check is money, not paper.
- An unknown label is refused rather than stored.

`TestTheChecklistCanActuallyBeTicked` adds eleven tests. **`test_the_state_is_reachable_from_the_route`
is the one that was missing** — it ticks every artifact through the HTTP route the screen uses and
asserts the checklist reaches `COMPLETE`, writing `artifacts_held` nowhere by hand.

**The lesson, recorded because it has now cost three defects:** a test that builds its own
precondition proves the logic and says nothing about whether the application can reach it. Where a
state matters, one test must arrive at it the way the screen does.

**Superseded text follows, kept as the record of what was found.**

The repair depended on a decision only Mike could make: whether ticking a document
means *"I have it in hand"* (a tap, recorded on the Mission Record) or *"a photo or scan is stored"*
(which makes UPLOAD the real work — file storage, naming, location on `D:`, retention). The two
build differently and the second cannot be reached without a working camera and signal at the dock.
Recorded here so the choice is made deliberately rather than inherited from whichever gets built.

---

### What was confirmed working

- **Orphan detection.** With the PID record deleted, start refused with `port 8080 is already in use`,
  **named the unclaimed process**, created no second server, and told the operator what to do.
- **Failure reporting.** A non-Dispatch process on 8080 produced one sentence, no traceback, and
  `status` then showed it under `Last start failure` with a timestamp.
- **Secret redaction.** Every `SECRET`/`KEY`/`PASSWORD`/`TOKEN`/`PIN` hit in the launcher log is a
  setting **name** followed by `[REDACTED]`. No value appears. The log directory is outside the
  repository and is not tracked.
- **Launcher and portal agree.** Started independently, both print the same address, the same
  database path and the same three storage roots.

---

## 1. What used to govern all the others

Section 1 below was written when nothing had ever run on Mike's machine. That changed today
and the sections are left in place rather than rewritten, so the change is visible.

**What worked:** the launch file, Python resolution, Flask, the first-run PIN prompt, the
server binding `127.0.0.1:8080`, and sign-in.

**What failed:** every page behind the login gate — `/home` and `/dispatch` both return HTTP
500. `/login` works; it is the only page that neither extends `base.html` nor reads freight
data.

**Not reproduced.** The same code from the same ZIP returns 200 on both pages here.

**Cause unknown.** The traceback has not been recovered yet. Leading hypothesis, recorded as
a hypothesis: `DISPATCH_OPERATIONS_ROOT` is set on that machine — his repository folder has
no `logs` directory, which the default would have created — and that variable moves the
freight database to `<ops root>\Current Workspace\PortalData\dispatch.db`, plausibly onto
an external drive. Not confirmed.

Detail: `docs/readiness/OPERATIONAL_PROOF.md`.

## 1. What used to govern all the others

**Nothing in Dispatch has been run on Mike's machine.** Not one step. Every build session so
far has executed in an isolated Linux container with no reachable Windows filesystem, so:

- the launcher has never started a Windows process,
- no load has moved through a running portal on his hardware,
- `D:\Sandbox\Play Pen` has never been read,
- and no path, drive letter, code page or antivirus interaction has been observed.

Everything is `IMPLEMENTED`. Nothing is `OPERATIONALLY PROVEN`. **15 first-start items and
20 load-proof steps are `UNVERIFIED`** — listed in `docs/readiness/OPERATIONAL_PROOF.md` §3
and §4.

This is not a permission that can be granted. `C:\` and `D:\` are not blocked from the build
container; they are not attached to it.

---

## 2. Not connected

**Every external system is `UNCONFIGURED`.** No ELD, GPS, telematics, traffic, weather, load
board, mapping provider, accounting provider, scanner, or Outlook client. Route Risk has no
feed. All eight connectors report `UNCONFIGURED` honestly; one mock reports `SIMULATED` and
is deliberately not registered.

The connector boundary means adding one is a small governed change rather than a rewrite
(`docs/connectors/PROVIDER_INSERTION.md`). **Nothing is connected today, and no surface
claims otherwise.**

### 2.1 Dispatch does not know hours of service

There is no ELD feed and no HOS source. Fourteen places that stated or implied otherwise
were corrected. Any surface that implies Dispatch knows a driver's HOS is a defect — report
it.

---

## 3. Numbers that are assumptions, not measurements

`_DRIVE_SPEED_MPH`, the fleet MPG fallback, and the average fuel price are **defaults**.
They have never been checked against a real settlement from a real truck.

Everything derived from them — cost estimates, profitability, fuel projections — is an
estimate, is labelled as one, and is only as good as three numbers nobody has verified.
Replacing them with measurements from Level 1 Transport's own trucks is real work with real
value, and it has not been done.

---

## 4. Structural limitations that are accepted, not accidental

| | |
|---|---|
| **The launcher runs a development server** | `app.run()` is Flask's built-in server. There is no WSGI server, no Windows service, no supervisor. Defensible for a single-operator local install; not what belongs on a VPS |
| **Rehearsal records are labelled, not quarantined** | They live in the same tables as live records — travelling the same code path is the entire point. A report written later that forgets `include_rehearsal=False` will count one. The badge is the backstop; the discipline is the operator's |
| **An unverified backup is a hope** | Nothing reads `VERIFIED` without a `restore-verification.json` that only a real, human-performed restore produces. Dispatch will say `UNVERIFIED` forever until then, and it is right to |
| **`dispatch_launcher/` is outside the coverage gate** | Its uncovered lines are Windows-only branches that cannot execute on Linux CI. Measured and reported, not gated — see `docs/readiness/OPERATIONAL_PROOF.md` §2.1 |
| **No migration framework** | Schema is idempotent `CREATE TABLE IF NOT EXISTS`. Adding a table is free; changing a column's meaning is a hand-written job |

---

## 5. Open questions that need Mike, not a builder

Recommendations exist for most of these and are marked as recommendations. None has been
decided.

1. **`ROUTED_TO_MANAGER`** — a legacy Spine state name under a No-Manager rule. It is
   persisted data, so renaming it rewrites audit history. Three options and a recommendation:
   `docs/architecture/DISPATCH_ARCHITECTURE.md` §7.1.
2. **`DISPATCH_LEGACY_TOKENS_UNTIL`** — whether it must be set before deployment was never
   decided. Open since the Repair and Connection campaign.
3. **`REVIEW_AGE_DAYS`** — the threshold has never been chosen against real operating
   experience.
4. **Whether `loads.status` should be absorbed by the Spine.** Two representations of
   lifecycle currently coexist. Not urgent; not free either.
5. **CF-01** — where governance documents live. `governance/` at the root and `docs/governance/`
   both now exist; this document set put the new authority document in `docs/governance/`
   and left the existing `governance/` file where it was rather than moving somebody else's
   record without a ruling.
6. **CF-02** — whether a `DF-` prefix is adopted for Driver-First clause citations.
7. **CF-05 / BM-02** — the Manager question in the build matrix.
8. **Eleven items in `docs/readiness/COMPLETION_REPORT.md` §8**, including the seven Windows
   environment facts the repository cannot establish.
9. **Ten items in `docs/connectors/PROVIDER_INSERTION.md` §7** — which providers to insert
   first, and on what terms.
10. **Whether to rewrite the Jules repository's history** to purge a Werkzeug debugger PIN
    that was committed to its `main` and has since been removed going forward. The repository
    is public. Removing it from history is a force-push over shared history; leaving it means
    it stays retrievable. Neither is free.

---

## 6. Fixed — kept for the record

| Date | Was |
|---|---|
| 2026-08-25 | **The launcher window vanished after Stop, taking the confirmation with it.** `pause >nul` prints nothing, so pressing Return produced no visible response while Python started up — and the natural second press sat in the keyboard buffer and instantly satisfied the *final* pause. The stop prompt is now visible, the keypress is acknowledged immediately, and the buffer is drained before the window asks again |
| 2026-08-25 | **A double-clicked launcher window closed before it could be read.** `dispatch.bat` paused only on a non-zero exit, and `run_menu` returns 0 on EOF — so a window without usable keyboard input printed the whole status block, quit cleanly, and vanished. Reported as *"a black screen that flashed and I almost could read"*, and what it threw away was the exact diagnostic that had been asked for. Both wrappers now wait unconditionally on the double-click path, success included |
| 2026-08-25 | **A crashed page told the operator nothing.** No error handler existed at all, so every unhandled exception fell through to Flask's bare *"Internal Server Error"* — no error name, no statement that the rest of Dispatch was still running, no mention that a log exists. Found on the first Windows run: two rounds went by hunting for a log file the failing page could have named. `portal/errors.py` now names the failure, prints the exact log path, and carries a redacted traceback in a one-click-selectable block; it recognises a damaged database by name and gives the remedy |
| 2026-08-25 | **A fresh install had no sign-in PIN, and no way for a non-developer to create one.** Dispatch started, the browser opened, and every PIN was rejected with *"No identity configured yet. Run cin-portal-init-admin on the server first"* — a console script that only exists after `pip install -e .`, which the launcher does not do. A running server behind a door nobody can open, which is worse than not starting because it looks like success. First run now asks for a PIN in the launcher window and creates the identity through the existing one-time `bootstrap_authority()`. No default PIN was introduced |
| 2026-08-25 | **A forgotten PIN had no recovery path.** `bootstrap_authority()` refuses once an identity exists, so the only way back in was deleting `identity.json` by hand. Added `identity.set_pin()` and `[P] Reset PIN` in the Control Center, gated on physical access and a typed `RESET` confirmation |
| 2026-08-25 | **Dispatch had no launch path a non-developer could find.** `dispatch.bat` existed, was current and worked — but with Windows' default hidden extensions it displayed under the same name as the `dispatch` folder, which Explorer lists first, among 82 root entries. Reported as *"I cannot find it"* and treated as a defect. `DISPATCH_START_HERE.cmd` added: one double-click, generates this machine's security settings, installs Flask if missing, starts, opens the browser, and puts a Desktop icon so the folder is never needed again. Evidence: `docs/readiness/LAUNCH_PATH.md` |
| 2026-08-25 | **The portal could not start if the Route Risk plug-in was absent.** `portal/routes/driver_portal.py` imported `dispatch.route_risk` at module scope, which imported the standalone `route_risk` engine at module scope — so an uninstalled *optional risk advisor* took down blueprint registration, and with it every driver surface, every load and every milestone. A direct violation of the Plug-In Separation Doctrine and of "degradation is permitted, incapacity is not". Reads now degrade to `ABSENT`; writes refuse loudly rather than silently discarding a recorded hazard. Guarded by `tests/test_repository_doctrine.py` |
| 2026-08-25 | **The portal called itself "L2-COS Operations Portal" in its own chrome.** The program is Dispatch; the sidebar heading, the login page, ~30 page titles, the startup banner and two package docstrings said otherwise. Renamed across `portal/`, with three test assertions updated and a drift test added so it cannot come back. Recorded as gap 10 in `docs/readiness/COMPLETION_REPORT.md` §10, which is left as written — it is that mission's record, not a live status |
| 2026-08-25 | **`CLAUDE.md` described only the CIN-Lite half of the repository**, so a cold-start builder concluded Dispatch was a contract-archiving tool. Rewritten as a full cold-start brief; the conflict is recorded in `CLAUDE.md` §1 rather than quietly overwritten |
| 2026-08-25 | **The README's CI badge pointed at `jax1313-outlook/cin-hybrid`**, a repository this is not. Corrected to `jax1313-outlook/Dispatch` |
| 2026-08-24 | `driver_step_milestone` swallowed refused transitions in `except Exception: pass` — a driver tapped a milestone, nothing was recorded, and the screen said it worked. The classic 70 MPH Test failure |
| 2026-08-24 | `check_evidence_path` crashed the readiness check when the upload directory could not be created, because `_get_upload_dir()` raises `OSError` |
| 2026-08-24 | `.gitattributes` ordering silently disabled the CRLF rule for the Windows wrappers — last matching pattern wins, and the catch-all was last |

---

## 7. The exact next operational blocker

> **CLEARED 2026-09-07. All fifteen first-start acceptance items are recorded `LIVE`.**
>
> The last six were proven by running the launcher on Mike's machine and reading its real output:
> item 1 by invoking `dispatch.bat` the way Explorer does; 9 and 10 from the rendered menu; 14 by
> asking Reset Session to run while Dispatch was live and being refused by process ID; 15 by
> killing a process behind the launcher's back to create a genuinely stale record, clearing it, and
> confirming every load, milestone and opportunity survived.
>
> **Item 8 needed no external drive.** It tests the reporting vocabulary, not the hardware, and all
> four states were proven: `UNCONFIGURED`, `ABSENT`, `UNVERIFIED`, and `VERIFIED` after a real
> backup, hash verification, restore, and a read of the restored database showing 36 tables,
> `integrity=ok`, and row counts identical to the live one.
>
> **The next operational blocker is now PILOT-01 — one real load, end to end.** Nothing stands
> between Dispatch and that except freight.

Updated 2026-08-25. Everything that came before this is cleared. Dispatch launches, signs in
and renders on the target machine.

What remains is the gap between *"it worked"* and *a record that proves it worked*. Roughly
half the fifteen items have no observation at all behind them yet — the full status block
cross-checked against the portal, Stop confirming the process is gone, Restart proving the
old one died, an orphan being reported rather than duplicated, a failed start explained in
one sentence with secrets redacted, backup status, and **Reset Session refusing while
Dispatch is running**, which is the one that matters most and is untouched.

After that, and only after that, the twenty-step load proof
(`docs/readiness/OPERATIONAL_PROOF_PROCEDURE.md`) — run as a **rehearsal** first, on records
that can never pass for a live mission.

**Do not enter a real revenue load before the rehearsal passes.**

Still cannot be done from a build container. It has to be done there.
