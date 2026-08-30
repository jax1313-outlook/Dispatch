# Sandbox survey procedure — the read-only first pass over `D:\Sandbox\Play Pen`

**Status of the survey itself: `ABSENT`.** It has not been run. Nothing under
`D:\Sandbox\Play Pen` has been read, listed, hashed, sampled or classified by
anyone building this tool. The tool was written and proven in an isolated Linux
container with no `D:` drive, no mount, no network path and no credential
reaching the Windows machine that holds that folder.

**Status of the tool's behaviour on Mike's machine: `UNVERIFIED`.** Its behaviour
is proven by 77 tests in `tests/test_sandbox_survey.py`, which are evidence of
software behaviour only and are never operational proof. Only a run on the real
machine produces operational truth, and only Mike can perform it.

Template copies of all nine output documents are committed in
`docs/readiness/sandbox_templates/`, so the shape of every report can be
inspected before anything is run. Every content claim in them is `ABSENT`. The
same templates are also written to `proof/sandbox/`, which is gitignored
alongside the rest of the local-machine proof artifacts.

---

## 1. What this command does

It walks `D:\Sandbox\Play Pen`, opens every file **read-only**, hashes it,
reads the first 64 KB of each for heuristics, classifies each file against named
deterministic rules, groups exact and near duplicates, flags sensitive material
by path and category, and writes eleven timestamped documents into
`D:\Sandbox\Play Pen\Dispatch`.

## 2. What it will never do

- Move, rename, delete, overwrite, deduplicate, convert, archive, upload or
  commit any file. There is **no code path** in the package that performs a
  move, a rename or a merge — not behind a flag, not behind a confirmation
  prompt, not at all. `tests/test_sandbox_survey.py` proves this by parsing the
  package's own source and failing the build if such a call appears.
- Execute anything it finds. No script, notebook, macro or binary in the
  Sandbox is run, imported or evaluated.
- Follow a link out of the Sandbox. Symlinks and NTFS junctions are inventoried
  as links and never opened; a link whose target sits outside the Sandbox is
  recorded as escaping and left alone.
- Open a network connection, or fetch anything referenced inside a Sandbox file.
- Write anywhere except `D:\Sandbox\Play Pen\Dispatch`. Every write goes through
  one function that refuses any destination outside that folder, and opens with
  mode `"x"` so an existing file can never be replaced.
- Quote any file's contents in any report. Reports carry paths, sizes,
  timestamps, hashes, class names, rule identifiers and counts — never content.
- Treat anything it finds as doctrine or as a decision Mike has made.

The only change it makes to the disk is creating
`D:\Sandbox\Play Pen\Dispatch` if it does not exist, and writing new files into
it. That is the single permitted structural change.

## 3. Before you run it

Nothing to install. Python 3.11 or later, standard library only, no third-party
packages, no network access required.

```powershell
cd C:\path\to\Dispatch
python --version          # expect 3.11 or later
```

## 4. Run it — dry run first

The dry run scans and reports to the screen. It creates no folder and writes no
file, so it is the safest possible way to see what the real run will do.

```powershell
python scripts\sandbox_survey.py --dry-run
```

Read the summary. If the file count, the folder count and the class breakdown
look like your folder, go on. If they do not, stop and say so — a wrong count
means a wrong path, not a wrong folder.

## 5. Run it for real

```powershell
python scripts\sandbox_survey.py
```

Defaults are `--sandbox-root "D:\Sandbox\Play Pen"` and
`--output-root "D:\Sandbox\Play Pen\Dispatch"`. To survey a copy instead of the
live folder, point `--sandbox-root` at the copy; the output folder follows it
automatically, so a copy is never surveyed while writing into the original.

```powershell
python scripts\sandbox_survey.py --sandbox-root "E:\Sandbox Copy\Play Pen"
```

### The flags

| flag | what it does |
| --- | --- |
| `--sandbox-root` | the folder to survey, read-only. Default `D:\Sandbox\Play Pen`. |
| `--output-root` | the one folder the tool may write to. Must be **inside** `--sandbox-root` or the run is refused. Default `<sandbox-root>\Dispatch`. |
| `--dry-run` | scan and report to the screen; create no folder, write no file. |
| `--max-bytes` | how much of each file is read for classification heuristics. Default 65536. The whole file is always hashed regardless. |

### Exit codes

| code | meaning |
| --- | --- |
| `0` | the survey ran and the documents were written. |
| `2` | a safety rule refused the run, or `--max-bytes` was nonsense. Nothing was read and nothing was written. The reason is printed. |

### When it refuses

A refusal prints `REFUSED:` and a plain-language reason, then
`Nothing was read and nothing was written.` It refuses when the Sandbox path
does not exist, is not a folder, when the output folder is outside the Sandbox
folder or is the Sandbox folder itself, when the output path exists but is a
file, or when the output folder cannot be created. A refusal is always safe:
nothing has happened.

## 6. What you get, and what each document means

Eleven files, all named with the run's UTC timestamp so a second run never
overwrites the first.

| document | what it is | what it is not |
| --- | --- | --- |
| `SANDBOX_FILE_INVENTORY_<run>.csv` | every file: path, size, modified, SHA-256, primary class, secondary classes, Dispatch-related Y/N, and the rule ids behind the classification. The machine-readable form; header lines start with `#`. | not a judgement about any file's value. |
| `SANDBOX_FILE_INVENTORY_<run>.md` | the same data as a readable summary, plus totals and the prior output-folder contents listed separately. | not authoritative where it differs from the CSV. |
| `SANDBOX_KNOWLEDGE_MAP_<run>.md` | the narrative: what exists, how it relates, what appears current versus superseded, what questions are open, what could not be determined. States the rules of interpretation verbatim. | not a statement of what is true about the business. It is a statement about what is on a disk. |
| `DISPATCH_RESEARCH_CANDIDATES_<run>.md` | architecture and research material carrying a Dispatch signal, with why each qualified. | **not accepted architecture.** Research is not a decision. |
| `POSSIBLE_DUPLICATES_<run>.md` | exact SHA-256 groups and near-duplicate groups, each with the evidence for the match — the hash, or the similarity score and its inputs. | not an instruction to delete anything. Nothing is ever deleted. |
| `GOVERNANCE_AND_DOCTRINE_CANDIDATES_<run>.md` | material that reads as doctrine, tagged **candidate**, with which locked doctrine it matches or conflicts with. | **not doctrine.** Notes are not doctrine. Only you can promote a candidate. |
| `MIKE_DECISION_CANDIDATES_<run>.md` | decisions that appear recorded, decision candidates that were downgraded and why, and questions that appear to need a decision. | not a decision, and not a record that you have seen it. |
| `SENSITIVE_MATERIAL_REPORT_<run>.md` | paths and categories of credentials, personal data, financial data and third-party confidential material. | **contains no excerpts.** Never a copy of what it found. |
| `PROPOSED_FOLDER_STRUCTURE_<run>.md` | a target structure organised around three separated sources of truth. | not applied, and not applied later by this tool. |
| `PROPOSED_ORGANIZATION_ACTIONS_<run>.md` | a numbered list of reversible moves, merges to review, and triage tasks. | **nothing in it has been executed and this tool cannot execute it.** See §8. |
| `sandbox_survey_<run>.json` | the full machine-readable result. Every document above is generated from this file and nothing else. | not a report; the input to the reports. |

### Reading the classes

Every file gets one primary class and any number of secondary classes from a
closed set: `Knowledge`, `Evidence`, `Research`, `Decision`, `Doctrine`,
`Draft`, `Duplicate`, `Historical`, `Personal`, `Sensitive`, `Unknown`.

The rules of interpretation, reproduced in the knowledge map itself:

1. Architecture research is not accepted architecture.
2. Notes are not doctrine.
3. AI-generated reports are not human decisions.
4. A file is `Decision` only if it records an explicit human decision with an
   identifiable actor; otherwise it is at most a `Decision` **candidate**.
5. `Doctrine` is assigned only to material that matches doctrine already locked
   in this mission or in the repository; everything else that looks like
   doctrine is a `Doctrine` **candidate**.
6. When in doubt, `Unknown`. Never upgrade confidence to make the map look
   complete.

A large `Unknown` count is not a defect. It is the tool declining to guess.

### Files it could not read

A file that cannot be opened — a permission error, a lock held by another
program, a disconnected network path — is still inventoried, classified
`Unknown`, with the operating system's error recorded against it. It is never
silently skipped, because a silently skipped file would make the inventory lie.

## 7. Running it again

Run it as often as you like. Output filenames carry the run's timestamp, the
writer opens with mode `"x"` and refuses to replace an existing file, and the
contents of the output folder are excluded from the next run's inventory —
listed separately as "prior output-folder contents" instead — so the map never
reads its own reports back in as if they were Sandbox material.

## 8. `PROPOSED_ORGANIZATION_ACTIONS` is a separate decision, and this tool cannot perform it

**Executing any action in `PROPOSED_ORGANIZATION_ACTIONS` is a separate decision
by Mike Zachary, carried out by Mike Zachary, with tooling that is not this
tool.** This tool contains no move, no rename, no merge and no delete. There is
no flag that enables one, no environment variable that unlocks one, and no
second mode. If you want the reorganisation performed, that is a new piece of
work with its own approval — and it should start from the inventory CSV of a
specific run, so that every move is reversible against a recorded prior state.

Nothing in any of these documents is accepted doctrine, and nothing in them is a
decision you have made. Until you say otherwise, in your own words, every
classification in them is a proposal about someone else's filing cabinet.

## 9. If something goes wrong

- **It refused.** Read the reason after `REFUSED:`. Nothing was read and nothing
  was written; fix the path and run it again.
- **It reported far fewer files than you expect.** Check `--sandbox-root`, then
  check the unreadable count in the summary — a folder the account cannot read
  reports as unreadable entries, not as absent ones.
- **A file you care about is `Unknown`.** That is the tool declining to guess.
  Open the file; the answer is a fact about the file, not about the tool.
- **It flagged something sensitive that is not.** The detectors are deliberately
  eager, because a false positive costs half a minute and a false negative sends
  a credential into a reorganisation plan unflagged.
- **You want the survey undone.** Delete `D:\Sandbox\Play Pen\Dispatch`. That
  folder is the only thing the run created, and nothing else on the disk was
  touched.
