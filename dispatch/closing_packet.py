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


def templates_in(shelf: Path) -> list:
    """His fill-in templates, in his own numbered order, policy document aside."""
    folder = shelf / TEMPLATES_DIRNAME
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob("*.docx")
                  if not any(mark in p.name.upper() for mark in _NOT_A_TEMPLATE)
                  and not p.name.startswith("~$"))


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
          today: str = "", driver_name: str = "", delivered: bool = True) -> dict:
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

    if not shelf or not shelf.is_dir():
        # UNCONFIGURED, said plainly. Not an error in the run -- the freight is
        # delivered either way.
        report["ok"] = False
        report["note"] = ("No document shelf is configured. Set DISPATCH_MEMORY_ROOT "
                          "to the folder holding Templates and Company Library.")
        return report

    values = pv.values_for(record, today=today, driver_name=driver_name,
                           delivered=delivered)

    for template in templates_in(shelf):
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
