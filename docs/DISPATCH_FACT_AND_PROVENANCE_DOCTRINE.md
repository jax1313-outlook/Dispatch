# DISPATCH FACT AND PROVENANCE DOCTRINE

Status: DOCTRINE. No runtime behaviour is changed by this document.

---

## 1. The principle

**Dispatch does not invent facts. Every fact carries its origin.**

A number on a screen that cannot be traced to a source is not information. It is a guess
wearing the costume of information, and it is more dangerous than a blank field, because
a blank field makes the operator go look.

## 2. Four origins, always distinguishable

| Origin | Meaning | Example |
|---|---|---|
| **SOURCE** | Came from outside, as-is | Broker rate, SAM deadline, load number |
| **DERIVED** | Computed by the chassis from SOURCE facts and the policy profile | Fit score, deadhead miles, recommendation |
| **HUMAN** | Entered or authorised by the operator | Decision, override, note, correction |
| **UNKNOWN** | Not established | Missing deadline, unresolved location |

Every displayed fact resolves to one of these. A DERIVED fact must be reproducible from
its inputs and the profile version. A SOURCE fact must name its source and the time it was
retrieved.

## 3. UNKNOWN is a value, not an absence

`UNKNOWN` is displayed, it lowers confidence, and it never silently becomes `0`, `False`,
`no risk`, or an average.

**Recovered from v1.3.3**, which handled this correctly:

```python
return -5, 'UNKNOWN LOCATION', 'Location could not be confidently classified from SAM data.'
```

An unknown location is scored differently from a known-bad one, carries its own reason,
and is visible as unknown.

**Recovered from v1.0.1**, which distinguished three deadline states rather than two:
parsed and feasible, parsed and blocking, and `"Deadline could not be parsed"` — a third,
honest outcome.

## 4. No fabrication — the lineage precedent

The L1-COS Master Constitution forbade fabricated data from the beginning. v1.0.1's code
contained `sample_opportunities`, a fallback that generated plausible opportunities when
the connector failed.

**The governing document and the running code disagreed for the first build of the
system.** v1.1 removed the fallback and brought the code into line.

Two lessons Dispatch inherits:

1. **Doctrine is not self-enforcing.** A rule in a markdown file is not a rule in the
   product until something in the product enforces it.
2. **A fallback that fabricates is worse than a failure that reports.** The failure sends
   the operator to look. The fabrication sends them to a load that does not exist.

## 5. Provenance survives enrichment

The Mission Record is progressively enriched — one record, gaining detail over its life.
Enrichment adds; it does not overwrite origin.

- The broker's load number is preserved **exactly** as given, forever, as SOURCE.
- The Dispatch mission number is ours, and is DERIVED.
- A corrected value keeps the original alongside it, marked HUMAN with a timestamp.
- A re-evaluated score does not erase the score the human saw when they decided.

That last point is what makes a past decision auditable. If the score is silently
recomputed under a new profile, the record no longer explains why the human chose what
they chose.

## 6. Reasons, risks and missing information are first-class

Recovered from v1.0.1 and v1.3.3, both of which stored these as separate fields rather
than folding them into a score:

- **Reasons** — why this scored as it did, in plain language
- **Risks** — what could go wrong, with severity
- **Missing information** — what was not known at evaluation time

These are not presentation. They are outputs of the engine, stored with the record. A
score without reasons is unexplainable, and an unexplainable score cannot be trusted or
corrected.

## 7. The system never claims an act it did not perform

Dispatch may state:

- what it found
- what it computed
- what it recommends
- what the human authorised, and when

Dispatch may not state that anything was sent, filed, accepted, booked or approved unless
that act actually occurred and was recorded. This is shared with the JOE authority model
and is not configurable.
