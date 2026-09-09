 What Billing should show an owner/operator$# What Billing should show an owner/operator
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$- Opened: 2026-09-09, by Mike, during the Billing walk
 What Billing should show an owner/operator$- Status: OPEN — target state set, most of it not built
 What Billing should show an owner/operator$- Framed as a KEEP list, but see below: only part of it exists to keep
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$## Mike's ruling
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$Billing should carry owner/operator operational-awareness metrics, not
 What Billing should show an owner/operator$accounting.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**Weekly revenue.** How much did I make this week?
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**Monthly revenue.** How much did I make this month?
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**Rolling revenue trends.** Last 7 days against previous 7 days. Last 30 days
 What Billing should show an owner/operator$against previous 30 days. The purpose is one question: am I moving up or down?
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**Gross profit estimate.** Revenue, minus fuel, minus maintenance escrow. The
 What Billing should show an owner/operator$purpose is: is the truck approximately making money? Not accounting accuracy.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$## What exists today
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$Checked on `tab-walk/build`, 2026-09-09.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$| Wanted | Class | Notes |
 What Billing should show an owner/operator$| --- | --- | --- |
 What Billing should show an owner/operator$| Weekly revenue | Missing | Nothing computes a week |
 What Billing should show an owner/operator$| Monthly revenue | Implemented but unverified | `get_chart_data` returns monthly revenue, but nothing renders it since Load Overview came off Home. It is a chart series, not a headline number |
 What Billing should show an owner/operator$| Rolling 7 and 30 day comparisons | Missing | Nothing computes a rolling window or a prior-period comparison anywhere |
 What Billing should show an owner/operator$| Gross profit estimate | Partially proven | `get_financial_dashboard` computes revenue minus all expenses, all-time. Fuel is one of eleven expense categories, so a fuel-only subtotal is reachable |
 What Billing should show an owner/operator$| Maintenance escrow | Missing | The word does not appear anywhere in the repository. There is a `repair` expense category, which is money already spent, not money set aside |
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$So this is a target state, not a keep list. The one thing that genuinely exists
 What Billing should show an owner/operator$to keep is the revenue figure itself.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$## What the current screen actually shows
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$Total revenue, profit, paid, invoiced, overdue and disputed. All of them
 What Billing should show an owner/operator$all-time, none of them windowed. That is why the screen reads 100% margin: no
 What Billing should show an owner/operator$expenses are recorded, so revenue minus expenses is revenue.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$An all-time total answers a different question from the one Mike is asking. It
 What Billing should show an owner/operator$cannot say whether he is moving up or down, which is the whole point of the
 What Billing should show an owner/operator$rolling comparison.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$## Two things to settle before building
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**What a maintenance escrow is.** A per-mile or per-load accrual set aside
 What Billing should show an owner/operator$against future repairs is a new concept. It needs a rate, a place to hold the
 What Billing should show an owner/operator$balance, and a rule for when it is drawn down. None of that exists.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$**Whether estimate means estimate.** Mike said not accounting accuracy. If fuel
 What Billing should show an owner/operator$and escrow are the only deductions, the number will differ from the profit
 What Billing should show an owner/operator$figure on the same screen, which subtracts all eleven expense categories. Two
 What Billing should show an owner/operator$different profit numbers on one screen needs a deliberate answer, not an
 What Billing should show an owner/operator$accident.
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$## Answer
 What Billing should show an owner/operator$
 What Billing should show an owner/operator$Not yet answered.
