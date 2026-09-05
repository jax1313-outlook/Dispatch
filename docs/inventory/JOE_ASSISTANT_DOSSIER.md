# JOE_ASSISTANT_DOSSIER.md

Repository inventory dossier. Authority: Mike Zachary.
Compiled 2026-09-05 from the repository at commit `4a9a6a3` (`origin/main`).

Recovery operation only. This dossier records what exists. It makes no design,
archive, cleanup, or refactor recommendation.

---

## SECTION 1 — REPOSITORY FACTS

| Fact | Value | How established |
|---|---|---|
| Repository name | `Joe-Assistant` | `git remote get-url origin` |
| Repository URL | https://github.com/jax1313-outlook/Joe-Assistant | same |
| Visibility | Public | `list_repos` |
| Creation date (first commit) | 2026-08-08 14:34:02 -0400 | `git log --reverse` |
| Last commit date | 2026-08-28 15:25:07 -0400 (`4a9a6a3`, "Create Screens") | `git log -1` |
| Last push | 2026-08-28T19:25:08Z | `list_repos` |
| Branch count | **1** (`main` only) | `git ls-remote --heads` |
| Commit count | **36** | `git rev-list --count HEAD` |
| Default branch | `main` | `git ls-remote` |
| Contributors | `jax1313-outlook` (36) — sole contributor | `git shortlog -sne` |
| README status | Present — **two**: `README.md` and `READ ME.md` (separate files) | `git ls-files` |
| Tracked files | 342 | `git ls-files \| wc -l` |
| Python | 135 files, **34,000 lines** | `git ls-files '*.py'` + `wc -l` |
| Markdown | 130 files, 19,290 lines | same |
| Windows `.cmd` launchers | 30 | `git ls-files '*.cmd'` |

**Second-largest repository in the ecosystem** by Python volume, after Dispatch.

---

## SECTION 2 — PURPOSE

**Evidence sources:** `Assistant_Plugin/docs/JOE_CONSTITUTION_v1.md`,
`JOE_ARCHITECTURE_v1.md`, `JOE_CONTEXT_v1.md`, `ASSISTANT_PLUGIN_CONSTITUTION_v1/`,
`JOE_CAPABILITY_TRUTH_MATRIX.md`, and the code.

Joe-Assistant is the repository of **JOE — the Level 1 Transport Assistant Plug-In**: a
local, Windows-resident, driver-facing assistant that reasons, remembers, reads a company
document library, reads Outlook read-only, researches, and speaks.

Dispatch's own `CLAUDE.md` §5.4 defines the relationship from the other side:

> Route Risk, Mission Visibility, SAM, and Assistant are **plug-ins**. Dispatch must start
> and run its core operation without any of them.
> Do not embed Assistant code into Dispatch… **No direct Dispatch write authority may be
> granted to Assistant.**

That boundary is honoured in code: `Assistant_Plugin/adapters/dispatch_port.py` is a port,
and the capability matrix reports `Dispatch NOT CONNECTED`.

The repository holds **three generations of the same program**, all still present:

1. `ASST/1`–`ASST/6` — six deliberately standalone increments, each with its own
   Constitution, Architecture, Context, Source, Tests, Operator Guide, Build Report and
   Test Report.
2. `Assistant_Plugin/` — the integrated JOE application built from those increments, with
   real adapters to live services.
3. `Build/sandbox_engine/` — a separate sandbox/retention engine with its own governance set.

---

## SECTION 3 — DIRECTORY MAP

```
Joe-Assistant/
├── Assistant_Plugin/            THE INTEGRATED JOE APPLICATION (161 files)
│   ├── joe_main.py              Entry point
│   ├── START_JOE.cmd            Double-click launch
│   ├── app/                     Service core (13 files)
│   │   ├── service.py           1,470 LOC — the assistant service
│   │   ├── reasoning_capabilities.py  514 LOC — six reasoning modes
│   │   ├── router.py, bootstrap.py, config.py, alerts.py, followup.py,
│   │   ├── driver_voice.py      Continuous Driver Mode loop
│   │   ├── load_card.py, logbook.py, when.py, hearing_proof.py
│   ├── adapters/                LIVE EXTERNAL INTEGRATIONS (13 files)
│   │   ├── outlook_com.py       706 LOC — Outlook via COM, read-only
│   │   ├── mailbox_registry.py  533 LOC — 3-view mailbox discovery
│   │   ├── m365_copilot.py      492 LOC — M365 Copilot reasoning
│   │   ├── m365_copilot_auth.py 347 LOC — MSAL + DPAPI token storage
│   │   ├── reasoning_provider.py 534 LOC
│   │   ├── claude_provider.py, research_provider.py
│   │   ├── voice_sapi.py        Windows SAPI speech output
│   │   ├── whisper_listen.py    Speech input
│   │   ├── microphones.py, library_fs.py
│   │   └── dispatch_port.py     The Dispatch boundary (not connected)
│   ├── ui/                      Assistant window (window.py 745 LOC) + settings panel
│   ├── memory/                  assistant_memory: retention, store, clock, record, CLI
│   ├── library/                 assistant_library: search, document, library, CLI
│   ├── outlook/                 assistant_outlook: awareness, provider, models, CLI
│   ├── research/                assistant_research: analysis, authority, sources, record
│   ├── voice/                   assistant_voice: session, driver_mode, engines, utterance
│   ├── contracts/               447 LOC — ReasoningMode, Provenance, shared contracts
│   ├── governance/              Governance gate
│   ├── proof/                   9 proof scripts (1,663 LOC runner) + 3 PNG screenshots
│   ├── launchers/               14 .cmd/.ps1 operator launchers
│   ├── tests/test_joe.py        3,119 LOC — the integrated suite
│   ├── docs/                    33 documents
│   ├── configuration/           joe.config.json + template
│   └── Deployment/              PACKAGE_JOE.cmd, verify_package.ps1, VERSION.txt
├── ASST/1..6                    SIX STANDALONE INCREMENTS (124 files)
│   1 = UI · 2 = Memory · 3 = Library · 4 = Outlook · 5 = Research · 6 = Voice
│   each: Architecture/ Constitution/ Context/ Source/ Tests/ Operator_Guide/
│         README.md BUILD_REPORT_v1.md TEST_REPORT_v1.md
├── Build/sandbox_engine/        Standalone sandbox engine (engine 446, cli 417 LOC)
├── Architecture/ Constitution/ Context/   Sandbox-engine governance set
├── Testing/                     proof_local.py (639), test_sandbox_engine.py (535)
├── Sandbox/ Artifacts/          LIVE RUNTIME DATA — sandbox records + artifact requests
├── ASSISTANT_PLUGIN_CONSTITUTION_v1/   7-document constitution package
├── Governing_Inputs/            LEVEL1_ASSISTANT_BUILD_PACKAGE_v1.docx + agent config
├── Play-Pen/                    jules_session_…zip
└── (root)                       Dispatch governance mirror: 02–08 matrices,
                                 DISPATCH_CONSTITUTION_v2, DISPATCH_CONTEXT_MASTER_v2,
                                 JOE Display Architecture v1.0, Ergonomic Hybrid JOE Display
```

**Folder purposes**

- `ASST/N` — each increment is a *complete, independently runnable* component with its own
  law and its own tests. Their READMEs state their limits explicitly (e.g. ASST/4:
  "Not connected to a real mailbox… It reads sample fixture files in `Data\`").
- `Assistant_Plugin/` — where those six were integrated and connected to real services.
- `Sandbox/active`, `Sandbox/deleted`, `Artifacts/requests` — **committed runtime records**
  (`SBX-…json`, `AR-…json/md`), not fixtures.

---

## SECTION 4 — CODE INVENTORY

### Applications
| Application | Entry point | Evidence |
|---|---|---|
| JOE Assistant (integrated) | `Assistant_Plugin/joe_main.py`, `START_JOE.cmd` | Truth matrix: "window visible in 4.6 s, `pythonw`, 0 console windows" — **PROVEN** |
| Sandbox Engine | `Build/sandbox.cmd`, `Build/sandbox_engine/cli.py` | `Architecture/SANDBOX_ENGINE_ARCHITECTURE_v1.md` |
| ASST/1 Assistant UI | `ASST/1/Source/run_ui.cmd` | `ASST/1/README.md` |
| ASST/2 Memory | `ASST/2/Source/memory.cmd` | `ASST/2/README.md` |
| ASST/3 Library | `ASST/3/Source/library.cmd` | `ASST/3/README.md` |
| ASST/4 Outlook | `ASST/4/Source/outlook.cmd` | `ASST/4/README.md` |
| ASST/5 Research | `ASST/5/Source/research.cmd` | `ASST/5/README.md` |
| ASST/6 Voice | `ASST/6/Source/voice.cmd` | `ASST/6/README.md` |

### Services / modules — `Assistant_Plugin/app/` (13)
`service.py` (1,470), `reasoning_capabilities.py` (514), `router.py`, `bootstrap.py`,
`config.py`, `alerts.py`, `followup.py`, `driver_voice.py`, `load_card.py`, `logbook.py`,
`when.py`, `hearing_proof.py`.

### Adapters / Connectors — `Assistant_Plugin/adapters/` (13)
`outlook_com.py` (706, live COM), `mailbox_registry.py` (533),
`reasoning_provider.py` (534), `m365_copilot.py` (492), `m365_copilot_auth.py` (347, MSAL
public client + DPAPI), `claude_provider.py`, `research_provider.py`, `voice_sapi.py`,
`whisper_listen.py`, `microphones.py`, `library_fs.py`, `dispatch_port.py`.

### Contracts
`Assistant_Plugin/contracts/__init__.py` (447 LOC) — `ReasoningMode`, `Provenance` and the
shared object contracts. `Assistant_Plugin/governance/__init__.py` — the governance gate.

### Modules (packaged sub-libraries, each with `__main__` and CLI)
`assistant_memory` (store, retention, record, clock, cli),
`assistant_library` (library, search, document, cli),
`assistant_outlook` (provider, awareness, models, cli),
`assistant_research` (analysis, authority, sources, record, cli),
`assistant_voice` (session, driver_mode, engines, utterance, cli),
`assistant_ui` (window, view_model, conversation, actions),
`sandbox_engine` (engine, cli, store, records, intents, clock).

### CLI tools
`python -m assistant_memory|assistant_library|assistant_outlook|assistant_research|assistant_voice`,
`Build/sandbox_engine/cli.py`, plus 30 Windows `.cmd` launchers:
`START_JOE`, `RESTART_JOE`, `STOP_JOE`, `JOE_STATUS`, `JOE_ACCOUNTS`, `MIC_LIST`, `MIC_TEST`,
`OPEN_DATA`, `OPEN_LOGS`, `PROVE_COPILOT`, `PROVE_VOICE_INPUT`, `RUN_PROOF`, `RUN_TESTS`,
`INSTALL_JOE_SHORTCUTS`, `PACKAGE_JOE`, per-increment `run_ui`/`memory`/`library`/`outlook`/
`research`/`voice` commands.

### Background services
`app/driver_voice.py` (`DriverVoiceLoop` — continuous Driver Mode),
`app/followup.py`, `app/alerts.py`.

### Database models / storage
No SQL database. `assistant_memory/store.py` is a file-backed record store with
Level 1/2/3 retention and 3-hour expiry; `sandbox_engine/store.py` and `records.py` back the
`Sandbox/*.json` records. `assistant_library` indexes a filesystem corpus.

### Proof harness — `Assistant_Plugin/proof/` (9 scripts)
`run_proof.py` (1,663 LOC), `prove_copilot.py` (406), `audit_controls.py` (397),
`prove_microphone.py` (363), `prove_voice_input.py`, `prove_reasoning.py`,
`prove_research.py`, `prove_email_layer.py`, `run_live_reasoning_proof.py`,
plus screenshots `window_launched.png`, `window_running.png`, `window_v2.png`.

### Tests
8 test files, **729 `def test_` functions**. Largest: `Assistant_Plugin/tests/test_joe.py`
(3,119 LOC). Per-increment suites: `ASST/{1..6}/Tests/`. Plus `Testing/test_sandbox_engine.py`
(535) and `Testing/proof_local.py` (639). *Not run during this inventory.*

### Scripts / utilities
`Deployment/PACKAGE_JOE.cmd`, `Deployment/verify_package.ps1`,
`launchers/install_shortcuts.ps1`.

---

## SECTION 5 — FUNCTIONAL CAPABILITIES

Status below is taken **verbatim from `Assistant_Plugin/docs/JOE_CAPABILITY_TRUTH_MATRIX.md`**,
which records: "Measured: 2026-08-26, by running the program… Every row was measured, not read
off a label." Its evidence classes are PROVEN / UNPROVEN / PARTIAL / BLOCKED-HUMAN /
BLOCKED-EXTERNAL / NOT IMPLEMENTED.

| Capability | Exists | Evidence | Primary files | Status |
|---|---|---|---|---|
| Launch by double-click | Yes | window visible in 4.6 s, `pythonw`, 0 console windows | `START_JOE.cmd`, `joe_main.py` | **PROVEN** |
| Written interaction record | Yes | every request produces a record | `app/service.py::ask` | **PROVEN** |
| Retention Levels 1/2/3, Print Ready, Delete | Yes | proof steps 4–8 | `memory/assistant_memory/retention.py` | **PROVEN** |
| 3-hour expiry, restart persistence | Yes | proof 13 | `assistant_memory` `MemoryStore` | **PROVEN** |
| Company Library retrieval | Yes | 34 documents indexed, real documents returned | `adapters/library_fs.py`, `assistant_library` | **PROVEN** |
| Outlook read (read-only) | Yes | live COM read; **21 write calls scanned and refused** | `adapters/outlook_com.py` | **PROVEN** |
| Calendar ordering / filtering | Yes | chronological, item by item | `_PREPARE["calendar"]` | **PROVEN** |
| Mail order / contact order | Yes | newest-first; alphabetical | `_sort_contacts` | **PROVEN** |
| present / absent / **unknown** status | Yes | a timeout is unknown, never absent | `account_status()` | **PROVEN** |
| Mailbox registry, 3-view discovery | Yes | Accounts + Stores + Folders reconciled | `adapters/mailbox_registry.py` | **PROVEN** |
| Per-mailbox failure isolation | Yes | one mailbox failing does not disable another | `MailboxRegistry.source_for` | **PROVEN** |
| Copilot authentication | Yes | MSAL public client, DPAPI blob verified byte-level | `adapters/m365_copilot_auth.py` | **PROVEN** |
| Copilot reasoning (live) | Yes | live prompt, live answer, signed in as Ops@ | `adapters/m365_copilot.py` | **PROVEN** — matrix notes the API is `/beta`, unsupported by Microsoft for production |
| Six reasoning modes | Yes | enforced in the governance gate; a breach is refused | `contracts::ReasoningMode` | **PROVEN** |
| Web-grounded research | Yes | 11 real attributions with URLs | `adapters/research_provider.py` | **PROVEN** — matrix states it does not replace DOT or 511 |
| Per-entry provenance | Yes | Copilot and Library entries stay separate | `contracts::Provenance` | **PROVEN** |
| Voice **output** | Yes | spoke aloud | `adapters/voice_sapi.py::speak` | **PROVEN** |
| Calendar answers to Mike | Partly | no approved mailbox holds a calendar; JOE refuses and says why | — | **PARTIAL** |
| Contact answers to Mike | Partly | same | — | **PARTIAL** |
| Multi-turn conversation | Partly | context carries; substantive answers non-deterministic — 2/2, 1/2, 1/2, 0/2 across runs | `prove_reasoning.py` | **PARTIAL** |
| Voice **input** | Code exists | engine binds; microphone enumerated; **no person has spoken to it** | `DriverVoiceLoop`, `whisper_listen.py` | **BLOCKED-HUMAN** |
| Bluetooth headset operation | Code exists | LEVN headset known to Windows; not connected at last check | `adapters/microphones.py` | **BLOCKED-HUMAN** |
| Microphone suppression while speaking | Code exists | 18 tests pass | `DriverVoiceLoop.say` | **UNPROVEN** |
| Continuous Driver Mode | Code exists | loop, commands, state machine tested headless | `app/driver_voice.py` | **UNPROVEN** |
| Audio-activity detection | **No** | JOE cannot distinguish a dead microphone from a silent room | — | **NOT IMPLEMENTED** |
| Dispatch connection | **No** | status strip reads `Dispatch NOT CONNECTED` | `adapters/dispatch_port.py` | Port exists; not connected |
| Sandbox Engine (retention/intents) | Yes | `Testing/SANDBOX_ENGINE_TEST_REPORT_v1.md`; live records in `Sandbox/active` | `Build/sandbox_engine/` | IMPLEMENTED |
| Load Card | Yes | `app/load_card.py` | that file | IMPLEMENTED |
| Logbook | Yes | `app/logbook.py` | that file | IMPLEMENTED |
| Alerts / follow-up | Yes | `app/alerts.py`, `app/followup.py` | those files | IMPLEMENTED |
| Claude provider | Yes | `adapters/claude_provider.py` | that file | IMPLEMENTED |

**Status strip as recorded in the matrix:**
`Reasoning LIVE | Library LIVE | Outlook READY | Research LIVE | Voice out LIVE | Voice in NOT CONNECTED | Dispatch NOT CONNECTED`

---

## SECTION 6 — DOCUMENT INVENTORY

130 markdown documents. By location: `Assistant_Plugin/` 50, `ASST/` 49,
`ASSISTANT_PLUGIN_CONSTITUTION_v1/` 7, root 14, `Artifacts/` 3, `Testing/` 2,
`Architecture/`, `Constitution/`, `Context/`, `Build/` 1 each.

**Constitutions**
`ASSISTANT_PLUGIN_CONSTITUTION_v1/` — `00_README`, `01_CONTEXT_v1`, `02_CONSTITUTION_v1`,
`03_ARCHITECTURE_v1`, `04_GOVERNANCE_v1`, `05_REPOSITORY_RECOMMENDATION_v1`,
`AMENDMENT_1_TRANSMISSION_PROPOSED`.
`Assistant_Plugin/docs/JOE_CONSTITUTION_v1.md`.
`Constitution/SANDBOX_ENGINE_BOUNDARIES_v1.md`.
Per-increment: `ASST/{1..6}/Constitution/`.
Mirrored from Dispatch: `DISPATCH_CONSTITUTION_v2.md`, `DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`.

**Architecture documents**
`Assistant_Plugin/docs/JOE_ARCHITECTURE_v1.md`,
`Architecture/SANDBOX_ENGINE_ARCHITECTURE_v1.md`,
`# JOE Display Architecture v1.0.md`, `Ergonomic Hybrid JOE Display.md`,
`Assistant_Plugin/docs/DISPATCH_AGENT_INTEGRATION_MAP.md`,
per-increment `ASST/{1..6}/Architecture/`.

**Governance documents**
Root Dispatch mirror: `02_DISPATCH_AGENT_GOVERNANCE_LAW.md`,
`03_DISPATCH_AGENT_RELATIONSHIP_MATRIX.md`, `04_DISPATCH_CONTEXT_MASTER.md`,
`05_DISPATCH_AUTHORITY_MATRIX.md`, `06_DISPATCH_LEARNING_MATRIX.md`,
`07_DISPATCH_CONFLICT_MATRIX.md`, `08_DISPATCH_BUILD_VALIDATION_STANDARD.md`,
`DISPATCH_CONTEXT_MASTER_v2.md`.
Plus `Assistant_Plugin/docs/JOE_GOVERNANCE_APPLICATION_REPORT.md`.

**Specifications / contracts**
`Assistant_Plugin/docs/JOE_INTERFACE_CONTRACT_v1.md`,
`JOE_FUTURE_DISPATCH_INTERFACE_CONTRACTS.md`,
`EMAIL_CONNECTION_LAYER_v1_REQUIREMENT.md`.

**Roadmaps / build plans**
`Assistant_Plugin/docs/DISPATCH_COPILOT_AGENT_BUILD_PLAN.md`,
`JOE_STEP_1_INTEGRATION_READINESS.md`,
`DISPATCH_OPERATIONAL_READINESS_MISSION.md`,
`REPOSITORY_OWNERSHIP_AND_MIGRATION_PLAN.md`.

**Evidence / proof / audit reports**
`JOE_CAPABILITY_TRUTH_MATRIX.md` · `JOE_CURRENT_STATE_EVIDENCE.md` ·
`JOE_LIVE_REASONING_PROOF_v1.md` · `JOE_LOCAL_PROOF_REPORT_v1.md` · `PROOF_AUDIT_v1.md` ·
`JOE_TEST_REPORT_v1.md` · `JOE_BUILD_REPORT_v1.md` / `v2` · `VOICE_LIVE_RESEARCH_FINDINGS.md` ·
`REPOSITORY_CERTIFICATION_REPORT.md` · `REPOSITORY_INVENTORY_REPORT.md` ·
`ARCHITECTURE_CONFLICT_REGISTER.md` · `JOE_CODE_SALVAGE_MATRIX.md` ·
`LEGACY_CONSOLIDATION_REPORT.md` · `DISPATCH_DISCOVERY_VALUE_REPORT.md` ·
`BACKUP_INVENTORY_REPORT.md` / `BACKUP_ACTION_REPORT.md` ·
`Testing/LOCAL_PROOF_REPORT_v1.md` · `Testing/SANDBOX_ENGINE_TEST_REPORT_v1.md` ·
12 per-increment `BUILD_REPORT_v1.md` / `TEST_REPORT_v1.md`.

**Operational documents**
`JOE_OPERATOR_GUIDE_v1.md`, `JOE_DEPLOYMENT_GUIDE_v1.md`, `COPILOT_ACTIVATION_STEPS.md`,
`JOE_KNOWN_LIMITATIONS_v1.md`, `Artifacts/SANDBOX_ENGINE_OPERATOR_GUIDE_v1.md`,
6 per-increment `Operator_Guide/`.

**Handoffs**
`Assistant_Plugin/docs/JOE_REVIEW_HANDOFF_v1.md`.

**Prompts / agent configuration**
`Governing_Inputs/LEVEL1_ASSISTANT_AGENT_CONFIG_v1.txt`,
`Governing_Inputs/LEVEL1_ASSISTANT_BUILD_PACKAGE_v1.docx`.

---

## SECTION 7 — UNIQUE ASSETS

**330 of 342 files (96.5%) have content found in no other repository.** Only 12 files are
byte-identical to a file elsewhere (the mirrored Dispatch governance set at the root).

1. **The only assistant/JOE program in the ecosystem.** 34,000 lines of Python. No other
   repository contains any JOE code. Dispatch's `CLAUDE.md` §5.4 explicitly forbids embedding
   it there.
2. **The only code in the ecosystem operationally proven against live external services.**
   `JOE_CAPABILITY_TRUTH_MATRIX.md` records measured-by-running proofs of: live Outlook COM
   reads, live M365 Copilot reasoning signed in as Ops@, MSAL+DPAPI token storage verified
   byte-level, audible SAPI speech, and web research returning 11 real URL attributions.
   Dispatch, by contrast, records in its own `CLAUDE.md` §8 that **nothing** in it has been
   run on Mike's machine.
3. **Live Microsoft 365 integration code** — `m365_copilot.py`, `m365_copilot_auth.py`,
   `outlook_com.py`, `mailbox_registry.py`. Roughly 2,078 LOC of real Microsoft integration
   existing nowhere else. Dispatch has an `outlook_connector.py` interface with no provider.
4. **Voice stack** — `voice_sapi.py`, `whisper_listen.py`, `microphones.py`,
   `assistant_voice/` (session, driver_mode, engines, utterance), `DriverVoiceLoop`.
   Unique to this repository.
5. **The six ASST increments** — 124 files. Each is a self-contained component with its own
   constitution, architecture, context, source, tests, operator guide and build/test reports.
   This is the ecosystem's clearest worked example of `CLAUDE.md` §5.7 THE MIKE RULE
   (standalone subsystems preferred over shared abstractions).
6. **The proof harness** — 9 `prove_*.py` scripts plus a 1,663-line runner and three
   screenshots of a running window. A working, executed evidence-collection apparatus.
7. **The Sandbox Engine** — `Build/sandbox_engine/` with its own Architecture, Constitution
   and Context documents, plus **live committed runtime records** in `Sandbox/active`,
   `Sandbox/deleted`, `Testing/_proof_expiry/` and `Artifacts/requests/`.
8. **JOE display / ergonomics design** — `# JOE Display Architecture v1.0.md`,
   `Ergonomic Hybrid JOE Display.md`.
9. **The 3,119-line integrated test file** `Assistant_Plugin/tests/test_joe.py` and 729 test
   functions overall — second-largest suite in the ecosystem.
10. **`Governing_Inputs/LEVEL1_ASSISTANT_BUILD_PACKAGE_v1.docx`** and
    `LEVEL1_ASSISTANT_AGENT_CONFIG_v1.txt` — source inputs found nowhere else.
11. **`Play-Pen/jules_session_12863749728267333928.zip`** — an archived Jules session,
    matching Dispatch branch `jules-driver-transformation-missions-1-4-12863749728267333928`.
12. **Windows packaging** — `Deployment/PACKAGE_JOE.cmd`, `verify_package.ps1`,
    `install_shortcuts.ps1`, and 30 operator `.cmd` launchers.

---

## SECTION 8 — CROSS-REPOSITORY REFERENCES

| Referenced entity | Occurrences | Representative files |
|---|---|---|
| Dispatch | 857 | `adapters/dispatch_port.py`, `docs/DISPATCH_AGENT_INTEGRATION_MAP.md`, `JOE_FUTURE_DISPATCH_INTERFACE_CONTRACTS.md`, `DISPATCH_OPERATIONAL_READINESS_MISSION.md`, root governance mirror |
| Library | 974 | `adapters/library_fs.py`, `library/assistant_library/`, `ASST/3` |
| Joe | 752 | throughout |
| Publisher | 91 | governance matrices at root |
| Route Risk | 36 | `docs/DISPATCH_AGENT_INTEGRATION_MAP.md` |
| Mission Visibility | 24 | `ASST/3` corpus references, integration map |
| Manager | 117 | `03_DISPATCH_AGENT_RELATIONSHIP_MATRIX.md`, `05_DISPATCH_AUTHORITY_MATRIX.md` |
| COMI | 10 | integration map |
| Jules | 7 | `Play-Pen/jules_session_….zip` |
| SAM | 2 | governance matrices |

**Named dependency direction.** `dispatch_port.py` is JOE's outbound port to Dispatch;
the truth matrix records `Dispatch NOT CONNECTED`. Dispatch's `CLAUDE.md` §5.4 forbids
granting Assistant any direct Dispatch write authority. Both sides of the boundary state it.

**Shared governance documents** (byte-identical to copies in other repos):
`DISPATCH_CONSTITUTION_v2.md`, `DISPATCH_CONTEXT_MASTER_v2.md`,
`DISPATCH_AGENT_GOVERNANCE_LAW_v1.md`, and the `02_`–`08_` numbered matrices — the same set
also present in `L2-intelligence-agent.` and `Publisher`.

---

## SECTION 9 — BUILT VS PLANNED

### Built In Code (and proven against a live service)
Double-click launch · written interaction record · retention Levels 1/2/3 with Print Ready
and Delete · 3-hour expiry surviving restart · company Library retrieval over 34 indexed
documents · Outlook read-only via COM with 21 write calls refused · calendar/mail/contact
ordering · present/absent/**unknown** status semantics · mailbox registry with 3-view
discovery · per-mailbox failure isolation · Copilot MSAL+DPAPI authentication · live Copilot
reasoning · six enforced reasoning modes · web-grounded research with real attributions ·
per-entry provenance · audible voice output.

### Built In Code (not proven against a live service)
Continuous Driver Mode · microphone suppression while speaking · sandbox engine · load card ·
logbook · alerts and follow-up · Claude provider · the six ASST increments (each proven
against its own fixtures only) · packaging and shortcut installation.

### Partially Built
- **Calendar and contact answers** — the code works; no approved mailbox holds a calendar,
  so JOE refuses and says why. `PARTIAL`.
- **Multi-turn conversation** — context carries, but substantive answers are non-deterministic
  (matrix: 2/2, 1/2, 1/2, 0/2 across runs). `PARTIAL`.
- **Voice input** — engine binds and microphones enumerate; **no person has ever spoken to it**.
  `BLOCKED-HUMAN`.
- **Bluetooth headset** — the LEVN headset is known to Windows, not connected. `BLOCKED-HUMAN`.

### Documented Only
`JOE_FUTURE_DISPATCH_INTERFACE_CONTRACTS.md` (future Dispatch contracts),
`EMAIL_CONNECTION_LAYER_v1_REQUIREMENT.md` (a requirement, not an implementation),
`ASSISTANT_PLUGIN_CONSTITUTION_v1/AMENDMENT_1_TRANSMISSION_PROPOSED.md` (proposed),
`REPOSITORY_OWNERSHIP_AND_MIGRATION_PLAN.md`, `DISPATCH_COPILOT_AGENT_BUILD_PLAN.md`.

### Referenced But Missing
- **Audio-activity detection** — matrix: `NOT IMPLEMENTED`. JOE cannot distinguish a dead
  microphone from a silent room.
- **The Dispatch connection itself** — `dispatch_port.py` exists; the service is not connected.
- **Library coverage gaps** — matrix notes the Library "holds no detention or load-refusal
  procedure".

### Unknown
- Whether the 729 test functions currently pass — **the suite was not run** during this inventory.
- Whether the proof results in the truth matrix (measured 2026-08-26) still hold; the last
  commit is 2026-08-28.
- Whether `Assistant_Plugin/configuration/joe.config.json` (committed) holds current settings.

---

## SECTION 10 — EXECUTIVE SUMMARY

**What is this repository?**

Joe-Assistant holds **JOE**, the Level 1 Transport Assistant plug-in: a local Windows
assistant that reasons, remembers, reads a company document library, reads Outlook, researches,
and speaks. It is the second-largest repository in the ecosystem — 342 files, 34,000 lines of
Python, 130 documents, 729 test functions — and it is a single-branch, single-contributor
repository with 36 commits. It contains three generations of the same program side by side:
six standalone ASST increments (UI, Memory, Library, Outlook, Research, Voice), the integrated
`Assistant_Plugin/` built from them, and a separate Sandbox Engine.

**What is actually implemented?**

More than any other repository has *proven*. `JOE_CAPABILITY_TRUTH_MATRIX.md` — measured on
2026-08-26 by running the program, not by reading labels — records as **PROVEN**: double-click
launch in 4.6 seconds, live Outlook reads over COM with 21 write calls scanned and refused,
live Microsoft 365 Copilot reasoning signed in as a real account, MSAL+DPAPI token storage
verified byte-level, a 34-document company library returning real documents, six enforced
reasoning modes, per-entry provenance, web research with 11 real URL attributions, and audible
speech output. It records equally plainly what is not: **voice input has never heard a person**;
audio-activity detection is `NOT IMPLEMENTED`; calendar and contact answers are `PARTIAL`
because no approved mailbox holds a calendar; multi-turn reasoning is non-deterministic; and
**Dispatch is NOT CONNECTED**.

**What unique value does it contain?**

96.5% of its files exist nowhere else. Three things stand out. First, it is the **only
repository in the ecosystem with capabilities operationally proven against live external
services** — while Dispatch's own `CLAUDE.md` states that nothing in Dispatch has ever been run
on Mike's machine. Second, it holds the ecosystem's **only Microsoft 365 / Outlook / voice
integration code** (~2,078 lines of real Microsoft integration plus the full voice stack) —
Dispatch has the interface, JOE has the working implementation. Third, the six ASST increments
are the ecosystem's clearest worked example of standalone-subsystem construction, each with its
own constitution, tests, and build and test reports. Alongside these it carries a working
9-script proof harness with screenshots, live committed sandbox runtime records, JOE display
and ergonomics design documents, and the original `LEVEL1_ASSISTANT_BUILD_PACKAGE_v1.docx`.
