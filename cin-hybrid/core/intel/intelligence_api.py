from core.intel.intelligence_guard import enforce_intelligence_owner


def get_intelligence(orchestrator, vendor_id):
    """
    Enforce intelligence ownership and return unified CIN intelligence.
    """
    enforce_intelligence_owner(orchestrator)
    return orchestrator.run_intelligence(vendor_id)
