"""BLOCK-04 — more than one Dispatch on a machine.

On 2026-08-25 three copies existed on the operator's laptop. The one holding
port 8080 all day was an incomplete extraction missing `dispatch/connectors`,
and every page behind the sign-in returned HTTP 500 for seven hours. Four
theories were built and discarded; none was "you are running a different copy
from the one you are looking at."

These tests pin what the check finds, and — more importantly — the three things
it must never do: block a start, take forever, or touch anything on disk.
"""

from __future__ import annotations

import time

import pytest

from dispatch_launcher import copies


def make_install(root, name, *, launch_file=False, packages=True, partial=False):
    """A directory that looks like a Dispatch install to the check."""
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    if launch_file:
        (path / "DISPATCH_START_HERE.cmd").write_text("@echo off\n", encoding="utf-8")
    if packages:
        (path / "dispatch").mkdir(exist_ok=True)
        if not partial:
            (path / "portal").mkdir(exist_ok=True)
    return path


class TestWhatCountsAsAnInstall:
    def test_the_launch_file_alone_is_enough(self, tmp_path):
        p = make_install(tmp_path, "a", launch_file=True, packages=False)
        assert copies.looks_like_dispatch(p)

    def test_both_packages_are_enough(self, tmp_path):
        p = make_install(tmp_path, "b")
        assert copies.looks_like_dispatch(p)

    def test_one_package_alone_is_not(self, tmp_path):
        p = make_install(tmp_path, "c", partial=True)
        assert not copies.looks_like_dispatch(p)

    def test_an_ordinary_folder_is_not(self, tmp_path):
        (tmp_path / "photos").mkdir()
        assert not copies.looks_like_dispatch(tmp_path / "photos")

    def test_a_missing_path_is_not_a_finding(self, tmp_path):
        assert not copies.looks_like_dispatch(tmp_path / "nope")

    def test_a_file_is_not_an_install(self, tmp_path):
        f = tmp_path / "dispatch.txt"
        f.write_text("x", encoding="utf-8")
        assert not copies.looks_like_dispatch(f)


class TestFinding:
    def test_a_sibling_copy_is_found(self, tmp_path):
        running = make_install(tmp_path, "running")
        other = make_install(tmp_path, "other")
        found = copies.find_copies(running)
        assert other.resolve() in [p.resolve() for p in found]

    def test_the_running_copy_is_never_listed_as_another(self, tmp_path):
        running = make_install(tmp_path, "running")
        found = copies.find_copies(running)
        assert running.resolve() not in [p.resolve() for p in found]

    def test_a_nested_copy_is_found(self, tmp_path):
        """The operator's copies were nested: C:\\Dispatch\\Dispatch\\Dispatch-main."""
        running = make_install(tmp_path, "running")
        nested = make_install(running, "Dispatch-main")
        found = [p.resolve() for p in copies.find_copies(running)]
        assert nested.resolve() in found

    def test_an_incomplete_extraction_is_still_found(self, tmp_path):
        """The whole point. The broken copy was missing files and still started."""
        running = make_install(tmp_path, "running")
        broken = make_install(tmp_path, "broken", launch_file=True, packages=False)
        found = [p.resolve() for p in copies.find_copies(running)]
        assert broken.resolve() in found


class TestItNeverHarms:
    def test_it_changes_nothing_on_disk(self, tmp_path):
        running = make_install(tmp_path, "running")
        make_install(tmp_path, "other")
        before = sorted(str(p) for p in tmp_path.rglob("*"))
        copies.find_copies(running)
        assert sorted(str(p) for p in tmp_path.rglob("*")) == before

    def test_an_unreadable_root_does_not_raise(self, tmp_path, monkeypatch):
        def explode(_):
            raise OSError("denied")

        monkeypatch.setattr(copies.os, "scandir", explode)
        assert copies.find_copies(tmp_path) == []

    def test_it_is_fast(self, tmp_path):
        """A startup check the operator dreads is a check they will disable."""
        running = make_install(tmp_path, "running")
        for i in range(20):
            make_install(tmp_path, f"copy{i}")
        start = time.time()
        copies.find_copies(running)
        assert time.time() - start < 5.0


class TestTheMessage:
    def test_one_copy_says_so_plainly(self, tmp_path):
        running = make_install(tmp_path, "running")
        assert "One copy of Dispatch" in copies.describe(running, others=[])

    def test_it_names_the_running_copy_first(self, tmp_path):
        """The question that went unanswered for seven hours."""
        running = make_install(tmp_path, "running")
        other = make_install(tmp_path, "other")
        text = copies.describe(running, others=[other])
        assert "RUNNING NOW" in text
        assert text.index(str(running)) < text.index(str(other))

    def test_it_warns_that_each_copy_has_its_own_database(self, tmp_path):
        running = make_install(tmp_path, "running")
        text = copies.describe(running, others=[make_install(tmp_path, "other")])
        assert "own database" in text

    def test_it_does_not_tell_the_operator_to_delete_anything(self, tmp_path):
        """Copies hold data. Which one to keep is the operator's decision."""
        running = make_install(tmp_path, "running")
        text = copies.describe(running, others=[make_install(tmp_path, "other")])
        assert "Do not delete anything until you are sure" in text

    def test_it_counts_every_folder_including_the_running_one(self, tmp_path):
        running = make_install(tmp_path, "running")
        others = [make_install(tmp_path, "a"), make_install(tmp_path, "b")]
        assert copies.describe(running, others=others).startswith("3 folders")


class TestItNeverBlocksAStart:
    def test_the_step_is_not_fatal_when_copies_are_found(self, tmp_path, monkeypatch):
        from dispatch_launcher import first_run as fr

        monkeypatch.setattr(copies, "find_copies",
                            lambda *a, **k: [tmp_path / "other"])
        report = fr.FirstRunReport()
        fr.check_one_copy(report)
        assert report.steps[-1].ok is True
        assert report.blocker in (None, "")

    def test_a_check_that_explodes_does_not_stop_the_start(self, monkeypatch):
        from dispatch_launcher import first_run as fr

        def explode(*a, **k):
            raise RuntimeError("scan failed")

        monkeypatch.setattr(copies, "find_copies", explode)
        report = fr.FirstRunReport()
        fr.check_one_copy(report)
        assert report.steps[-1].ok is True

    def test_a_failed_check_does_not_claim_there_is_one_copy(self, monkeypatch):
        """Silence is not proof. An unknown is reported as an unknown."""
        from dispatch_launcher import first_run as fr

        def explode(*a, **k):
            raise RuntimeError("scan failed")

        monkeypatch.setattr(copies, "find_copies", explode)
        report = fr.FirstRunReport()
        fr.check_one_copy(report)
        assert "not a statement that there is only one" in report.steps[-1].detail.lower()
