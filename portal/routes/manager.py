"""Manager's Staff Report page -- read-only.

Per DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md, this is the one
Portal surface this build adds. GET only -- no action buttons, no
approve/dismiss/promote/route capability. Viewing what Manager
prepared is not gated by login in this build (see Section 10 of the
design: action capability, not viewing, is what would need session/
role awareness -- that's Portal-Wide Enforcement-adjacent territory,
not part of this build).

The Stage Gate summary (Phase M4, DISPATCH_STAGE12_MANAGER_M4_MIRROR_DESIGN_v1.md)
fails soft by design: stage_gate.build_summary() returns None if
docs/STAGE_STATUS.json is missing or malformed, and the template
simply omits that panel -- the signal-pipeline report above it is
never affected either way.
"""

from __future__ import annotations

from flask import Blueprint, render_template

from dispatch.manager.staff_report import generate_staff_report
from dispatch.manager.stage_gate import build_summary

manager_bp = Blueprint("manager", __name__)


@manager_bp.route("/manager")
def staff_report():
    report = generate_staff_report()
    return render_template(
        "manager.html",
        counts=report["counts"],
        cards=report["cards"],
        stage_gate=build_summary(),
    )
