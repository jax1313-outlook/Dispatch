"""Acquisition Layer.

Fetches contracts from the designated source. The live source is the SAM.gov
Opportunities API (https://open.gsa.gov/api/get-opportunities-public-api/); when
no API key is configured it falls back to local sample data so the pipeline still
runs offline.

Each opportunity is mapped into the pipeline's contract shape so it flows through
the deterministic rule modules unchanged:
    title, agency, solicitation_number, naics_text, description,
    estimated_value, response_date, notes

Configuration (environment):
    CIN_LITE_SAM_API_KEY          api.data.gov key (its presence enables live SAM.gov)
    CIN_LITE_SAM_LIMIT            max opportunities to pull (default 10)
    CIN_LITE_SAM_POSTED_FROM      MM/DD/YYYY (default: 7 days ago)
    CIN_LITE_SAM_POSTED_TO        MM/DD/YYYY (default: today)
    CIN_LITE_SAM_NAICS            optional NAICS code filter (ncode)
    CIN_LITE_SAM_PTYPE            optional procurement type filter (e.g. "o,k,p")
    CIN_LITE_SAM_FETCH_DESCRIPTION  "1"/"0", default "1" (fetch full description text)
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"
SAM_SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"
_DESCRIPTION_CAP = 4000


def acquire() -> list[dict]:
    """Return raw contract dicts from the configured source (SAM.gov or local)."""
    api_key = os.environ.get("CIN_LITE_SAM_API_KEY")
    if api_key:
        print("Acquisition: SAM.gov Opportunities API")
        return _acquire_sam(api_key)
    print("Acquisition: local sample_data (set CIN_LITE_SAM_API_KEY for live SAM.gov)")
    return _acquire_local()


# --------------------------------------------------------------------------- local

def _acquire_local() -> list[dict]:
    contracts: list[dict] = []
    for path in sorted(SAMPLE_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("_source_file", path.name)
        contracts.append(data)
    return contracts


# --------------------------------------------------------------------------- SAM.gov

def _http_get(url: str, params: dict) -> bytes:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    req = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def _acquire_sam(api_key: str) -> list[dict]:
    today = datetime.now(timezone.utc)
    page_size = int(os.environ.get("CIN_LITE_SAM_LIMIT", "10"))
    fetch_desc = os.environ.get("CIN_LITE_SAM_FETCH_DESCRIPTION", "1") == "1"

    base_params = {
        "api_key": api_key,
        "limit": str(page_size),
        "postedFrom": os.environ.get(
            "CIN_LITE_SAM_POSTED_FROM", (today - timedelta(days=7)).strftime("%m/%d/%Y")
        ),
        "postedTo": os.environ.get("CIN_LITE_SAM_POSTED_TO", today.strftime("%m/%d/%Y")),
        "ncode": os.environ.get("CIN_LITE_SAM_NAICS"),
        "ptype": os.environ.get("CIN_LITE_SAM_PTYPE"),
    }

    all_opportunities: list[dict] = []
    offset = 0
    _MAX_PAGES = 10

    for _ in range(_MAX_PAGES):
        params = {**base_params, "offset": str(offset)}
        try:
            body = _http_get(SAM_SEARCH_URL, params)
            data = json.loads(body)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            print(f"cin_lite: SAM.gov request failed (HTTP {exc.code}): {detail}", file=sys.stderr)
            if not all_opportunities:
                print("cin_lite: falling back to local sample_data.", file=sys.stderr)
                return _acquire_local()
            break
        except Exception as exc:
            print(f"cin_lite: SAM.gov acquisition failed ({exc})", file=sys.stderr)
            if not all_opportunities:
                print("cin_lite: falling back to local sample_data.", file=sys.stderr)
                return _acquire_local()
            break

        page = data.get("opportunitiesData", [])
        all_opportunities.extend(page)
        total = data.get("totalRecords", len(page))

        if len(all_opportunities) >= total or len(page) < page_size:
            break
        offset += page_size

    return [_map_opportunity(opp, api_key, fetch_desc) for opp in all_opportunities]


def _naics_text(opp: dict) -> str:
    codes: list[str] = []
    if opp.get("naicsCode"):
        codes.append(str(opp["naicsCode"]))
    for code in opp.get("naicsCodes") or []:
        codes.append(str(code))
    # de-dup preserving order
    seen, ordered = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return "NAICS " + ", ".join(ordered) if ordered else ""


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _fetch_description(opp: dict, api_key: str) -> str:
    """Best-effort fetch of the full description text (a URL in the SAM record)."""
    url = opp.get("description")
    if not isinstance(url, str) or not url.startswith("http"):
        return _strip_html(url) if isinstance(url, str) else ""
    try:
        sep = "&" if "?" in url else "?"
        with urllib.request.urlopen(f"{url}{sep}api_key={api_key}", timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
        try:
            parsed = json.loads(raw)
            text = parsed.get("description", raw) if isinstance(parsed, dict) else raw
        except json.JSONDecodeError:
            text = raw
        return _strip_html(text)[:_DESCRIPTION_CAP]
    except Exception:
        return ""


def _award_amount(opp: dict):
    award = opp.get("award")
    if isinstance(award, dict):
        amount = award.get("amount")
        try:
            return float(amount) if amount is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _map_opportunity(opp: dict, api_key: str, fetch_desc: bool) -> dict:
    """Map one SAM.gov opportunity into the pipeline's contract shape."""
    notice_id = opp.get("noticeId", "")
    description = _fetch_description(opp, api_key) if fetch_desc else ""
    set_aside = opp.get("typeOfSetAsideDescription") or opp.get("typeOfSetAside") or ""

    return {
        "solicitation_number": opp.get("solicitationNumber") or notice_id,
        "title": opp.get("title"),
        "agency": opp.get("fullParentPathName") or opp.get("department"),
        "naics_text": _naics_text(opp),
        "description": description,
        "estimated_value": _award_amount(opp),
        "response_date": opp.get("responseDeadLine"),
        "notes": set_aside,
        "point_of_contact": opp.get("pointOfContact"),
        "award": opp.get("award"),
        "_source_file": f"sam.gov/{notice_id}" if notice_id else "sam.gov",
        "_sam_notice_id": notice_id,
        "_sam_ui_link": opp.get("uiLink"),
    }
