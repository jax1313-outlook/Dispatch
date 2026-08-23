# W0-2 — Delivery Proof Procedure (rehearsed)

**Unit:** W0-2 of `DISPATCH_REPAIR_AND_CONNECTION_CAMPAIGN_v1`
**Purpose:** prove the last link of the source-control model — approved merge → **Mike's machine**.
**Performed by:** Mike Zachary, on Windows. **Cannot be delegated.** No agent can reach that machine;
this document exists so the run succeeds the first time.
**Status of this document:** the procedure below was **rehearsed end to end on Linux** against a
fresh clone of `origin/main` @ `37f4fd0`. What was proven there is marked ✅; what only Mike's own
run can prove is marked ⬜.

---

## ⚠ BLOCKER FOUND IN REHEARSAL — read this first

**The documented Quick Start does not work.** `DEPLOY_LOCAL.md` line 4 of the Quick Start says:

```
pip install -e .
```

That command **fails**, on a clean clone, with current tooling:

```
error: Multiple top-level packages discovered in a flat-layout:
       ['sync', 'portal', 'dispatch', 'cin_lite', 'route_risk', 'reconciliation'].
       setuptools will not proceed with this build.
```

**Root cause:** `pyproject.toml` declares four console scripts but **no package list**. There is no
`[tool.setuptools]` section, no `setup.py`, no `setup.cfg`. Modern setuptools refuses flat-layout
auto-discovery when more than one top-level package is present. Reproduced on Python 3.11.15,
pip 24.0, setuptools 79.0.1.

**Consequence:** `cin-portal-init-admin` is never installed. Per `DEPLOY_LOCAL.md`'s own words,
skipping that step means *"the app runs but nothing past the login page is reachable."* **W0-2 as
documented is not completable.**

> **UPDATE 2026-08-23 — Path B was authorized and applied.** `pyproject.toml` now carries a
> `[tool.setuptools.packages.find]` block; `pip install -e .` works. The blocker below is kept as
> the record of what was found and why the fix exists. **Use the Quick Start as written in
> `DEPLOY_LOCAL.md`**; steps 2 and 4 of this procedure show both paths, and either works.

**Two ways forward. Path A needs no repository change; Path B has since been applied.**

### Path A — run from source (no install). Rehearsed ✅. Still works; no longer necessary.

Everything works; only the `pip install -e .` convenience layer is skipped.

### Path B — fix the packaging. Rehearsed ✅, authorized, and **now applied.**

Four lines appended to `pyproject.toml`:

```toml
[tool.setuptools]
packages = ["cin_lite", "dispatch", "portal", "reconciliation", "route_risk", "sync"]
```

Verified in the rehearsal clone: `pip install -e .` then exits 0, all six packages import from the
installed distribution, and `cin-portal-init-admin` installs and behaves correctly (it refuses a
second run with *"An identity already exists."*).

**Applied 2026-08-23** under the authorization *"2. Packaging repair (Path B)"*. The shipped form
uses `[tool.setuptools.packages.find]` with `include` patterns rather than a literal list: six of
the twelve packages here are subpackages, and a literal list omits them silently — the install
succeeds and `import portal.routes` then fails from the installed distribution. That trap was hit
and backed out during the change. Verified after applying: a real wheel builds, all 19 module
imports succeed from a clean venv with the working directory outside the repository, all four
console scripts install, `pip install -e .` exits 0, and the full suite is **2,817 passed, exit 0** —
unchanged.

---

## The procedure

Run these in order, at a terminal, on the Windows machine. **Do not pipe or script step 4** — the
PIN prompt does not echo.

### 1 · Clone ⬜

```bat
cd C:\where-you-keep-code
git clone https://github.com/jax1313-outlook/Dispatch.git
cd Dispatch
```

*Rehearsed ✅ — 297 tracked files, `main` @ `37f4fd0`, clone completes in ~2 s.*

### 2 · Virtual environment and dependencies ⬜

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

**`pip install -e .` now works** (Path B, applied). If you prefer to skip the install entirely,
`pip install flask` and run from the repository root also works — `flask` is the only hard runtime dependency
(`portal/requirements.txt`). `paramiko` is needed only for `sync/`; `anthropic` only for the
optional Claude summarizer, which falls back deterministically without it.

*Rehearsed ✅ — after this, `import portal.app, portal.cli, dispatch.services` succeeds from the
repository root.*

### 3 · Set the two secrets ⬜

```bat
set PORTAL_SECRET_KEY=<pick a long random string>
set DISPATCH_EMAIL_SECRET=<pick a different long random string>
```

**Not optional in practice, even though nothing enforces it yet.** Both currently fall back to
published defaults (`"dev-portal-key-change-in-production"`, `"dispatch-dev-secret"`) — audit
findings S-1 and S-3. `check_secret_key()` prints a warning and continues. Campaign unit **W2-1**
makes the app refuse to start without them; until that lands, this step is yours to remember.

*Not part of the rehearsal's pass/fail — set to non-defaults throughout.*

### 4 · Create the Authority identity — **once, interactively** ⬜

```bat
cin-portal-init-admin
```

(or, without the install: `python -c "from portal.cli import init_admin; init_admin()"`)

It asks for a user id, a display name, and a PIN (twice, not echoed). Minimum 4 characters.

*Rehearsed ✅ — the real `init_admin()` code path was driven through a pty. Result verified at the
store, not from the console: `portal/data/identity.json` created with permissions `-rw-------`
(owner-only), `identity.has_any_identity()` → `True`, and a `security_events.jsonl` audit line
written. Re-running it exits 1 with "An identity already exists. init-admin only runs once."*

### 5 · Start the portal ⬜

```bat
python portal\app.py
```

or `run_portal.bat`, which does the same thing on port 8080.

It prints a storage map — take a screenshot of it; it is the record of where your data actually
lives. Then open `http://127.0.0.1:8080`.

*Rehearsed ✅ — starts clean, prints the storage map, `Debug mode: off`. An unauthenticated
`GET /dispatch` returns **302 → /login**: the gate fails closed, as designed.*

### 6 · Log in ⬜ and create one load ⬜

Log in with the user id and PIN from step 4, go to Dispatch, and create a load. Anything real
enough to recognise — customer, pickup, delivery, rate.

*Rehearsed ✅ — login returns 302 → `/home`; `GET /dispatch` then returns 200; a load created via
the API came back as `LOAD-20260823-4941E243`, status `created`, `created_at 2026-08-23T15:03:43Z`.*

### 7 · Stop the app ⬜

`Ctrl+C` in the terminal. **Confirm it is actually stopped** before step 8 — reload
`http://127.0.0.1:8080` and check the browser cannot connect.

*This step earned its own warning: in the rehearsal the first "restart" killed a wrapper process,
not the server. The second launch failed with "Address already in use" and the original process
answered the follow-up request — which would have produced a **false pass**. It was caught, the real
process was stopped, and the test was redone. Verify the stop.*

### 8 · Restart and find the load again ⬜ — **this is the proof**

```bat
python portal\app.py
```

Log in again, open Dispatch, and confirm your load is there with the same details.

*Rehearsed ✅ — genuinely new process (PID changed, `* Running on …` printed fresh), new login, and
`GET /api/dispatch/loads/LOAD-20260823-4941E243` returned the load intact with its **original**
`created_at`. The SQLite file was 393,216 bytes on disk between the two runs.*

---

## What Mike sends back

The proof is the transcript, not a summary. Please capture:

1. The output of step 1 (clone) and step 2 (pip).
2. The exact error if `pip install -e .` is tried, or a note that Path A was used.
3. The storage-map screenshot from step 5 — **especially the `Database` line.** That line is the
   answer to "where does my business live."
4. The load id from step 6.
5. The same load, on screen, after step 8.
6. Anything that did not behave as written above.

Item 3 matters more than it looks. If you set the `D:` root variables, the map should show the
database under `D:\Dispatch Operations\Current Workspace\PortalData`. If you did not, it will sit
under `portal\data\` inside the clone — which means **a fresh clone elsewhere starts empty**, and
that is the thing most likely to surprise you later.

## What this proves, and what it does not

**Proves:** the repository is self-contained; the program installs, launches, authenticates
fail-closed, accepts operational data, and keeps it across a process restart on your hardware.

**Does not prove:** that the data is backed up (nothing backs it up — campaign unit **W2-2**), that
it survives a disk failure, or that `bootstrap_d_drive.py` works. That utility has still never run
against a real `D:` volume, from any session, and its four tests copy between Linux temporary
directories. **Do not run it as part of W0-2.**

---

## Rehearsal record

| | |
|---|---|
| Source | `git clone https://github.com/jax1313-outlook/Dispatch.git`, `main` @ `37f4fd0` |
| Platform | Linux container, Python 3.11.15, pip 24.0, setuptools 79.0.1, Flask 3.1.3 |
| Path used | **A** (run from source) |
| Documented path | **FAILED** — `pip install -e .`, flat-layout package discovery |
| Candidate fix | 4 lines, verified in the scratch clone only; **repository untouched** |
| Identity | created and verified at the store; file mode `-rw-------` |
| Login gate | fails closed — 302 → `/login` unauthenticated |
| Load created | `LOAD-20260823-4941E243` |
| Restart | genuine new process, verified after a false pass was caught and discarded |
| Persistence | **PROVEN** — same load, same `created_at`, after restart |
| Repository changes | **none** — `git status --porcelain` → 0, `pyproject.toml` unchanged |
