"""Operations Portal — stdlib-only HTML rendering.

No template engine, no JS framework: plain f-string HTML with `html.escape`
on every interpolated value, the same "keep it lightweight and auditable"
approach cin_lite/control.py takes for its plain-text control email, just
aimed at a browser instead of an inbox.
"""

from __future__ import annotations

import json
from html import escape as _e

from l2_cos.ui.cards import LoadCard
from l2_cos.ui.repository import LoadBundle
from l2_cos.ui.sandbox import SandboxEntry

_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
.badge {{ color: #0a7a2f; font-weight: bold; }}
.red {{ color: #b00020; }}
table {{ border-collapse: collapse; }}
td, th {{ padding: 0.4rem 0.8rem; text-align: left; }}
nav a {{ margin-right: 1rem; }}
</style></head><body>
<nav>
  <a href="/">Cards</a>
  <a href="/locations">Location Intelligence Library</a>
  <a href="/brokers">Broker Intelligence Library</a>
  <a href="/publisher">Publisher Alerts &amp; Sandbox Tracking</a>
</nav>
<h1>{title}</h1>
{body}
</body></html>"""


def _page(title: str, body: str) -> str:
    return _PAGE.format(title=_e(title), body=body)


def render_card(card: LoadCard) -> str:
    reasons = "".join(f"<li>{_e(r)}</li>" for r in card.red_flag_reasons)
    reasons_block = f'<ul class="red">{reasons}</ul>' if reasons else ""
    badge = f'<div class="badge">{_e(card.badge)}</div>' if card.badge else ""

    return f"""
<div class="card">
  <h3>{card.indicator} {_e(card.load_id)} — {_e(card.lane)}</h3>
  {badge}
  <p>Broker: {_e(card.broker_name)} | Equipment: {_e(card.equipment_type or "unspecified")} |
     Stage: {_e(card.stage)} | Score: {card.score}</p>
  {reasons_block}
  <p>
    <a href="/loads/{_e(card.load_id)}/brief">Brief</a> |
    <a href="/loads/{_e(card.load_id)}/draft">Draft</a> |
    <a href="/loads/{_e(card.load_id)}/source">Source</a> |
    <a href="/loads/{_e(card.load_id)}/lifecycle">Lifecycle</a>
  </p>
</div>
"""


def render_dashboard(cards: list[LoadCard]) -> str:
    body = "".join(render_card(c) for c in cards) or "<p>No loads in the Archive yet.</p>"
    return _page("L2-COS Operations Portal — Cards", body)


def render_brief(bundle: LoadBundle, card: LoadCard) -> str:
    """Brief: quick decision support — the headline facts, no per-module detail."""
    pickup = bundle.facility_pickup.name if bundle.facility_pickup else bundle.raw_load.get("pickup_facility_id")
    delivery = (
        bundle.facility_delivery.name if bundle.facility_delivery else bundle.raw_load.get("delivery_facility_id")
    )
    body = f"""
{render_card(card)}
<h2>Brief</h2>
<ul>
  <li>Intelligence score: {bundle.overall_score}</li>
  <li>Pickup: {_e(str(pickup))}</li>
  <li>Delivery: {_e(str(delivery))}</li>
  <li>Rate/mile: {_e(str(bundle.raw_load.get("rate_per_mile")))}</li>
  <li>Deadhead miles: {_e(str(bundle.raw_load.get("deadhead_miles")))}</li>
</ul>
"""
    return _page(f"Brief — {bundle.load_id}", body)


def render_draft(bundle: LoadBundle, card: LoadCard) -> str:
    """Draft: deeper analysis — every rule module's score/flags and the full lifecycle history."""
    modules = "".join(
        f"<li>{_e(name)}: score {r['score']}, flags: {_e(', '.join(r['flags']) or 'none')}</li>"
        for name, r in bundle.intelligence.items()
    )
    history = bundle.load.model_dump()["history"]
    history_items = "".join(
        f"<li>{_e(ev['stage'])} at {_e(str(ev['at']))} by {_e(ev['actor'])}</li>" for ev in history
    )
    body = f"""
{render_card(card)}
<h2>Draft — deeper analysis</h2>
<h3>Rule modules</h3>
<ul>{modules}</ul>
<h3>Lifecycle history</h3>
<ul>{history_items or "<li>none yet</li>"}</ul>
"""
    return _page(f"Draft — {bundle.load_id}", body)


def render_source(bundle: LoadBundle) -> str:
    """Source: the raw acquired load record — the underlying system of record."""
    body = f"<pre>{_e(json.dumps(bundle.raw_load, indent=2))}</pre>"
    return _page(f"Source — {bundle.load_id}", body)


def render_lifecycle(bundle: LoadBundle, actions: dict[str, str]) -> str:
    options = "".join(
        f'<li><form method="post" action="/loads/{_e(bundle.load_id)}/advance">'
        f'<input type="hidden" name="action" value="{_e(key)}">'
        f'<button type="submit">{_e(label)}</button></form></li>'
        for key, label in actions.items()
    )
    body = f"<p>Current stage: <strong>{_e(bundle.load.stage.value)}</strong></p><ul>{options}</ul>"
    return _page(f"Lifecycle — {bundle.load_id}", body)


def render_locations(facilities: dict) -> str:
    rows = "".join(
        f"<tr><td>{_e(f.facility_id)}</td><td>{_e(f.name)}</td><td>{_e(f.address)}</td>"
        f"<td>{_e('; '.join(f.historical_problems) or 'none')}</td>"
        f"<td>{_e(f.security_requirements or 'none')}</td></tr>"
        for f in facilities.values()
    )
    body = (
        "<table border=\"1\"><tr><th>ID</th><th>Name</th><th>Address</th>"
        f"<th>Historical problems</th><th>Security requirements</th></tr>{rows}</table>"
    )
    return _page("Location Intelligence Library", body)


def render_brokers(brokers: dict) -> str:
    rows = "".join(
        f"<tr><td>{_e(b.broker_id)}</td><td>{_e(b.company_name)}</td>"
        f"<td>{_e(b.contact_email or 'none')}</td><td>{_e(b.payment_terms or 'none')}</td>"
        f"<td>{_e(', '.join(f'{lane}: {rpm}' for lane, rpm in b.historical_rates.items()) or 'none')}</td></tr>"
        for b in brokers.values()
    )
    body = (
        "<table border=\"1\"><tr><th>ID</th><th>Company</th><th>Contact</th>"
        f"<th>Payment terms</th><th>Historical RPM</th></tr>{rows}</table>"
    )
    return _page("Broker Intelligence Library", body)


def render_publisher_alerts(entries: list[tuple[SandboxEntry, str]]) -> str:
    from l2_cos.ui.sandbox import SANDBOX_HOLD_HOURS

    rows = "".join(
        f"<tr><td>{_e(entry.load_id)}</td><td>{_e('sent' if entry.sent else 'declined')}</td>"
        f"<td>{_e(entry.entered_at.isoformat())}</td><td>{_e(entry_status)}</td></tr>"
        for entry, entry_status in entries
    )
    body = (
        f"<p>Sandbox hold: {SANDBOX_HOLD_HOURS} hours from publisher evaluation.</p>"
        "<table border=\"1\"><tr><th>Load</th><th>Outcome</th><th>Entered sandbox</th>"
        f"<th>Status</th></tr>{rows}</table>"
    )
    return _page("Publisher Alerts &amp; Sandbox Tracking", body)
