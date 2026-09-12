"""Backups, where the operator actually looks.

`dispatch/backup.py` could capture the estate, verify it and restore it, and
`dispatch_launcher/backups.py` could report on the result. Nothing anywhere
could *take* one from a screen. The whole estate -- SQLite, twelve JSON stores
and every uploaded evidence file -- sat on one laptop behind Mike remembering a
script path.

This page is deliberately thin: it reads the same status the launcher reads, and
the two buttons call the same engine the launcher calls, so there is one
implementation of "take a backup" and one answer to "is there one".

Running a backup inside a request is defensible only because of what this
program is: a single-operator application on that operator's own machine,
serving one person who just pressed the button and is watching. It is not a
multi-tenant service, and there is no queue to put the work on that would not be
a second thing to keep running. The work is bounded by the size of the estate,
and the operation is idempotent -- a second click writes a second archive, it
does not corrupt the first.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

maintenance_bp = Blueprint("maintenance", __name__)


def _status():
    from dispatch_launcher import backup_actions, backups

    directory = backup_actions.resolve_backup_dir()
    return backups.backup_status(directory), directory


@maintenance_bp.route("/maintenance")
def maintenance():
    from dispatch.db import get_connection
    from dispatch.money_schema import money_column_report, verify_money_integrity

    status, directory = _status()
    with get_connection() as conn:
        money_report = money_column_report(conn)
        money_integrity = verify_money_integrity(conn)

    return render_template(
        "maintenance.html",
        backup=status,
        backup_dir=str(directory) if directory else None,
        money_report=money_report,
        money_integrity=money_integrity,
    )


@maintenance_bp.route("/maintenance/backup", methods=["POST"])
def run_backup():
    from dispatch_launcher import backup_actions

    result = backup_actions.create(compress=bool(request.form.get("compress")))
    flash(
        ("Backup taken. " if result.ok else "Backup failed. ") + result.summary,
        "success" if result.ok else "error",
    )
    return redirect(url_for("maintenance.maintenance"))


@maintenance_bp.route("/maintenance/prove-restore", methods=["POST"])
def run_prove_restore():
    """Restore the newest backup into a scratch directory and record the result.

    Never the live paths: `dispatch.readiness.check_restore_destination` refuses a
    destination that overlaps the live database or the live evidence store, and
    it runs before anything is written.

    `confirmed_by` is only ever what a person typed. A blank one records
    Code-automated and the status stays UNVERIFIED, because the program can prove
    the archive restores and that every hash matches -- it cannot prove the
    restored Dispatch works, and manufacturing that claim is the thing the whole
    verification record exists to prevent.
    """
    from dispatch_launcher import backup_actions

    confirmed_by = (request.form.get("confirmed_by") or "").strip() or None
    result = backup_actions.prove_restore(confirmed_by=confirmed_by)
    flash(
        (result.summary + " " + result.detail.replace("\n", " ")) if result.ok else
        ("Restore proof failed. " + result.summary + " " + result.detail),
        "success" if result.ok else "error",
    )
    return redirect(url_for("maintenance.maintenance"))
