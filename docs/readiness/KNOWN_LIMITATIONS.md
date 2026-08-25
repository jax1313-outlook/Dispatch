# Dispatch — Known Limitations

**Current as of:** 2026-08-25. **This is a living document.** When something on it is fixed,
the entry moves to §6 with a date rather than being deleted — an entry that quietly vanishes
teaches nobody anything.

Companion documents: `docs/readiness/OPERATIONAL_PROOF.md` (what is proven) and
`docs/architecture/DISPATCH_ARCHITECTURE.md` §7 (where code conflicts with doctrine).

---

## 1. The one that governs all the others

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
| 2026-08-25 | **The portal could not start if the Route Risk plug-in was absent.** `portal/routes/driver_portal.py` imported `dispatch.route_risk` at module scope, which imported the standalone `route_risk` engine at module scope — so an uninstalled *optional risk advisor* took down blueprint registration, and with it every driver surface, every load and every milestone. A direct violation of the Plug-In Separation Doctrine and of "degradation is permitted, incapacity is not". Reads now degrade to `ABSENT`; writes refuse loudly rather than silently discarding a recorded hazard. Guarded by `tests/test_repository_doctrine.py` |
| 2026-08-25 | **The portal called itself "L2-COS Operations Portal" in its own chrome.** The program is Dispatch; the sidebar heading, the login page, ~30 page titles, the startup banner and two package docstrings said otherwise. Renamed across `portal/`, with three test assertions updated and a drift test added so it cannot come back. Recorded as gap 10 in `docs/readiness/COMPLETION_REPORT.md` §10, which is left as written — it is that mission's record, not a live status |
| 2026-08-25 | **`CLAUDE.md` described only the CIN-Lite half of the repository**, so a cold-start builder concluded Dispatch was a contract-archiving tool. Rewritten as a full cold-start brief; the conflict is recorded in `CLAUDE.md` §1 rather than quietly overwritten |
| 2026-08-25 | **The README's CI badge pointed at `jax1313-outlook/cin-hybrid`**, a repository this is not. Corrected to `jax1313-outlook/Dispatch` |
| 2026-08-24 | `driver_step_milestone` swallowed refused transitions in `except Exception: pass` — a driver tapped a milestone, nothing was recorded, and the screen said it worked. The classic 70 MPH Test failure |
| 2026-08-24 | `check_evidence_path` crashed the readiness check when the upload directory could not be created, because `_get_upload_dir()` raises `OSError` |
| 2026-08-24 | `.gitattributes` ordering silently disabled the CRLF rule for the Windows wrappers — last matching pattern wins, and the catch-all was last |

---

## 7. The exact next operational blocker

> **Nobody has ever double-clicked `dispatch.bat` on the Windows laptop.**

That is the blocker. Not a missing feature — a missing observation.

Item 1 of the fifteen. Until it happens, every other readiness question downstream of it is
unanswerable: whether `py.exe` resolves to the interpreter that has Flask, whether the
`setx` roots reached the window, whether SmartScreen interferes with a detached process,
whether the console renders the menu. Each is cheap to answer and impossible to guess, and
each currently blocks the twenty-step load proof behind it.

**The one action that unblocks the most:** open the Dispatch folder on the laptop,
double-click `dispatch.bat`, and record what appears — including if nothing does.
`DISPATCH_FIRST_START_GUIDE.md` says what is expected;
`docs/readiness/LAUNCHER_PROOF_TEMPLATE.md` is where the answer goes.

It cannot be done from a build container. It has to be done there.
