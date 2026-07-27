"""L2-COS (Dispatch) — cloned and repurposed from the cin_lite (SAM Sweeper) pipeline.

Per System Rule 15 (Reuse Before Create), this package reuses the cin_lite
architecture pattern (deterministic rule modules -> structured JSON ->
control-layer decision -> archive) rather than introducing a new design.
See l2_cos/models/ for the Pydantic entities that replace cin_lite's
dataclass-based contract/RuleResult shapes for this domain.
"""
