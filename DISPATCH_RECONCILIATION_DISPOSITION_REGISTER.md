# Constitutional Regression Reconciliation — Disposition Register

**Mission:** CONSTITUTIONAL REGRESSION RECONCILIATION, Mike Zachary, 16 September 2026.

> **PRIMARY RULE** — *"Each consequential business act shall have one authoritative operation. Every screen, API route, helper, and test representing that act must call the same authoritative operation."*

Ten batches, 16–17 September 2026. Each has a `DECISION_LOG.md` entry carrying the
verbatim approval that authorised it; this register is the index, not the record.

## A note on the "48 findings"

The audit that opened this mission was run by five read-only agents in a single
working session and its numbered list of findings **was never written to the
repository** — it existed in that conversation and nowhere else. This register
therefore does not reproduce it. Reconstructing a 48-item enumeration from memory
would produce a document that looks authoritative and cannot be checked against
anything, which is the opposite of what a register is for.

What follows is what the batches **disposed of**, every line of which is checkable
against the code, the tests and the `DECISION_LOG` entry named beside it.

---

## Disposed

### Batch 1 — Lifecycle authority

| finding | disposition |
|---|---|
| A started run could be deleted: `en_route_pickup → cancelled → delete`, over the API, no trace | **Fixed.** Deletable only from `created`, and only when no milestone was ever recorded |
| The no-undo rule lived on the glass and in the sandbox sweep, and nowhere in the engine | **Fixed.** *"The glass is not authoritative."* |
| `_try_auto_dispatch` advanced a load to `dispatched` from data entry — status, milestone, visibility and a mailed notification | **Fixed.** A named no-op; the call sites assign and stop |
| A self-dispatched load never rendered START RUN at all | **Fixed** by the above |
| `picked_up`, `in_transit` and `at_delivery` had no exit — a load on the trailer could not be cancelled | **Fixed.** Cancellation reaches all three; the run is recorded and never deleted |
| Audit recommended removing `delivered → archived` and called three tests stale | **Refused by the Owner.** *"some loads genuinely end without a POD coming back."* The three tests were correct and were left alone |

### Batch 2 — Commitment authority

| finding | disposition |
|---|---|
| `committed_at()` read `accepted_at` as a legacy alias **and BOOK wrote it** — pressing *Book Load* satisfied `is_committed()` with none of COMMIT's consequences | **Fixed.** `LEGACY_FIELD` removed; BOOK writes `booked_at` |
| An engineer proposed a compatibility shim | **Refused by the Owner.** *"No compatibility shim is required because there is no business history to preserve."* |
| BOOK on a committed mission could mint a second Mission Number | **Fixed.** Refused |
| PASS refused the discard of a committed record **and fell through**, writing a status and an Archive record for freight on the truck | **Fixed.** 409, and the record is byte-identical afterwards |
| A captured load never got a load number, so its packet filed under `no-load-number` | **Fixed.** COMMIT assigns it. *Found by a test, not by the audit* |
| Two `accepted_at` uses in `library.py` and `reconciliation/` | **Left alone.** A different fact under the same word |

### Batch 3 — The POD correction, verified

| finding | disposition |
|---|---|
| POD upload attached the file and stopped; the load stayed `delivered` and the cockpit asked for the POD for ever | **Fixed** (early, on the Owner's instruction) and **verified on the live path**: 8 of 9 measurable points |
| `completed` was in the driver's closed-status list — the cockpit denied the run at the moment it was finished | **Fixed** |
| Point 9: the retention record carried neither the load number nor the packet path | **Deferred to Batch 5 by the Owner**, held by a strict `xfail`, **closed there** |

### Batch 4 — Communication side effects

| finding | disposition |
|---|---|
| ARRIVE mailed the customer **before** anything looked at the load — a mission never committed still put *"Truck arrived on site SAFELY"* in front of a broker | **Fixed.** Stamp, record, then send. *"gate refuses, no notice goes"* |
| A withheld notice would have read *"I couldn't send the arrival notice myself"* | **Fixed.** A refusal reads as a refusal |
| `notice["sent"]` read `arrived_at` | **Fixed.** Reads whether a notice went |
| The notice promised *"Load Securement Photos"* and *"Delivery Photos"* — names from no vocabulary | **Struck**, not renamed. *"true from all Template emails"* |
| Audit finding: *"three unattended outbound acts"* | **Corrected, not carried.** All three address `reviewer_address()` and go to Ops. The audit classified them wrong |

### Batch 5 — Closeout authority, and point 9

| finding | disposition |
|---|---|
| Point 9: the Archive could not reach the closing packet filed under the tracing number | **Fixed.** `load_number` and `packet_location` on `retention`, read from the packet report — a caller cannot state its own retrieval path |
| Three doors reached `archived`; **two filed nothing** — the Advance button and the batch-status control, which did it by the handful | **Fixed.** Engine first, then the glass |
| A completed load had nowhere to be closed out | **Fixed.** `/closeout` queue on the Operations nav |
| Archive fired with no review | **Fixed.** *"Driver completes the mission. Operations closes the file. Archive performs retention."* A **reviewed-closeout gate, not a mechanical artifact gate** — a checklist would have re-stranded the POD-less loads the 2026-09-16 ruling protects |

### Batch 6 — Mission Visibility

| finding | disposition |
|---|---|
| `customer_note` and `internal_note` erased by every milestone, and again by archiving | **Fixed.** One writer; a caller that says nothing about the notes keeps them |
| `archive_load` also dropped `next_expected_milestone` | **Fixed** |
| `update_load` never refreshed visibility — the office and the customer read different states | **Fixed** |
| `archive_load` asked about closeout before checking the run, so a load still on the road was told to review its file | **Fixed.** Reordered |

### Batch 7 — Capacity truth

| finding | disposition |
|---|---|
| The Booking screen printed *"Mon–Wed and Sat sellable · Thu–Fri held for expedited · Sun closed"* long after `WEEK_PATTERN` was opened to seven OPEN days | **Fixed.** The board drew one rule and the footer named another |
| A headline figure counted *"held"* days, which could only ever be zero | **Removed**, with `held_and_taken` — unreachable by construction |
| Capacity warning Levels 1, 2 and 3 were doctrine and did not exist | **Built.** Position, Time, HOS awareness — all from facts already stored |
| Level 3 appeared to require drive time, which `load_assessment.py:225` forbids | **Resolved by the Owner**: the gap between two typed times. Held by a test that greps the module for `drive_time` |

### Batch 8 — Mission Artifact Intake

| finding | disposition |
|---|---|
| Three attach routes, each with its own handler and refusals | **Fixed.** One route, five classifications. *"Everything else is classification"* |
| **Nothing anywhere could attach a Bill of Lading** — the controlling freight document had no door | **Fixed** |
| The closing packet was built by the cockpit's handler, so the parked Driver Portal's POD route **completed a run and filed nothing** | **Fixed.** The packet lives with the act. *The Batch 3 dead end, still alive on the other screen* |
| *"No file was attached"* told a driver nothing about which tile he mistapped | **Fixed.** The refusal names what was expected |

### Batch 9 — Visible language

| finding | disposition |
|---|---|
| REJECT's confirm said *"It stays on record"* while ruling D12 discards the card and capture together | **Fixed** |
| *"Lane History"* on two screens | **Renamed** to Previous Runs. *"there is no lane use in dispatch"* |
| The cockpit pointed a driver at *Book Load*, which stopped opening a load when BOOK was separated from COMMIT | **Fixed** |

### Batch 10 — Verification

| finding | disposition |
|---|---|
| **`create_load_with_id` created no Mission Visibility record** — and it is the path COMMIT uses, so every mission committed through the Mission Brief had no visibility record until the driver's first tap | **Fixed.** *Found by the end-to-end walk; no batch had caught it* |
| A note written before the truck rolled was written to a row that did not exist and **silently lost** | **Fixed.** `update_visibility_notes` goes through the one writer |
| Batch 9 shipped with no `DECISION_LOG` entry | **Fixed.** Entry written during this batch's audit of the record itself |

---

## Open for the Owner

Nothing below is a defect anyone has ruled on. Each is recorded rather than
decided, because deciding it here would be an engineer writing doctrine.

| item | why it is his |
|---|---|
| **The engine imports the portal in nine modules** (15 imports: data directories, the sandbox, the publisher, the conflict model). One is at module level (`dispatch/audit.py`); the rest are deferred inside functions, which is why nothing has broken. | Whether the boundary forbids this is architecture, not a bug. Pinned by test at 15 so it cannot grow quietly |
| **`/calendar` is a third month view** of load days, beside Booking's MONTH and the driver's calendar. It stores no day-state, so it breaks no scheduling rule. | Whether three month views should exist is a tab-walk question |
| **`lane_history` remains the engine's internal name** for Previous Runs | Batch 9 was visible language; renaming store and service functions is wider than the ruling asked |
| **A captured card carries no contact at all** if neither phone nor email was taken. His ruling: *"if both are missing this would create an ALERT to be flashed at time of capture."* | **Ruled, not built.** Capture-path work, both doors — voice and the typed New Mission card |
| **The BOL line on the closeout checklist cannot yet be satisfied** by any route | It is shown rather than hidden, on the same principle as the brief's empty fields. Nothing blocks on it |
| **Six required fields on New Mission** | Raised earlier in the build and never answered |
| **`D:\Memory\Evidence` write path** | Raised earlier in the build and never answered |

---

## What the verification proves, and what it does not

`tests/test_the_whole_run.py` walks one mission from capture to retention
**through the controls a person presses** — 24 checks, no engine function called
directly to build a precondition. It holds each batch's ruling at the end of the
whole chain rather than in isolation, and half of it proves the negatives: that
ARRIVE tells nobody on an uncommitted mission, that BOOK does not commit, that
the Advance button cannot archive, that a started run cannot be deleted, that the
old attach routes are gone.

**It is still a test.** The Owner's completion gate is unchanged and is not met
by anything in this register:

> nothing is finished until a real load runs on Mike's laptop.

Two missions have already failed on that gate. This one is not claimed to have
passed it.
