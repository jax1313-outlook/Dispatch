"""Unit tests for the Processing Layer — process() and all_flags()."""

from __future__ import annotations

from cin_lite import processing
from cin_lite.rules import ALL_RULES


class TestProcess:
    def test_returns_dict_with_all_modules(self, mapped_contract):
        result = processing.process(mapped_contract)
        assert isinstance(result, dict)
        for rule in ALL_RULES:
            assert rule.NAME in result

    def test_each_module_has_required_keys(self, mapped_contract):
        result = processing.process(mapped_contract)
        for name, module_output in result.items():
            assert module_output["module"] == name
            assert "version" in module_output
            assert "flags" in module_output
            assert "summary" in module_output
            assert "deterministic" in module_output

    def test_clean_contract_produces_fewer_flags(self, mapped_contract, clean_contract):
        rich = processing.process(mapped_contract)
        clean = processing.process(clean_contract)
        rich_flags = sum(len(r.get("flags", [])) for r in rich.values())
        clean_flags = sum(len(r.get("flags", [])) for r in clean.values())
        assert rich_flags > clean_flags


class TestAllFlags:
    def test_returns_list(self, intelligence):
        flags = processing.all_flags(intelligence)
        assert isinstance(flags, list)

    def test_aggregates_from_all_modules(self, intelligence):
        flags = processing.all_flags(intelligence)
        per_module = [r.get("flags", []) for r in intelligence.values()]
        expected_count = sum(len(f) for f in per_module)
        assert len(flags) == expected_count

    def test_empty_intelligence_returns_empty(self):
        assert processing.all_flags({}) == []

    def test_modules_without_flags(self):
        intelligence = {
            "fake_module": {"module": "fake", "version": "1.0", "summary": "x"},
        }
        assert processing.all_flags(intelligence) == []

    def test_rich_contract_has_flags(self, intelligence):
        flags = processing.all_flags(intelligence)
        assert len(flags) > 0
