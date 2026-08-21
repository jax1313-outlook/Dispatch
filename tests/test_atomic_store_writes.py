"""Tests for M-A: the JSON stores write atomically.

Every store in portal/models (and dispatch/email_helper.py, its standalone
copy) does read-modify-write: _load() reads the whole file, the caller mutates
it, _save() writes it back. A plain path.write_text() truncates first and then
writes, so a power cut, an OOM kill, or a full disk mid-write left a
half-written JSON file -- and every later _load() raised JSONDecodeError. The
failure mode is not "one lost record"; it is "this store is now unreadable".

M-A (DISPATCH_BUILD_MATRIX_v1) replaces that with write-temp-then-os.replace(),
which is atomic on POSIX and Windows: a reader sees the complete old file or
the complete new one.

Explicitly NOT claimed, and tested as not claimed: concurrency safety. Two
writers doing read-modify-write still lose one update. Locking is a separate,
larger question and M-A does not attempt it.
"""

from __future__ import annotations

import json
import os

import pytest

from portal.models import atomic_write_json


@pytest.fixture(autouse=True)
def _portal_data(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path / "PortalData"))
    monkeypatch.setenv("DISPATCH_MEMORY_ROOT", str(tmp_path / "Memory"))
    monkeypatch.setenv("DISPATCH_ARCHIVE_ROOT", str(tmp_path / "ArchiveRoot"))
    yield


# ── the helper itself ──────────────────────────────────────────────────


class TestAtomicWriteJson:
    def test_writes_readable_json(self, tmp_path):
        target = tmp_path / "store.json"
        atomic_write_json(target, [{"id": "A", "value": 1}])
        assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "A", "value": 1}]

    def test_creates_missing_parent_directories(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "store.json"
        atomic_write_json(target, {"ok": True})
        assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}

    def test_overwrites_existing_content_completely(self, tmp_path):
        target = tmp_path / "store.json"
        atomic_write_json(target, [{"id": "long"}, {"id": "second"}, {"id": "third"}])
        atomic_write_json(target, [{"id": "x"}])
        assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "x"}]

    def test_leaves_no_temp_files_behind_on_success(self, tmp_path):
        target = tmp_path / "store.json"
        atomic_write_json(target, {"a": 1})
        assert [p.name for p in tmp_path.iterdir()] == ["store.json"]

    def test_preserves_unicode(self, tmp_path):
        target = tmp_path / "store.json"
        atomic_write_json(target, {"note": "Jacksonville → Savannah — café"})
        assert json.loads(target.read_text(encoding="utf-8"))["note"] == (
            "Jacksonville → Savannah — café"
        )


# ── the property that matters: a failed write loses nothing ────────────


class TestCrashSafety:
    def test_previous_content_survives_a_failed_write(self, tmp_path, monkeypatch):
        """The whole point of M-A.

        Under the old write_text() this test's file would be truncated or
        half-written; the original record set would be unrecoverable.
        """
        target = tmp_path / "store.json"
        original = [{"id": "KEEP-ME", "payload": "x" * 5000}]
        atomic_write_json(target, original)

        def _die(*a, **kw):
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", _die)
        with pytest.raises(OSError, match="disk full"):
            atomic_write_json(target, [{"id": "NEVER-LANDS"}])

        assert json.loads(target.read_text(encoding="utf-8")) == original

    def test_no_temp_file_is_left_behind_after_a_failure(self, tmp_path, monkeypatch):
        target = tmp_path / "store.json"
        atomic_write_json(target, [{"id": "A"}])

        monkeypatch.setattr(os, "replace", lambda *a, **kw: (_ for _ in ()).throw(OSError("boom")))
        with pytest.raises(OSError):
            atomic_write_json(target, [{"id": "B"}])

        assert sorted(p.name for p in tmp_path.iterdir()) == ["store.json"]

    def test_unserializable_data_does_not_destroy_the_store(self, tmp_path):
        """json.dump raises partway through -- the original must still be there."""
        target = tmp_path / "store.json"
        atomic_write_json(target, [{"id": "ORIGINAL"}])

        class NotSerializable:
            pass

        with pytest.raises(TypeError):
            atomic_write_json(target, [{"id": "A"}, {"bad": NotSerializable()}])

        assert json.loads(target.read_text(encoding="utf-8")) == [{"id": "ORIGINAL"}]
        assert sorted(p.name for p in tmp_path.iterdir()) == ["store.json"]


# ── every store actually uses it ───────────────────────────────────────


class TestNoStoreStillTruncates:
    def test_no_portal_store_uses_bare_write_text(self):
        """Structural guard: a new store added later must not reintroduce the
        truncating pattern."""
        import pathlib

        offenders = []
        for path in pathlib.Path("portal/models").glob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "path.write_text(json.dumps(" in source:
                offenders.append(path.name)
        assert offenders == []

    def test_dispatch_email_helper_does_not_use_bare_write_text(self):
        import pathlib

        source = pathlib.Path("dispatch/email_helper.py").read_text(encoding="utf-8")
        assert "path.write_text(json.dumps(" not in source
        assert "os.replace(" in source

    def test_dispatch_does_not_import_portal_for_this(self):
        """dispatch/email_helper.py is a deliberate standalone copy under THE
        MIKE RULE; M-A must not have quietly coupled it to portal/."""
        import pathlib

        source = pathlib.Path("dispatch/email_helper.py").read_text(encoding="utf-8")
        assert "from portal" not in source
        assert "import portal" not in source


# ── round-trip through the real stores ─────────────────────────────────


class TestRealStoresRoundTrip:
    def test_conflict_store(self):
        from portal.models import conflict

        notice = conflict.create_notice(
            "missing_rate", "warning", "SBX-1", "No rate", "Ask the broker",
        )
        assert conflict.get_all() == [notice]

    def test_publisher_store(self):
        from portal.models import publisher

        action = publisher.create_action(
            action_type="Broker Packet Required",
            sandbox_id="SBX-1",
            trigger_reason="test",
            available_data=[],
            missing_data=[],
        )
        assert publisher.get_queue() == [action]

    def test_completion_packet_store(self):
        from portal.models import completion_packet

        packet = completion_packet.create_packet("LOAD-1", {"available": [], "missing": []})
        assert completion_packet.get_packet("LOAD-1") == packet

    def test_sandbox_store(self):
        from portal.models import sandbox

        entry = sandbox.create_entry(
            source_type="dispatch",
            source_id="X1",
            title="JAX -> SAV",
            card_data={},
        )
        assert sandbox.get(entry["id"]) == entry

    def test_dispatch_email_helper_store(self):
        from dispatch import email_helper

        pkg = email_helper.create_draft(
            "LOAD-1",
            {"load_id": "LOAD-1", "customer": "Acme", "broker_shipper": "B"},
        )
        assert email_helper.get_package("LOAD-1") == pkg

    def test_stores_survive_a_rewrite_cycle(self):
        """Read-modify-write repeatedly; the store must stay parseable."""
        from portal.models import conflict

        for i in range(10):
            conflict.create_notice(
                "missing_rate", "warning", f"SBX-{i}", f"No rate {i}", "Ask",
            )
        assert len(conflict.get_all()) == 10
        assert len(conflict.get_unresolved()) == 10


# ── the limit is stated, not hidden ────────────────────────────────────


class TestConcurrencyIsNotClaimed:
    def test_last_writer_wins_on_a_lost_update(self, tmp_path):
        """Documents the known limit rather than implying safety M-A does not
        provide. Two read-modify-write cycles interleaved: one update is lost.
        If this ever starts failing, locking was added and the docstrings in
        atomic_write_json / dispatch.email_helper._save must be corrected.
        """
        target = tmp_path / "store.json"
        atomic_write_json(target, [{"id": "base"}])

        reader_a = json.loads(target.read_text(encoding="utf-8"))
        reader_b = json.loads(target.read_text(encoding="utf-8"))

        atomic_write_json(target, reader_a + [{"id": "from-a"}])
        atomic_write_json(target, reader_b + [{"id": "from-b"}])

        final = json.loads(target.read_text(encoding="utf-8"))
        assert final == [{"id": "base"}, {"id": "from-b"}]
        assert {"id": "from-a"} not in final
