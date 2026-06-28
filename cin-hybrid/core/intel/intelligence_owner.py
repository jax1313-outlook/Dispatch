from abc import ABC, abstractmethod


class IntelligenceOwner(ABC):
    """
    Explicit contract for CIN-Hybrid intelligence ownership.

    Only classes implementing this interface may:
    - run the full intelligence pipeline
    - aggregate engine outputs
    - build HybridSummary
    - build HybridIntelligence
    - produce scoring, rules, routing, assessment
    - return the unified CIN intelligence dict

    This prevents operational nodes (HybridOps), controllers
    (HybridLifecycleController), or workers (vendor loaders,
    packet builders, DocuSign bridges, email clients) from
    generating intelligence or partial intelligence objects.
    """

    @abstractmethod
    def run_intelligence(self, vendor_id: str) -> dict:
        """
        Execute the full CIN intelligence pipeline and return
        the unified intelligence output.

        Implementations MUST:
        - run Phase-3 engines
        - build HybridSummary
        - build HybridIntelligence
        - return the complete intelligence dict

        Implementations MUST NOT:
        - perform operational workflow
        - track packet lifecycle
        - submit packets
        - call external services
        """
        raise NotImplementedError
