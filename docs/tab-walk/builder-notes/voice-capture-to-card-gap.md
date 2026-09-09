# Voice capture writes to a store no screen reads

- Opened: 2026-09-09, found while returning to the JOE build
- Status: OPEN — this is the blocker on the end-to-end test
- Not a tab-walk finding. Recorded here because this is where findings live.

## The gap

Mike wants one test: speak a board listing, watch it become an Opportunity Card,
follow it through the program. That test cannot complete today, and the reason
is one seam.

There are two stores and nothing joins them.

| Store | Written by | Read by |
| --- | --- | --- |
| `opportunities` table, `dispatch/opportunity.py` | `POST /api/joe/opportunity`, the voice capture contract | `joe_api.py`, one adapter, and tests. **No screen** |
| Sandbox JSON store, `portal/models/sandbox.py` | The Dispatch and SAM page loads | Every portal screen, including the JOE portal home, candidate queue, booking board and mission brief |

The JOE portal's own screens read the sandbox, not the opportunity table.
`dispatch/opportunity.py` contains no reference to the sandbox and the sandbox
contains no reference to opportunities. The word appears in `sandbox.py` twice,
both times as the unrelated field `economic_opportunity_flag`.

So a capture succeeds, mints its `OPP-` id, dedups correctly, writes its audit
row, returns a spoken echo, and then stops. Nothing downstream can see it.

## What is proven, and what is not

| | Class |
| --- | --- |
| The voice plug-in exists on this machine, at `D:\Joe Assistant\Assistant_Plugin` | Proven by inspection |
| The capture contract exists and is complete: validation, dedup, id minting, rehearsal tagging, bearer auth, audit | Proven by inspection |
| A capture becomes a row in the opportunities table | Implemented but unverified — no capture has been run and checked |
| A capture becomes a card any screen renders | **Missing.** No code path exists |
| The card flows through commit, mission and archive | Untestable until the above exists |

## Where it lives

None of this is on `main`. All of it is on `merge/main-into-joe-portal`: the
plug-in contract, the opportunity module, the JOE portal screens, and six JOE
test files. The tab-walk changes are on `tab-walk/build`, cut from `main`. The
two lines have not met.

## The one missing piece

A bridge from a captured Opportunity to a card the portal renders. Either the
capture also creates a sandbox entry, or the screens learn to read both stores.
That is the decision, and it is Mike's.

Everything else the end-to-end test needs already exists on the JOE branch.

## Answer

Not yet answered.
