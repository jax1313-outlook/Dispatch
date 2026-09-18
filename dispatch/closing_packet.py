"""The closing packet: one folder, named by the load number.

**Owner ruling, 2026-09-16:** *"POD sent completes the load and triggers the
closing packet."*

And, on the filing, 2026-09-15:

    *"when i close a load and the POD and all invoice and closing documents are
    sent. a duplicate along with all original are placed in a folder inside of
    Library according to that number for retervial from Archive. that is the
    tracing number. same system used by FedEx/ UPS and others."*

So the folder is named by the load number and nothing else. `Tallahassee-1487`
is what a customer quotes back on the phone, and it is what the folder is
called.

WHAT IT PUTS IN THE FOLDER
==========================

His templates from `D:\\Memory\\Templates`, filled by `dispatch.template_fill` to
his locked placeholder policy: exact matches only, and **a fact nobody supplied
is left visible rather than blanked**. Then the fixed company documents --
`W9.pdf` and anything beside it -- copied in byte for byte.

**`D:\\Memory` is read. It is never written.** Everything produced lands under
the packet root.

WHAT IT DOES NOT DO
===================

**It does not send.** Assembling a packet and putting a document in front of a
broker are different acts, and the second one is the Owner's.

**It does not invoice.** *"All money issues are deferred to accounting
software."* The invoice document is produced because it is a document; the
invoice number, dates and terms stay visible for the accounting software to
answer.

**It never costs the load.** A packet that cannot be built is reported and the
completed run stands. A driver who has delivered his freight and sent his POD
has finished, whether or not a Word template was reachable.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Where his fill-in templates live. Read-only (CLAUDE.md: the Library shelf is
#: never written by Dispatch).
TEMPLATES_DIRNAME = "Templates"

#: The fixed company documents -- W9, authority, insurance -- copied in as they
#: are, never filled.
LIBRARY_DIRNAME = "Company Library"

#: His placeholder policy document is not a template to fill.
_NOT_A_TEMPLATE = ("PLACEHOLDER_POLICY",)

#: **The paper has a moment, and it is not the end of the run.**
#:
#: Two of his templates are forms a person signs at a dock. From his Document
#: List (`D:\Library\Templates\Document List.docx`):
#:
#:     Pickup Confirmation - POP - this document is signed by shipping
#:     personnel and may include a packing list, and other commodity related
#:     documents ... These documents will be scanned before departure.
#:
#:     Delivery Confirmation - POD is signed and scanned ... This is a legal
#:     receipt of goods for Florida lien laws and UCC1 filing if needed.
#:
#: And the workflow they belong to, in his words, 2026-09-17:
#:
#:     "the truck is parked and stored at a location miles away. The driver
#:      begins ELD, pre-trip inspection, fuels along the way. at some point the
#:      activation of pickup is done and Publisher creates load documents and
#:      ques for printing upon arrival at pickup location. Driver prints,
#:      clipboards them and enters."
#:
#: **Generation at activation, printing at arrival.** They were produced by
#: `build()` when the load reached `completed` -- after the POD had already
#: come back -- so a form meant for a dock could never have served its purpose.
#:
#: One document at each stop; his numbering, and his answer when asked:
#: *"pickup set 05, delivery set 03"*.
PHASE_SETS = {
    "pickup": ("05",),
    "delivery": ("03",),
}

#: What the closing packet still generates. The two dock forms are produced at
#: their stops and reach the packet as the **scanned signed copies** the driver
#: uploads -- a fresh blank at the end would be the wrong document entirely.
#:
#: `07` is the Detention Time **Policy**, an onboarding document. His Document
#: List names what the Closing Packet holds -- the cover Thank You letter, all
#: signed documents, POD and BOL, the documents acquired at pickup, and the
#: Invoice -- and the policy is not among them. Confirmed 2026-09-17: *"yes,
#: exclude 07"*.
_NOT_IN_THE_CLOSING_PACKET = ("03", "05", "07")


def memory_root() -> Path | None:
    """The Library shelf, if this node has one configured."""
    root = os.environ.get("DISPATCH_MEMORY_ROOT")
    return Path(root) if root else None


def packets_root() -> Path:
    """Where closed loads are filed. One folder per load number beneath it."""
    explicit = os.environ.get("DISPATCH_PACKET_ROOT")
    if explicit:
        return Path(explicit)
    ops_root = os.environ.get("DISPATCH_OPERATIONS_ROOT")
    if ops_root:
        return Path(ops_root) / "Closing Packets"
    data_dir = os.environ.get("PORTAL_DATA_DIR")
    if data_dir:
        return Path(data_dir) / "Closing Packets"
    return Path(__file__).resolve().parent.parent / "portal" / "data" / "Closing Packets"


def folder_for(load_number: str) -> Path:
    """The folder this load's documents are filed in.

    Named by the load number exactly as it was given -- no case folding, no
    stripping of dashes. A number we tidied up is a number that no longer
    matches theirs (`dispatch/load_number.py`). Only the characters a file
    system cannot hold are replaced.
    """
    safe = "".join("-" if ch in '\\/:*?"<>|' else ch
                   for ch in str(load_number or "").strip()) or "no-load-number"
    return packets_root() / safe


def templates_in(shelf: Path, *, only=None, without=None) -> list:
    """His fill-in templates, in his own numbered order, policy document aside.

    `only` and `without` take the leading numbers of his filenames -- `("05",)`
    -- because the number is how he refers to them and how the Document List
    orders them. Neither is a default: a caller says which moment it is filling
    for, and a caller that says nothing still gets everything, as it always did.
    """
    folder = shelf / TEMPLATES_DIRNAME
    if not folder.is_dir():
        return []
    found = sorted(p for p in folder.glob("*.docx")
                   if not any(mark in p.name.upper() for mark in _NOT_A_TEMPLATE)
                   and not p.name.startswith("~$"))
    if only is not None:
        found = [p for p in found if p.name[:2] in tuple(only)]
    if without is not None:
        found = [p for p in found if p.name[:2] not in tuple(without)]
    return found


def company_documents_in(shelf: Path) -> list:
    """The fixed documents, from both shelves. Nothing here is filled in."""
    found = []
    for folder in (shelf / LIBRARY_DIRNAME, shelf / TEMPLATES_DIRNAME):
        if folder.is_dir():
            found += [p for p in sorted(folder.iterdir())
                      if p.is_file() and p.suffix.lower() == ".pdf"
                      and not p.name.startswith("~$")]
    return found


def build(record: dict, *, shelf: Path | None = None, out_dir: Path | None = None,
          today: str = "", driver_name: str = "", evidence=None,
          only=None, without=None) -> dict:
    """Fill his templates for one load and file them under its load number.

    Returns `{"load_number", "folder", "documents", "copied", "missing",
    "accounting", "removed", "in_the_pod", "ok", "note"}`. `ok` is False only
    when a template could not be filled at all; a document with placeholders
    still standing is **not** a failure -- that is rule 7 working.
    """
    from dispatch import publisher_values as pv
    from dispatch import template_fill as tf

    record = dict(record or {})
    load_number = (record.get("load_number")
                   or (record.get("card_data") or {}).get("load_id") or "")
    shelf = shelf or memory_root()
    folder = Path(out_dir) if out_dir else folder_for(load_number)

    report = {"load_number": load_number, "folder": str(folder), "documents": [],
              "copied": [], "missing": [], "accounting": [], "removed": [],
              "in_the_pod": [], "ok": True, "note": ""}

    if only and shelf.is_dir() and not templates_in(shelf, only=only):
        # **Only when a set was asked for.** A caller naming `05` and finding
        # nothing has a real problem: the driver gets no form. A caller that
        # named no set and finds an empty shelf is the ordinary unconfigured
        # case, and it returned an empty report long before this guard existed
        # -- turning that into a failure changed the answer for every caller
        # that never asked for anything.
        report["ok"] = False
        report["note"] = ("No template on the shelf matches %s."
                          % ", ".join(only))
        return report

    if not shelf or not shelf.is_dir():
        # UNCONFIGURED, said plainly. Not an error in the run -- the freight is
        # delivered either way.
        report["ok"] = False
        report["note"] = ("No document shelf is configured. Set DISPATCH_MEMORY_ROOT "
                          "to the folder holding Templates and Company Library.")
        return report

    # **The uploaded files, not the driver's ticks.** The "is it attached"
    # lines on his covers are answered from the evidence actually on the load
    # (Owner, 2026-09-17: *"not before all documents are scanned and
    # uploaded."*). The caller holds the load row; the caller answers -- the
    # same reason `delivered` was once a parameter here.
    values = pv.values_for(record, today=today, driver_name=driver_name,
                           evidence=evidence)

    for template in templates_in(shelf, only=only, without=without):
        out = folder / template.name.replace(" 1.docx", ".docx")
        try:
            filled = tf.fill(template, values, out)
        except Exception as exc:  # noqa: BLE001 - one bad template is not a bad run
            report["ok"] = False
            report["documents"].append({"template": template.name, "output": "",
                                        "ok": False, "error": str(exc)})
            continue
        report["documents"].append({
            "template": filled["template"], "output": filled["output"],
            "filled": sorted(filled["filled"]), "left_visible": filled["left_visible"],
            "ok": filled["ok"],
        })
        for key in ("accounting", "removed", "in_the_pod"):
            for name in filled[key]:
                if name not in report[key]:
                    report[key].append(name)
        for name in filled["left_visible"]:
            if name not in report["missing"] and name not in filled["accounting"]:
                report["missing"].append(name)

    for document in company_documents_in(shelf):
        try:
            copied = tf.copy_as_is(document, folder / document.name)
        except Exception as exc:  # noqa: BLE001
            report["ok"] = False
            report["note"] = "%s could not be copied: %s" % (document.name, exc)
            continue
        report["copied"].append(copied["output"])

    if not report["documents"]:
        report["ok"] = False
        report["note"] = report["note"] or (
            "No templates found in %s." % (shelf / TEMPLATES_DIRNAME))
    return report
