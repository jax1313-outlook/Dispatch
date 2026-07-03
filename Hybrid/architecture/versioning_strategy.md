# Hybrid — Versioning Strategy

Five things are versioned independently: the **system**, **module contracts**,
**config schemas**, the **data model**, and the **intelligence product**.

## 1. System version (SemVer)
`MAJOR.MINOR.PATCH` for Hybrid as a whole.
- **MAJOR** — a breaking change to a published contract (`integration_points.md`
  I1–I8) or removal of a layer.
- **MINOR** — new module/adapter/engine, backward-compatible.
- **PATCH** — fixes, threshold/rule tuning, doc updates.
Tagged in git; recorded in a top-level `CHANGELOG`.

## 2. Contract versions (the load-bearing seams)
Each internal contract in `integration_points.md` carries a version. Changing a
contract's shape is a **MAJOR** system event and requires:
- a deprecation window (old + new accepted), and
- a migration note in the changelog.
Key contracts: `run_intelligence` (I1), `CINRouter.dispatch` (I2),
`eligibility_verdict` (I3), control actions (I4), `vendor_profile` (I5),
`packet` (I6), service clients (I7), `config` (I8).

## 3. Config schema versions
`rules.json` / `settings.json` / route + threshold files get a `schema_version`
field. Loaders accept the current and previous schema; unknown → safe default +
warning. Config edits (adding a rule, a route, a whitelist entry) are **data**,
not version bumps.

## 4. Data-model versions
Schemas in `data_model/` (owned elsewhere) version separately. Archived artifacts
embed the schema version they were written with so old records remain readable.
Never mutate an archived artifact in place — write a new versioned record.

**Schemas are immutable after Step 2; downstream modules may not reshape upstream
data.** All `data_model/` schemas land at Step 2 (front-load stance); any change
after Step 2 is a MAJOR event with a migration path. Consumers validate against the
pinned schema and fail on mismatch rather than silently adapting. See
`landing_points.md` and `build_sequence.md`.

## 5. Intelligence product version
The `intel_version` tag already emitted by `HybridIntelligence`
(e.g. `phase4-wip`) identifies the scoring/rules/routing generation. It advances
when the scoring model, rule set, or routing logic changes materially, so a stored
intelligence record is always interpretable against the logic that produced it.

## Branch & release model
- `main` — releasable; every merge green in `qa/`.
- `feature/*` — one change set; opened as a PR to `main`.
- Release = tag on `main` + changelog entry. (PRs are handled in the GitHub UI.)

## Compatibility policy
- **Additive by default:** new engines/adapters/routes must not change existing
  outputs.
- **Deprecate, don't delete:** contracts are removed only after a MAJOR bump with
  a migration path.
- **Adapters are swappable:** replacing SAM/DocuSign/Outlook/portal is a MINOR
  change if the owning module's contract is unchanged.
- **Eligibility rules are auditable & versioned:** any change to an eligibility
  check is recorded (rule id + version) so past verdicts can be explained.

## What is NOT a version event
Editing keyword lists, thresholds, whitelist entries, folder routes, or sender
reputation data — these are runtime configuration/data, tracked by the audit log,
not by the system version.
