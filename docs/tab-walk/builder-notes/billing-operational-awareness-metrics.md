# What Billing should show an owner/operator

- Opened: 2026-09-09, by Mike, during the Billing walk
- Status: OPEN — target state set, most of it not built
- Framed as a KEEP list, but see below: only part of it exists to keep

## Mike's ruling

Billing should carry owner/operator operational-awareness metrics, not
accounting.

**Weekly revenue.** How much did I make this week?

**Monthly revenue.** How much did I make this month?

**Rolling revenue trends.** Last 7 days against previous 7 days. Last 30 days
against previous 30 days. The purpose is one question: am I moving up or down?

**Gross profit estimate.** Revenue, minus fuel, minus maintenance escrow. The
purpose is: is the truck approximately making money? Not accounting accuracy.

## What exists today

Checked on `tab-walk/build`, 2026-09-09.

| Wanted | Class | Notes |
| --- | --- | --- |
| Weekly revenue | Missing | Nothing computes a week |
| Monthly revenue | Implemented but unverified | `get_chart_data` returns monthly revenue, but nothing renders it since Load Overview came off Home. It is a chart series, not a headline number |
| Rolling 7 and 30 day comparisons | Missing | Nothing computes a rolling window or a prior-period comparison anywhere |
| Gross profit estimate | Partially proven | `get_financial_dashboard` computes revenue minus all expenses, all-time. Fuel is one of eleven expense categories, so a fuel-only subtotal is reachable |
| Maintenance escrow | Missing | The word does not appear anywhere in the repository. There is a `repair` expense category, which is money already spent, not money set aside |

So this is a target state, not a keep list. The one thing that genuinely exists
to keep is the revenue figure itself.

## What the current screen actually shows

Total revenue, profit, paid, invoiced, overdue and disputed. All of them
all-time, none of them windowed. That is why the screen reads 100% margin: no
expenses are recorded, so revenue minus expenses is revenue.

An all-time total answers a different question from the one Mike is asking. It
cannot say whether he is moving up or down, which is the whole point of the
rolling comparison.

## Two things to settle before building

**What a maintenance escrow is.** A per-mile or per-load accrual set aside
against future repairs is a new concept. It needs a rate, a place to hold the
balance, and a rule for when it is drawn down. None of that exists.

**Whether estimate means estimate.** Mike said not accounting accuracy. If fuel
and escrow are the only deductions, the number will differ from the profit
figure on the same screen, which subtracts all eleven expense categories. Two
different profit numbers on one screen needs a deliberate answer, not an
accident.

## Answer

Not yet answered.
