from core.utils.logger import log

class HybridLifecycleController:
    """
    Operational lifecycle controller for HybridOps.
    Tracks packet state through review, DocuSign, and submission.
    This does NOT replace the Phase-3 HybridLifecycle engine runner.
    """

    def __init__(self):
        self.state = "init"
        log("HybridLifecycleController initialized")

    def transition(self, new_state: str):
        log(f"Lifecycle transition: {self.state} → {new_state}")
        self.state = new_state

    # ---------------------------------------------------------
    # Core lifecycle phases
    # ---------------------------------------------------------

    def on_loaded(self):
        self.transition("loaded")

    def on_generated(self):
        self.transition("generated")

    def on_review(self):
        self.transition("awaiting_review")

    # ---------------------------------------------------------
    # DocuSign lifecycle phases
    # ---------------------------------------------------------

    def on_external_edit_requested(self):
        """
        Packet is paused and sent out to DocuSign.
        """
        self.transition("awaiting_external_edit")

    def on_external_edit_in_progress(self):
        """
        Envelope created, waiting for signer to complete.
        """
        self.transition("external_edit_in_progress")

    def on_external_edit_completed(self):
        """
        Signed/corrected packet retrieved.
        Ready for final submission.
        """
        self.transition("ready_for_submission")

    # ---------------------------------------------------------
    # Final submission
    # ---------------------------------------------------------

    def on_submitted(self):
        self.transition("submitted")
