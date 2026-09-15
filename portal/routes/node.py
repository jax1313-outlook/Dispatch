"""Node health on the screen (CO-11): the Operations page, its JSON, and the cockpit card.

Read-only. Every route here only reports what dispatch/node_health.py observed.

Gates, and why they are these:

* ``/operations/node`` and ``/api/node/health`` sit behind the ordinary Operations sign-in
  (portal/app.py ``_require_authority_login``). They show paths, zones and record locations.
* ``/portal/node-card`` is also open to a driver sign-in, through ``NODE_DRIVER_ENDPOINTS``, which
  the same gate reads. It returns the short driver-worded lines the NODE card in the Driver
  Cockpit displays, and nothing else.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from dispatch import node_health

node_bp = Blueprint("node", __name__)

#: Endpoints a driver sign-in may reach, in addition to portal.routes.joe_portal's
#: DRIVER_COCKPIT_ENDPOINTS. Kept here so the node card is one self-contained change.
NODE_DRIVER_ENDPOINTS = frozenset({"node.node_card"})


def _refresh() -> bool:
    return request.args.get("refresh") == "1"


@node_bp.route("/operations/node")
def node_page():
    report = node_health.collect(refresh=_refresh())
    return render_template("node_health.html", report=report,
                           card=node_health.driver_card(report))


@node_bp.route("/api/node/health")
def node_health_json():
    return jsonify(node_health.collect(refresh=_refresh()))


@node_bp.route("/portal/node-card")
def node_card():
    return jsonify(node_health.driver_card(node_health.collect()))
