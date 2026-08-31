# DISPATCH SWEEP AND THE OPPORTUNITY BOARD

Status: SETTLED DESIGN DIRECTION. Issued by the operator, 31 August 2026. Not implemented.
This records a design he considers closed, so the next builder does not reopen it.

**Where it lives: the Operations Portal.** Not the Driver Portal — see §2.

---

## 1. SWEEP presents opportunities, not freight

**The distinction the operator names as the biggest realisation of the day.**

A traditional load board presents **freight listings**:

> *Here is a load.*

Dispatch presents **qualified opportunities**:

> *Given your truck, your schedule, your equipment, your capacity, your territory, your
> objectives, and your current position — this deserves your attention.*

Those are different products. The first is a list somebody else assembled for everybody. The
second is a judgement about **this** operation, from **this** starting position, on **this**
day.

**Only ranked, reasoned opportunities reach the board.** Anything that survives filtering but
earns no reason to be looked at is noise, and deciding it is noise is itself an operational
decision Dispatch is entitled to make.

## 2. SWEEP is an operations function

Sweeping is deciding **what work to look for**. That is a business function, and it does not
belong on a screen read at seventy miles an hour with seventy-five feet behind you.

**The driver may initiate a sweep. SWEEP administration is not a driver screen.**

This keeps the Driver Portal on mission execution and puts scheduling, sources, scoring
configuration and the board itself in the Operations Portal. It is the same separation
throughout: **business functions and driver functions get separate screens.**

## 3. Manual activation survives, and why it must

Scheduled sweeps run on their own. Manual activation stays, because **a hole in the schedule
is a real operational event** and it does not wait for the next cycle:

| | |
|---|---|
| A cancellation | An early delivery |
| A weather delay | Unexpected availability |
| New capacity opening | |

The operator must be able to say *run SWEEP now* the moment the day changes shape.

## 4. The board: high density, three lines, fast comparison

**Not cards. Not tiles. Not widgets.** A board built for comparison, in the operator's own
examples:

```
97 | JAX → ATL → JAX | TWO LOAD PLAN
$2475 | Complete Wed 18:30 | Capacity OK
Returns Home | Recommended

94 | JACKSONVILLE → SAVANNAH | AVAILABLE NOW
$825 | PU 11:30 | DEL 15:00
Strong Local Fit | Leaves Evening Capacity

72 | ATLANTA → JACKSONVILLE | CONDITIONAL
Useful Only When Paired With Outbound ATL Move
```

Three lines. Full width. Dense.

**The density is the feature, not a compromise.** Comparison is the whole job of this screen,
and comparison requires things to be adjacent. A card layout that shows four opportunities on
a screen has made the operator remember the fifth, which is the cognitive load this design
exists to remove.

Note what each row leads with: **the score, then the shape of the move, then why**. The
number orders the list; the reason is what he actually reads.

## 5. Opportunity types

The board must eventually express every shape the operator already evaluates in his head:

| Type | |
|---|---|
| **Individual** | one load, on its own merits |
| **Paired** | two loads that are worth more together than apart |
| **Conditional** | worth taking *only* if something else happens |
| **Return** | gets the truck home |
| **Schedule-hole fill** | fits a gap that already exists |
| **Repositioning** | worth taking for where it leaves the truck |
| **Sequence** | an ordered set that works as a plan |

**A load board can only express the first.** Everything else requires knowing the truck, the
day and the position — which is exactly the reasoning being formalised.

## 6. The deliverable, in the operator's words

Recorded verbatim, because a paraphrased specification is a different specification:

> SWEEP shall ingest opportunities from multiple sources, apply deterministic policy
> evaluation and scoring, perform contextual opportunity reasoning from the truck's current
> operational starting condition, construct qualified candidate opportunities (including
> individual loads, pairs, returns, sequence opportunities, and schedule-fill opportunities),
> and present only ranked, reasoned opportunities on the SWEEP board. JOE participates as the
> Dispatch co-driver interface and explanation layer because opportunity evaluation is part of
> the co-driver function. Human authority remains responsible for commitment, override, and
> policy decisions.

## 7. What this depends on

Stated so the sequence is visible, not to slow anything down.

| Needs | Because |
|---|---|
| The Policy Profile | scoring against *this* operation rather than a generic one |
| The Capacity Plan | "fits Tuesday" is a question about a day, not a truck |
| Current position | every opportunity type past *individual* is relative to where the truck is |
| The fifteen categories | what "qualified" means, and what a score is made of |

**Pairing is the hard one.** An individual opportunity is scored against policy. A *pair* has
to be constructed before it can be scored — the engine must propose the combination, then
evaluate it, and the number of possible combinations grows fast. That is real work and it is
the last thing to build, not the first.

## 8. Status of the current implementation

The sweep panel — scheduled times, manual *Start Sweep Now*, *Stop Scheduled Sweeping* —
already exists and works. It was lifted off the driver screen into
`portal/templates/_sweep_panel.html`, unchanged, and its API still answers.

**What exists is activation. What is designed here is the board.** They are different things,
and nothing above is built yet.
