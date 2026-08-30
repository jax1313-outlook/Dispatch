"""SAM/freight Sandbox scoping for HOLD.

Dispatch's Sandbox is shared between freight loads and SAM/CIN-Lite
opportunities, distinguished by source_type. These tests prove that
freight-only operations (get_all_for_source, run_hold_sweep) can never
see or touch a SAM-sourced entry, even when it sits in the same store.

Ported from the Claude-3 First Live Load sandbox build
(DISPATCH_PROMOTION_PLAN_FIRST_LIVE_LOAD.md item 4); mirrors
dispatch_build/tests/test_sandbox_program_scoping.py there.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from portal.models import sandbox


@pytest.fixture(autouse=True)
def _sandbox_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "portal_data"))


def _make_freight_entry(source_id="LOAD-1", title="JAX -> ATL"):
    return sandbox.create_entry(
        source_type=sandbox.SANDBOX_SOURCE_FREIGHT,
        source_id=source_id,
        title=title,
        card_data={"origin": "Jacksonville, FL", "destination": "Atlanta, GA"},
    )


def _make_sam_entry(source_id="NOTICE-1", title="8(a) Set-Aside Opportunity"):
    return sandbox.create_entry(
        source_type="sam",
        source_id=source_id,
        title=title,
        card_data={"agency": "DEPT OF DEFENSE"},
    )


def test_new_entries_start_with_no_hold_clock():
    entry = _make_freight_entry()
    assert entry["hold_started_at"] is None
    assert entry["hold_expires_at"] is None


def test_get_all_for_source_defaults_to_freight_only():
    freight = _make_freight_entry()
    sam = _make_sam_entry()

    freight_only = sandbox.get_all_for_source()

    assert freight["id"] in freight_only
    assert sam["id"] not in freight_only


def test_get_all_for_source_can_scope_to_another_program_explicitly():
    freight = _make_freight_entry()
    sam = _make_sam_entry()

    sam_only = sandbox.get_all_for_source("sam")

    assert sam["id"] in sam_only
    assert freight["id"] not in sam_only


def test_start_hold_only_affects_the_named_entry():
    freight = _make_freight_entry()
    sam = _make_sam_entry()
    now = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)

    updated = sandbox.start_hold(freight["id"], now=now)

    assert updated["hold_started_at"] == "2026-08-17T08:00:00Z"
    assert updated["hold_expires_at"] == "2026-08-17T11:00:00Z"
    assert sandbox.get(sam["id"])["hold_expires_at"] is None


def test_hold_sweep_never_deletes_a_sam_entry_even_past_expiry():
    now = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)
    freight = _make_freight_entry()
    sam = _make_sam_entry()

    sandbox.start_hold(freight["id"], now=now)
    sandbox.start_hold(sam["id"], now=now)  # hypothetical: something started a SAM hold too

    later = now + timedelta(hours=3, minutes=1)
    deleted = sandbox.run_hold_sweep(now=later)  # default source_type -- freight only

    assert deleted == [freight["id"]]
    assert sandbox.get(freight["id"]) is None  # deleted, not archived
    assert sandbox.get(sam["id"]) is not None  # untouched despite also being expired


def test_hold_sweep_does_not_fire_before_expiry():
    now = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)
    freight = _make_freight_entry()
    sandbox.start_hold(freight["id"], now=now)

    two_hours_later = now + timedelta(hours=2)
    deleted = sandbox.run_hold_sweep(now=two_hours_later)

    assert deleted == []
    assert sandbox.get(freight["id"]) is not None


def test_hold_sweep_requires_explicit_opt_in_to_touch_another_program():
    now = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)
    sam = _make_sam_entry()
    sandbox.start_hold(sam["id"], now=now)

    later = now + timedelta(hours=3, minutes=1)
    deleted_default = sandbox.run_hold_sweep(now=later)
    assert deleted_default == []
    assert sandbox.get(sam["id"]) is not None

    deleted_explicit = sandbox.run_hold_sweep(source_type="sam", now=later)
    assert deleted_explicit == [sam["id"]]
    assert sandbox.get(sam["id"]) is None
