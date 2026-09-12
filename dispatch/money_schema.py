"""Exact whole-cent companions for every monetary column.

`dispatch/money.py` explains why money stops being a float. This module is how
the existing tables get there without a rewrite of every write path and without
a data migration that can half-finish.

Each monetary REAL column gains a generated `<name>_cents` INTEGER column:

    ALTER TABLE expenses ADD COLUMN amount_cents INTEGER
        GENERATED ALWAYS AS (CAST(ROUND(amount * 100) AS INTEGER)) VIRTUAL

Three properties make this the right shape rather than a second column somebody
has to remember to update:

**It cannot drift.** A generated column is computed by SQLite on read, from the
column it derives from. There is no write path to forget, no trigger to
mis-order, no backfill that can be interrupted, and no window in which the two
disagree. Adding it is pure DDL -- no rows are rewritten, so it is instant on a
large table and it is reversible by dropping the column.

**It recovers the exact intended amount.** A double can represent any 2-decimal
amount to far better than half a cent, so `ROUND(amount * 100)` returns the cent
the operator actually typed. Float drift is a property of *accumulation*, not of
a single stored value -- which is why the fix is to do every sum, product and
comparison in cents, and why deriving cents from the stored double loses nothing.

**It is honest about what is authoritative.** The REAL column remains what every
existing reader sees, unchanged, so nothing breaks. The cents column is what
arithmetic uses. When the last reader of a REAL column is gone, the generated
column can be materialised and the REAL one dropped; until then there is one
value with two views of it, never two values.

SQLite has supported generated columns since 3.31 (2020). Python 3.11 ships
3.34+, so every supported interpreter has it. A database on an older library
falls back to computing cents in Python at the point of use -- slower, same
answer -- rather than failing to start, because refusing to run is a worse
outcome than a slow report on a machine that is otherwise fine.
"""

from __future__ import annotations

import sqlite3

#: table -> the REAL columns on it that hold money.
MONETARY_COLUMNS: dict[str, tuple[str, ...]] = {
    "rate_confirmations": ("rate_amount",),
    "expenses": ("amount",),
    "settlements": ("invoice_amount", "payment_amount", "factoring_fee"),
    "detention_events": ("hourly_rate",),
    "ifta_fuel_purchases": ("amount",),
    "driver_pay": ("amount", "rate"),
    "maintenance_schedules": ("cost_estimate",),
}


def cents_column(name: str) -> str:
    return f"{name}_cents"


def _generated_column_sql(table: str, column: str) -> str:
    return (
        f"ALTER TABLE {table} ADD COLUMN {cents_column(column)} INTEGER "
        f"GENERATED ALWAYS AS (CAST(ROUND({column} * 100) AS INTEGER)) VIRTUAL"
    )


def supports_generated_columns() -> bool:
    return sqlite3.sqlite_version_info >= (3, 31, 0)


def init_money_schema(conn: sqlite3.Connection) -> dict:
    """Add every missing `_cents` column. Idempotent; reports what it found.

    Returns a summary rather than nothing so `readiness` can state the fact
    ("cents columns: 10 of 10") instead of asserting it.
    """
    added: list[str] = []
    present: list[str] = []
    unsupported: list[str] = []

    if not supports_generated_columns():
        return {
            "supported": False,
            "added": [],
            "present": [],
            "unsupported": [
                f"{t}.{cents_column(c)}" for t, cols in MONETARY_COLUMNS.items() for c in cols
            ],
            "sqlite_version": sqlite3.sqlite_version,
        }

    for table, columns in MONETARY_COLUMNS.items():
        try:
            # table_xinfo, not table_info: a VIRTUAL generated column is hidden
            # from table_info, so checking there would report every cents column
            # as missing and re-run the ALTER on every startup.
            existing = {
                row[1] for row in conn.execute(f"PRAGMA table_xinfo({table})").fetchall()
            }
        except sqlite3.Error:
            continue  # the table is not in this database yet; _SCHEMA creates it first
        if not existing:
            continue
        for column in columns:
            if column not in existing:
                continue
            target = cents_column(column)
            if target in existing:
                present.append(f"{table}.{target}")
                continue
            try:
                conn.execute(_generated_column_sql(table, column))
                added.append(f"{table}.{target}")
            except sqlite3.OperationalError:
                # Already present under a race, or refused by this library.
                unsupported.append(f"{table}.{target}")

    return {
        "supported": True,
        "added": added,
        "present": present,
        "unsupported": unsupported,
        "sqlite_version": sqlite3.sqlite_version,
    }


def money_column_report(conn: sqlite3.Connection) -> dict:
    """Which monetary columns have an exact companion, and which do not."""
    rows = []
    for table, columns in MONETARY_COLUMNS.items():
        try:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_xinfo({table})").fetchall()}
        except sqlite3.Error:
            existing = set()
        for column in columns:
            rows.append(
                {
                    "table": table,
                    "column": column,
                    "cents_column": cents_column(column),
                    "present": cents_column(column) in existing,
                }
            )
    return {
        "rows": rows,
        "complete": all(r["present"] for r in rows),
        "covered": sum(1 for r in rows if r["present"]),
        "total": len(rows),
    }


def verify_money_integrity(conn: sqlite3.Connection, *, epsilon: float = 1e-6) -> dict:
    """Prove every stored amount really is a whole number of cents.

    A generated column cannot drift out of step with the column it derives from,
    so this is not checking SQLite. It is checking the *data*: a REAL value that
    is not a whole number of cents -- 10.007 from a third-party import, a
    per-mile rate typed to four decimals, a figure computed by an older version
    of this program and written back unrounded -- converts to cents by rounding,
    and rounding a value nobody intended to round is exactly the kind of silent
    money change this migration exists to end.

    Reported, never corrected here. Which way 10.007 should go is a decision
    about somebody's invoice, and this module has no standing to make it.
    """
    findings = []
    for table, columns in MONETARY_COLUMNS.items():
        for column in columns:
            cents = cents_column(column)
            try:
                rows = conn.execute(
                    f"SELECT rowid, {column} AS amount, {cents} AS cents FROM {table} "
                    f"WHERE {column} IS NOT NULL"
                ).fetchall()
            except sqlite3.Error:
                continue
            for row in rows:
                scaled = row["amount"] * 100
                fractional = abs(scaled - round(scaled))
                if fractional > epsilon:
                    findings.append(
                        {
                            "table": table,
                            "column": column,
                            "rowid": row["rowid"],
                            "stored": row["amount"],
                            "rounds_to_cents": row["cents"],
                            "sub_cent_remainder": fractional / 100,
                        }
                    )
    return {"ok": not findings, "findings": findings}
