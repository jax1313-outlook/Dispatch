"""Tests for the summarization agent (deterministic fallback + Claude code path)."""

from __future__ import annotations

from cin_lite.agents import summarizer


def test_deterministic_summary_without_key(mapped_contract, intelligence, flags):
    summary = summarizer.summarize(mapped_contract, intelligence, flags)
    # Fallback format: "<title> (<agency>) — est. <value>, due <date>. N flag(s): ..."
    assert mapped_contract["title"] in summary
    assert "flag(s)" in summary
    assert str(len(flags)) in summary


def test_deterministic_summary_helper(mapped_contract):
    s = summarizer._deterministic_summary(mapped_contract, ["a", "b"])
    assert "2 flag(s): a, b" in s


def test_claude_success_path(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic("CANNED CLAUDE SUMMARY")
    assert summarizer.summarize(mapped_contract, intelligence, flags) == "CANNED CLAUDE SUMMARY"


def test_claude_failure_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic(RuntimeError("api down"))
    summary = summarizer.summarize(mapped_contract, intelligence, flags)
    assert mapped_contract["title"] in summary  # deterministic fallback used


def test_claude_empty_response_falls_back(mapped_contract, intelligence, flags, install_anthropic):
    install_anthropic("   ")  # whitespace-only -> treated as empty
    summary = summarizer.summarize(mapped_contract, intelligence, flags)
    assert mapped_contract["title"] in summary
