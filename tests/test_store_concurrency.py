"""The JSON stores no longer lose a concurrent update.

`atomic_write_json` has always guaranteed that a reader never sees half a file.
It could not guarantee that two writers do not overwrite each other, because
the damage is done before either write begins: both read, both mutate their own
copy, and the second `os.replace` wins.

Measured on this repository before the fix, with twelve processes each queuing
one publisher action: **the store held two.** Ten records gone, nothing corrupt,
nothing anywhere saying so. That is the same shape as the PIN-lockout defect
fixed earlier, minus the security consequence -- and Dispatch runs the portal
and the launcher as two processes against one folder, so it is reachable rather
than theoretical.

After: twelve of twelve, repeatably.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import threading
from pathlib import Path

import pytest

from portal.models import atomic_write_json, guarded, lock_path_for, store_lock


# ── the lock itself ──────────────────────────────────────────────────────


class TestTheLock:
    def test_it_lives_beside_the_store_not_in_it(self, tmp_path):
        """A separate file, for two reasons: the store is replaced wholesale by
        os.replace on every write so a lock on its inode stops describing the
        file that is there, and a store that does not exist yet still needs a
        lock -- the first two writers race hardest."""
        store = tmp_path / "things.json"
        lock = lock_path_for(store)
        assert lock != store
        assert lock.parent == store.parent
        assert "things.json" in lock.name

    def test_it_can_be_taken_before_the_store_exists(self, tmp_path):
        store = tmp_path / "not-yet" / "things.json"
        with store_lock(store):
            pass
        assert not store.exists()

    def test_it_is_exclusive_between_threads(self, tmp_path):
        store = tmp_path / "things.json"
        order: list[str] = []
        first_inside = threading.Event()
        release = threading.Event()

        def hold():
            with store_lock(store):
                order.append("A-in")
                first_inside.set()
                release.wait(timeout=5)
                order.append("A-out")

        def contend():
            first_inside.wait(timeout=5)
            with store_lock(store):
                order.append("B-in")

        a = threading.Thread(target=hold)
        b = threading.Thread(target=contend)
        a.start()
        b.start()
        first_inside.wait(timeout=5)
        release.set()
        a.join(timeout=10)
        b.join(timeout=10)

        assert order == ["A-in", "A-out", "B-in"], order

    def test_it_is_released_even_when_the_body_raises(self, tmp_path):
        store = tmp_path / "things.json"
        with pytest.raises(RuntimeError):
            with store_lock(store):
                raise RuntimeError("boom")
        # If the lock leaked, this would block forever rather than return.
        with store_lock(store):
            pass


# ── the decorator ────────────────────────────────────────────────────────


class TestTheGuard:
    def test_it_resolves_the_path_at_call_time(self, tmp_path, monkeypatch):
        """Every store reads its path from PORTAL_DATA_DIR, and the tests move
        it. Resolving at import time would lock the wrong folder for the whole
        run."""
        seen: list[Path] = []

        def where():
            return Path(os.environ["A_STORE"])

        @guarded(where)
        def touch():
            seen.append(where())

        monkeypatch.setenv("A_STORE", str(tmp_path / "one.json"))
        touch()
        monkeypatch.setenv("A_STORE", str(tmp_path / "two.json"))
        touch()
        assert seen[0] != seen[1]

    def test_a_guarded_call_inside_a_guarded_call_does_not_deadlock(self, tmp_path):
        """An operation composed of other operations on the same store is
        ordinary. Without reentrancy it would hang forever, which is a worse
        failure than the one being fixed."""
        store = tmp_path / "things.json"
        reached = []

        @guarded(lambda: store)
        def inner():
            reached.append("inner")

        @guarded(lambda: store)
        def outer():
            reached.append("outer")
            inner()

        outer()
        assert reached == ["outer", "inner"]

    def test_it_returns_what_the_function_returns(self, tmp_path):
        @guarded(lambda: tmp_path / "s.json")
        def answer():
            return 42

        assert answer() == 42

    def test_it_keeps_the_function_identity(self, tmp_path):
        @guarded(lambda: tmp_path / "s.json")
        def named(a, b=1):
            """Docstring survives."""
            return a + b

        assert named.__name__ == "named"
        assert "Docstring survives" in named.__doc__
        assert named(1, b=2) == 3

    def test_the_lock_is_dropped_when_the_body_raises(self, tmp_path):
        store = tmp_path / "s.json"

        @guarded(lambda: store)
        def explode():
            raise ValueError("no")

        with pytest.raises(ValueError):
            explode()

        @guarded(lambda: store)
        def after():
            return "reached"

        assert after() == "reached"


# ── the defect, end to end ───────────────────────────────────────────────


def _queue_one(args):
    """Runs in a separate *process*: this is a cross-process race, not a
    threading one, because Dispatch runs the portal and the launcher apart."""
    repo, data_dir, n = args
    sys.path.insert(0, repo)
    os.environ["PORTAL_DATA_DIR"] = data_dir
    os.environ.setdefault("DISPATCH_MODE", "development")
    from portal.models import publisher

    publisher.create_action(
        action_type="govcon_draft", sandbox_id=f"SBX-{n}", trigger_reason="race"
    )


@pytest.mark.parametrize("writers", [12])
def test_twelve_processes_queueing_at_once_all_land(tmp_path, monkeypatch, writers):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    from portal.models import publisher

    repo = str(Path(__file__).resolve().parent.parent)
    with mp.Pool(writers) as pool:
        pool.map(_queue_one, [(repo, str(tmp_path), i) for i in range(writers)])

    queue = publisher.get_queue()
    assert len(queue) == writers, (
        f"{writers} processes each queued one action and the store holds "
        f"{len(queue)}. Before the store lock this reliably held 2."
    )
    assert len({entry["sandbox_id"] for entry in queue}) == writers


def test_threads_mutating_one_store_all_land(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    from portal.models import publisher

    barrier = threading.Barrier(8)
    errors: list[BaseException] = []

    def queue(n):
        try:
            barrier.wait(timeout=5)
            publisher.create_action(
                action_type="govcon_draft", sandbox_id=f"T-{n}", trigger_reason="race"
            )
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            errors.append(exc)

    threads = [threading.Thread(target=queue, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    assert errors == [], errors
    assert len(publisher.get_queue()) == 8


def test_the_write_is_still_atomic(tmp_path):
    """The guard is added to what atomic_write_json already did, not instead of
    it. A reader must still never see half a file."""
    store = tmp_path / "s.json"
    atomic_write_json(store, {"a": 1})
    assert json.loads(store.read_text()) == {"a": 1}
    leftovers = [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == [], leftovers
