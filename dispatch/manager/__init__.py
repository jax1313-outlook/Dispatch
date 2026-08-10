"""Dispatch Manager -- the Run Office function.

Scope is deliberately narrow, per DISPATCH_STAGE12_MANAGER_BUILD_DESIGN_v1.md
(Claude-3 repository): this module reads existing, already-tested
signal sources, classifies and ranks them per MANAGER.md's own
doctrine, and creates a Work Item + Portal Card only for signals that
clear the Review Needed bar. It never approves, books, submits, or
transitions a work item to any state Mike didn't authorize -- every
transition it makes moves through dispatch.spine.store.apply_transition(),
the same single writer path every other function uses.

Lives under dispatch/, not portal/, mirroring dispatch/spine/ and
dispatch/security/'s placement -- Manager's classification/priority/
signal-aggregation logic has no Flask dependency. Portal's route and
template (the actual /manager page) live under portal/, consuming this
module the same way portal/routes/pages.py consumes dispatch/services.py.

Persistence: no new database table. Dedup and card creation reuse the
Spine's existing work_items/portal_cards tables (dispatch/spine/).
"""
