# DISPATCH GOLD RECOVERY FINDINGS

Status: FINDINGS. Read-only analysis of the L1-COS v1 lineage. No L1-COS build was
modified. No Dispatch runtime behaviour is changed by this document.

---

## Finding 1 — No single v1 build is complete

**CONFIRMED.** This is the governing finding. Every other finding follows from it.

| Build | app.py modified | Lines | DB opps | Scan runs | Artifacts |
|---|---|---|---|---|---|
| v1.0 / v1.0.1 | 2026-07-13 08:10 | 502 | 2 | — | 1 proposal |
| v1.1 | 2026-07-13 09:41 | 251 | 9 | 10 | 2 proposals |
| v1.3 | 2026-07-13 11:38 | 270 | 27 | 5 | 1 proposal |
| v1.3.1 | 2026-07-13 12:27 | 263 | 17 | 2 | none |
| v1.3.3 | 2026-07-13 14:31 | 159 | 0 | 0 | none — **never ran** |
| **v1.3.2 GOLD** | **2026-07-20 08:09** | **577** | 37 | 2 | 4 briefs, 2 workspaces |

Every build except GOLD was made on **13 July 2026, between 08:10 and 14:31** — roughly
six hours of continuous work. GOLD came **seven days later**.

## Finding 2 — GOLD is a rewrite, not an increment

**CONFIRMED.** GOLD is the only transition in the lineage that *removes* capability. It
simultaneously dropped four things and added six.

**Dropped by GOLD** (all four present in v1.0.1 → v1.3.1):

| Lost | Last seen | What it did |
|---|---|---|
| Blocking-condition veto | v1.3.1 `app.py:87` | `BLOCKING → NOT A FIT`, before score bands |
| Decision vocabulary | v1.3.1 | Monitor / Defer / Decline / Pursue / Undecided, validated |
| Externalised scoring | v1.3.1 | `config/scoring_rules.json` |
| Location scoring | (v1.3.3 only) | Tiered territory model |

**Added by GOLD:**

`ensure_column` (schema migration), `interested`, `pursue`, `brief_path`,
`workspace_path`, and the Publisher.

GOLD is the best **workflow** in the lineage and the weakest **judgement**. It knows how
to move an opportunity through human gates and produce artifacts. It has lost the ability
to say *no* on principle.

## Finding 3 — The loss happened in a two-hour window

**CONFIRMED.** The veto, the decision vocabulary and the externalised weights did not
decay gradually. They were present in v1.0.1, v1.1, v1.3 and v1.3.1 — and absent in
v1.3.3 and GOLD.

```
v1.3.1   13 Jul 12:27   veto YES   vocabulary YES   external weights YES
v1.3.3   13 Jul 14:31   veto NO    vocabulary NO    external weights NO
```

Both later builds descend from the same rewrite. **GOLD did not lose these things
independently — it inherited a codebase that had already lost them.**

This corrects an earlier statement in `L1_COS_V1_LINEAGE_ANALYSIS.md` that presented these
as v1.0.1 capabilities. They are the capabilities of the **entire first branch** of the
lineage, and v1.3.1 is their last and cleanest holder.

## Finding 4 — v1.3.1, not v1.0.1, is the governance recovery source

**CONFIRMED.** v1.3.1 holds everything v1.0.1 held for governance, *and* is the build
where the code finally agreed with the constitution.

| | v1.0.1 | v1.3.1 |
|---|---|---|
| Blocking veto | yes | yes |
| Decision vocabulary | yes | yes |
| Externalised weights | yes | yes |
| Fabrication fallback | **present (3 refs)** | **removed** |
| Dashboard reset | no | yes |
| Scheduled scanning | no | yes |
| PSC / classification code | no | yes |
| Lines | 502 | 263 |

v1.0.1 shipped a `sample_opportunities` fallback that its own Master Constitution
forbade. Recovering governance from v1.0.1 means recovering the constitution **and** the
code that violated it.

**Recover the governing documents from v1.0.1 and v1.1. Recover the governance code from
v1.3.1.**

## Finding 5 — Two constitutions exist, and they differ

**CONFIRMED.** Both v1.0.1 and v1.1 carry `L1-COS_MASTER_CONSTITUTION_v1.0.md` and
`PROJECT_MEMORY_RULES.md`. The copies are **not identical** — the MD5 hashes differ for
both files.

Two documents share one version number and disagree. Before either is adopted as Dispatch
doctrine, they must be reconciled and the differences understood. **This is an open item.**

## Finding 6 — Three naming traps

**CONFIRMED.** Folder names in this lineage are not reliable. Trust timestamps and
content.

1. **`v1_3_1_no_fallback`** — the fallback was removed at **v1.1**, two builds earlier.
2. **`v1_3_3_location_email`** — numbered *above* GOLD, but seven days *older*, and it
   **never ran** (0 opportunities, 0 scan runs).
3. **`L1-COS_Prototype_v1_0`** — the inner folder is `v1_0_1`. Same build, stored twice.

## Finding 7 — v1.3.3 is an unrun experiment holding the best territory model

**CONFIRMED.** v1.3.3 has zero rows and zero scan runs. It was written and never
exercised. It is nonetheless the only build with:

- a four-tier territory model in external config
- `location_status` and `location_reason` as stored fields
- `growth_potential` with reasons
- `recommended_action` and `confidence`

Its ideas are the most advanced in the lineage and the **least tested**. Recover the
model; do not assume it works.

## Finding 8 — Credentials are duplicated across every build

**CONFIRMED, security-relevant.** Every build carries its own `.env` and `.env.example`,
each containing a live 40-character SAM.gov API key. v1.1 carries a **third** copy,
`.env.txt`.

That is at least 13 copies of a live credential across the lineage, inside a
OneDrive-synchronised folder, including in `.env.example` files that are conventionally
safe to share.

**This is Mike's decision, not a Dispatch code change.** Recorded here because any
recovery work that copies files from these builds will copy the key with them.

## Finding 9 — The lineage is preserved intact

**CONFIRMED.** No file in any of the seven builds was created, modified, renamed or
deleted by this analysis. The only files written into the lineage are reports.

Evidence, and the limits of it:

- **Source, config and credentials unchanged.** GOLD's `app.py`, `publisher_mvp.py` and
  `.env` are byte-identical to an archive extract.
- **No write-time activity.** GOLD's database contains **zero** records or scan runs dated
  later than 27 July 2026. Newest opportunity `2026-07-27T16:08:54Z`; newest scan run
  `2026-07-27T16:00:24Z`. Nothing in August exists.
- **All reads were read-only.** Databases were opened with SQLite `mode=ro`.

**Method note — filesystem timestamps are not evidence here.** GOLD's `data/l1_cos.db` and
one brief carry a modified time of 30 August 2026, which appears to be a change and is
not. These builds live in a OneDrive-synchronised folder, and reading a cloud-backed file
hydrates it locally, updating its local timestamp without altering content. The database
timestamps above are the reliable evidence, because they record when the application
actually wrote.

**The archive extract is an older snapshot, not a mirror of the current folder.** It holds
three briefs; the live folder holds four. The fourth belongs to an opportunity created
`2026-07-27T16:08:54Z` with `interested=1` — a human marking interest in July, after the
snapshot was taken. The extract is therefore sound evidence for **source files**, which did
not change between snapshots, and is **not** a baseline for data files. Any future drift
check on this lineage should use application-recorded timestamps, not file mtimes and not
this extract.

---

## What Dispatch inherits, by source

| From | Inherit |
|---|---|
| **v1.0.1 + v1.1 (documents)** | Master Constitution, Project Memory Rules, human authority, no-fabrication |
| **v1.3.1 (code)** | Blocking veto, decision vocabulary, externalised scoring, no-fallback discipline, reset, scheduled execution |
| **v1.1 (behaviour)** | Scheduled scan pattern (06:00 / 12:00 / 18:00), repeated operational execution |
| **v1.3 / v1.3.1** | Connector recovery lessons, clean-room testing, reset behaviour |
| **v1.3.3** | Tiered territory, location status + reason, growth potential, recommended action, confidence |
| **GOLD** | One evolving record, atomic gates, Interested → Brief, Pursue → Workspace, Publisher, artifacts, workspaces, archive, duplicate protection, source preservation, run history, recovery paths |
| **Current Dispatch** | Mission Record, System Independence, Driver First, COMI, Librarian, Publisher, Route Risk, JOE, Progressive Detail, human final authority |
