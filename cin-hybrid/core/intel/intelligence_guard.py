from core.intel.intelligence_owner import IntelligenceOwner


def enforce_intelligence_owner(orchestrator):
    if not isinstance(orchestrator, IntelligenceOwner):
        raise RuntimeError("Intelligence ownership violation")
