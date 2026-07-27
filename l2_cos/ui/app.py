"""L2-COS Operations Portal — FastAPI/HTML.

Card -> Brief/Draft -> Source workflow hierarchy: the dashboard's Cards
list every load currently in the Archive (the system of record); clicking
through opens a Brief (quick decision support), a Draft (deeper per-module
analysis), the raw Source JSON, or the Lifecycle controls for manual stage
progression. Built on FastAPI/HTML rather than a heavier UI framework per
CLAUDE.md's "must remain lightweight" constraint — all business logic lives
in plain, unit-tested functions in l2_cos/ui/*.py; this module only wires
routes to them.

Run it:
    pip install -r l2_cos/requirements.txt
    uvicorn l2_cos.ui.app:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

from l2_cos import archive, control, intelligence_store
from l2_cos.ui import cards as cards_module
from l2_cos.ui import render, repository, sandbox

app = FastAPI(title="L2-COS Operations Portal")


def _bundle_or_404(load_id: str) -> repository.LoadBundle:
    bundle = repository.get_load_bundle(load_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"unknown load {load_id!r}")
    return bundle


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    bundles = repository.list_load_bundles()
    return render.render_dashboard([cards_module.build_card(b) for b in bundles])


@app.get("/loads/{load_id}/brief", response_class=HTMLResponse)
def brief(load_id: str) -> str:
    bundle = _bundle_or_404(load_id)
    return render.render_brief(bundle, cards_module.build_card(bundle))


@app.get("/loads/{load_id}/draft", response_class=HTMLResponse)
def draft(load_id: str) -> str:
    bundle = _bundle_or_404(load_id)
    return render.render_draft(bundle, cards_module.build_card(bundle))


@app.get("/loads/{load_id}/source", response_class=HTMLResponse)
def source(load_id: str) -> str:
    bundle = _bundle_or_404(load_id)
    return render.render_source(bundle)


@app.get("/loads/{load_id}/lifecycle", response_class=HTMLResponse)
def lifecycle(load_id: str) -> str:
    bundle = _bundle_or_404(load_id)
    actions = control.available_actions(bundle.load)
    return render.render_lifecycle(bundle, actions)


@app.post("/loads/{load_id}/advance")
def advance(load_id: str, action: str = Form(...)) -> dict:
    bundle = _bundle_or_404(load_id)
    try:
        target = control.resolve(action, bundle.load)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if target is not None:
        bundle.load.advance(target, actor="operations-portal")
    archive.record_dispatch(bundle.load)
    return {"load_id": load_id, "stage": bundle.load.stage.value}


@app.get("/locations", response_class=HTMLResponse)
def locations() -> str:
    return render.render_locations(intelligence_store.load_facilities())


@app.get("/brokers", response_class=HTMLResponse)
def brokers() -> str:
    return render.render_brokers(intelligence_store.load_brokers())


@app.get("/publisher", response_class=HTMLResponse)
def publisher_alerts() -> str:
    entries = []
    for result in repository.list_publisher_results():
        entry = sandbox.build_entry(result)
        if entry is not None:
            entries.append((entry, sandbox.status(entry)))
    return render.render_publisher_alerts(entries)
