"""Money as whole cents. One representation, one rounding rule, no drift.

Every monetary column in this schema was declared REAL and every monetary field
was a Python float, so `rate_amount`, `invoice_amount`, `payment_amount`,
`factoring_fee`, driver pay and IFTA fuel all carried binary fractions that
cannot represent a decimal cent. `Decimal` appears nowhere in the repository;
what does appear is 102 `round()` calls, which is the shape of a program
patching drift at every display site while the accumulator keeps it:

    300 fuel surcharges of 18.35   ->  5505.000000000014
    Settlement.net_payment          ->  payment_amount - factoring_fee, unrounded

The service layer knew. `get_financial_dashboard()` carries a comment recording
that summing raw floats made two reports disagree by pennies on identical data,
and the workaround adopted was to round every row before adding it. That works
right up until the rounding itself is the thing under audit -- and
`services.compute_ifta_report()` computes tax owed for a government filing.

So money stops being a float.

**Integer cents, not Decimal.** SQLite stores INTEGER exactly and REAL as a
double; a Decimal would have to be serialised to TEXT and parsed back on every
read, and one bad parse anywhere silently becomes a wrong number. An integer
count of cents is exact in the database, exact in Python, exact in JSON, and
sorts and sums correctly in SQL. Decimal is used here only at the boundary,
where a string or float becomes cents, because that is the one place a decimal
fraction genuinely exists.

**ROUND_HALF_UP, not banker's rounding.** Python's built-in `round()` rounds
halves to even: `round(0.125, 2)` is 0.12. Invoices, settlements and tax
schedules round halves away from zero. Every conversion here uses ROUND_HALF_UP
so that what Dispatch prints is what an accountant, a broker and a state fuel-tax
form all expect, and so that the same input always produces the same cent.

**Allocation, not division.** Splitting $100.00 three ways as 33.33 x 3 loses a
penny. `allocate()` distributes the remainder deterministically so the parts
always sum exactly to the whole -- which is what a settlement split across two
drivers, or a fuel surcharge apportioned across jurisdictions, requires.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Iterable

CENTS = Decimal("0.01")


class MoneyError(ValueError):
    """A value that cannot be a monetary amount."""


def to_cents(value) -> int:
    """Any reasonable representation of an amount -> whole cents.

    Accepts int cents-free amounts as dollars (``5`` is $5.00, not 5c), floats,
    strings with or without a currency symbol or thousands separators, Decimals,
    and None (which is zero). A float is converted through its shortest repr
    rather than its binary expansion: `Decimal(2675.15)` is
    2675.1500000000000909..., and rounding *that* is how a value that was typed
    as 2675.15 becomes 2675.16 at some later scale.
    """
    if value is None:
        return 0
    if isinstance(value, bool):  # bool is an int; refuse it before it becomes $1
        raise MoneyError(f"not a monetary amount: {value!r}")
    if isinstance(value, int):
        return value * 100
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, float):
        dec = Decimal(repr(value))
    elif isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "")
        if not text:
            return 0
        negative = text.startswith("(") and text.endswith(")")  # (12.34) accounting negative
        if negative:
            text = text[1:-1]
        try:
            dec = Decimal(text)
        except InvalidOperation as exc:
            raise MoneyError(f"not a monetary amount: {value!r}") from exc
        if negative:
            dec = -dec
    else:
        raise MoneyError(f"not a monetary amount: {value!r}")

    if not dec.is_finite():
        raise MoneyError(f"not a monetary amount: {value!r}")
    return int(dec.quantize(CENTS, rounding=ROUND_HALF_UP) * 100)


def to_decimal(cents: int) -> Decimal:
    """Cents -> an exact Decimal amount. Use this for anything printed or filed."""
    return (Decimal(int(cents)) / 100).quantize(CENTS)


def to_float(cents: int) -> float:
    """Cents -> float, for the JSON and template surfaces that still expect one.

    Lossy by nature, and deliberately the last step rather than the first: the
    float is produced from an exact value at the moment of display, so it is
    never accumulated and never stored.
    """
    return float(to_decimal(cents))


def format_money(cents: int, *, symbol: str = "$") -> str:
    """`-$1,234.50`. Negative sign outside the symbol, thousands separated."""
    sign = "-" if cents < 0 else ""
    whole, part = divmod(abs(int(cents)), 100)
    return f"{sign}{symbol}{whole:,}.{part:02d}"


def multiply(cents: int, factor) -> int:
    """Cents x a rate (miles, hours, a percentage already divided by 100).

    The multiplication happens in Decimal and rounds once, at the end. Multiplying
    floats and rounding at each step is how a per-mile rate over 1,140 miles ends
    up a cent away from the same calculation done on paper.
    """
    if isinstance(factor, float):
        factor = Decimal(repr(factor))
    elif not isinstance(factor, Decimal):
        factor = Decimal(str(factor))
    product = (Decimal(int(cents)) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(product)


def percentage(cents: int, percent) -> int:
    """`percent` per cent of `cents`, rounded once. 27% of $2,675.15 is $722.29."""
    if isinstance(percent, float):
        percent = Decimal(repr(percent))
    elif not isinstance(percent, Decimal):
        percent = Decimal(str(percent))
    return multiply(cents, percent / 100)


def total(values: Iterable[int]) -> int:
    """Sum cents. Exact by construction -- this is the whole point of the type."""
    return sum(int(v) for v in values)


def allocate(cents: int, weights: list) -> list[int]:
    """Split an amount so the parts sum exactly to the whole.

    100.00 split three ways is 33.34 / 33.33 / 33.33, not 33.33 x 3 with a penny
    unaccounted for. The remainder goes to the earliest parts, which is
    arbitrary but deterministic -- the property that matters is that
    `sum(allocate(x, w)) == x` for every input, so a settlement split never
    invents or loses money.
    """
    if not weights:
        raise MoneyError("cannot allocate across no weights")
    decs = [Decimal(str(w)) for w in weights]
    if any(w < 0 for w in decs):
        raise MoneyError("allocation weights cannot be negative")
    weight_total = sum(decs)
    if weight_total == 0:
        raise MoneyError("allocation weights sum to zero")

    amount = int(cents)
    parts = [
        int((Decimal(amount) * w / weight_total).to_integral_value(rounding="ROUND_DOWN"))
        for w in decs
    ]
    remainder = amount - sum(parts)
    step = 1 if remainder >= 0 else -1
    index = 0
    while remainder != 0:
        parts[index % len(parts)] += step
        remainder -= step
        index += 1
    return parts


def is_cents_column(name: str) -> bool:
    """The naming convention that makes the representation self-describing."""
    return name.endswith("_cents")
