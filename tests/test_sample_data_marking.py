"""BLOCK-01 — sample data must never read as real freight.

`/home` rendered four freight cards carrying a lane, a rate and a broker while
ACTIVE LOADS read 0. They were bundled samples, and nothing on any surface said
so. `CLAUDE.md` §6: never represent sample data as live data.

These tests pin three things: records are marked at the source, a marked record
is badged wherever it renders, and the clear removes samples without ever being
able to take real freight with it.
"""

from __future__ import annotations

import json

import pytest

from dispatch import acquisition
from portal.models import sandbox


class TestMarkedAtTheSource:
    def test_bundled_samples_are_marked_simulated(self):
        loads = acquisition.acquire()
        assert loads, "the bundled sample directory should yield records"
        assert all(l["data_origin"] == "SIMULATED" for l in loads)

    def test_a_configured_directory_is_live(self, tmp_path, monkeypatch):
        (tmp_path / "load.json").write_text(
            json.dumps({"load_id": "L1", "origin": "A", "destination": "B"}),
            encoding="utf-8")
        monkeypatch.setenv("DISPATCH_LOAD_SOURCE", str(tmp_path))
        loads = acquisition.acquire()
        assert loads and all(l["data_origin"] == "LIVE" for l in loads)

    def test_the_origin_uses_the_repositorys_fixed_vocabulary(self):
        assert acquisition.ORIGIN_SIMULATED == "SIMULATED"
        assert acquisition.ORIGIN_LIVE == "LIVE"


class TestAnUnavailableSourceDoesNotFabricate:
    """The v1.0.1 defect: a failed connector returning samples as if live."""

    def test_api_failure_returns_samples_marked_simulated(self, monkeypatch):
        monkeypatch.setenv("DISPATCH_LOAD_API_URL", "http://127.0.0.1:1/never")
        loads = acquisition.acquire()
        assert loads, "the fallback should still return something to look at"
        assert all(l["data_origin"] == "SIMULATED" for l in loads), (
            "a source that was UNAVAILABLE must not yield records that read as LIVE"
        )

    def test_api_failure_says_unavailable_not_success(self, monkeypatch, capsys):
        monkeypatch.setenv("DISPATCH_LOAD_API_URL", "http://127.0.0.1:1/never")
        acquisition.acquire()
        assert "UNAVAILABLE" in capsys.readouterr().err


class TestSandboxCarriesTheMark:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        yield

    def test_an_entry_records_its_origin(self):
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="S1", title="Sample",
            card_data={}, data_origin="SIMULATED")
        assert entry["data_origin"] == "SIMULATED"

    def test_the_default_is_live_not_simulated(self):
        """A record whose origin nobody stated is not assumed to be a sample."""
        entry = sandbox.create_entry(
            source_type="dispatch", source_id="S2", title="Real", card_data={})
        assert entry["data_origin"] == "LIVE"

    def test_a_sample_cannot_be_laundered_into_a_live_record(self):
        """Re-ingesting the same id must not upgrade SIMULATED to LIVE."""
        sandbox.create_entry(source_type="dispatch", source_id="S3", title="Sample",
                             card_data={}, data_origin="SIMULATED")
        again = sandbox.create_entry(source_type="dispatch", source_id="S3",
                                     title="Sample", card_data={}, data_origin="LIVE")
        assert again["data_origin"] == "SIMULATED"


class TestTheClear:
    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
        yield

    def _two_of_each(self):
        sandbox.create_entry(source_type="dispatch", source_id="SIM1", title="s1",
                             card_data={}, data_origin="SIMULATED")
        sandbox.create_entry(source_type="dispatch", source_id="SIM2", title="s2",
                             card_data={}, data_origin="SIMULATED")
        sandbox.create_entry(source_type="dispatch", source_id="REAL1", title="r1",
                             card_data={}, data_origin="LIVE")

    def test_it_removes_the_samples(self):
        self._two_of_each()
        removed = sandbox.clear_simulated()
        assert len(removed) == 2
        assert sandbox.simulated_count() == 0

    def test_it_never_removes_a_live_record(self):
        """The rule that makes the button safe to press."""
        self._two_of_each()
        sandbox.clear_simulated()
        remaining = sandbox.get_all()
        assert len(remaining) == 1
        assert list(remaining.values())[0]["data_origin"] == "LIVE"

    def test_it_leaves_unmarked_records_alone(self):
        """Records predating the marking are not proven to be samples."""
        entry = sandbox.create_entry(source_type="dispatch", source_id="OLD",
                                     title="old", card_data={})
        del entry["data_origin"]
        data = sandbox._load()
        data[entry["id"]] = entry
        sandbox._save(data)

        sandbox.clear_simulated()
        assert entry["id"] in sandbox.get_all()

    def test_clearing_twice_is_harmless(self):
        self._two_of_each()
        sandbox.clear_simulated()
        assert sandbox.clear_simulated() == []

    def test_the_count_reports_what_is_there(self):
        self._two_of_each()
        assert sandbox.simulated_count() == 2
