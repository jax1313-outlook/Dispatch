# Adapters

**Contracts first. Adapters second.**

The Joe contract lives in `portal/routes/joe_api.py`, `dispatch/joe_authority.py`
and `dispatch/audit.py`. Nothing in those three files names a vendor — not in the
code and not in the prose. A test enforces it
(`tests/test_joe_api.py::TestJoeIsARoleNotAMicrosoftFeature`).

**This directory is where vendor names are allowed.** Everything here is an
adapter onto that contract: one way of reaching it, from one stack, certified
first. Being first does not make it the definition.

> Joe is a Level 4 Operational Co-Driver. Joe's intelligence is rented.
> Level 1 Transport owns the doctrine, the data, the face, and the audit trail.

## Why the separation is load-bearing

A rented brain is replaceable by definition. The moment a vendor's concepts —
its IDs, its naming, its workflow assumptions — reach the endpoints, the data
structures or the audit records, the rental becomes a marriage. Dispatch would
then be carrying somebody else's product decisions in its own record of what
happened, and the audit log is the one thing that has to outlive every vendor
in it.

So the rule is not stylistic:

- The contract knows about **drivers, missions, fields, channels and results.**
- The adapter knows about **whatever the vendor calls those things.**
- Translation happens here, in one direction, in one place.

## What lives here

| | |
|---|---|
| `joe_connector.yaml` | OpenAPI 3 description of the Joe contract, for building a custom connector in an agent platform |

## Adding a second stack

Nothing in `dispatch/` or `portal/routes/joe_api.py` changes. A new adapter
presents the same bearer token and driver name, sends its own channel string,
and gets the same audit trail in the same shape. That is the whole point of
having done it this way, and it is the only real test of whether it worked.
