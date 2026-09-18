"""Fill one of the Owner's Word templates from a Mission Record.

**His contract, not ours.** `D:\\Memory\\Templates\\00_PUBLISHER_PLACEHOLDER_POLICY_v1_LOCKED`
is a locked document and this module implements it rather than interpreting it:

    {{field_name}}   lowercase, underscores, exact match only
    1.  each placeholder is one uninterrupted text run
    6.  Publisher replaces exact placeholder matches only
    7.  Missing or unverified values must remain visible or produce a
        structured validation failure. **Publisher must not invent facts.**
    10. Every generated artifact must remain linked to its template version
        and source Mission Record.

Rule 7 is the one that shapes the code. A template filled with blanks where the
facts were missing looks finished and is not; a template that still says
`{{invoice_number}}` is telling the truth about what nobody supplied. So an
unfilled placeholder is **left standing**, is reported, and is not an error.

**Names this program does not know are left alone.** Mike, 2026-09-16: *"the
variations between documents and field names must be allowed. not 2 companies
are the same."* A template may ask for anything; what Dispatch cannot answer
stays visible and goes in the report.

**Money is not ours to fill.** *"any money issue it not the problem of this
program. All money issues are deferred to accounting software."* So
`{{invoice_number}}`, `{{invoice_date}}`, `{{payment_terms}}`,
`{{payment_due_date}}` and `{{remit_to}}` are never supplied here. They are not
gaps in Dispatch; they belong to the accounting software the closing packet is
handed to.

A `.docx` is a zip of XML parts. Replacing in the raw XML is exactly rule 6: a
placeholder Word has split across runs has tags inside it, so it does not match,
and this module **says so** (`split_runs`) rather than silently skipping it.
Stdlib only -- no python-docx, nothing to install on the node.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

#: Where text lives in a .docx. Headers and footers carry placeholders too --
#: the Owner's templates put the load number in a header on every page.
_TEXT_PART = re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")

#: A placeholder, exactly as the policy defines one.
PLACEHOLDER = re.compile(r"\{\{([a-z0-9_]+)\}\}")

#: Looks like one and is not. Reported so a typo is seen rather than silently
#: left standing as though nobody had a value for it.
_SUSPECT = re.compile(r"\{\{[^{}]{0,80}\}\}")

#: Placeholders Dispatch never fills, because the answer is the accounting
#: software's. Left visible on purpose, and reported separately from the facts
#: that are simply missing, so a gap in the mission is not confused with a
#: field that was never this program's to answer.
ACCOUNTING_FIELDS = frozenset({
    "invoice_number", "invoice_date", "payment_terms", "payment_due_date",
    "remit_to",
})

#: Placeholders nothing will ever fill, and **why** -- the two reasons need
#: different remedies (PUBLISHER TEST RULING - REVISION 3, 2026-09-16). Owned by
#: `dispatch/publisher_values.py`; imported rather than restated, because two
#: copies of a ruling drift.
#:
#:   removed       the Owner struck it. Revise the template.
#:   in_the_pod    real, and already inside the controlling document.
#:                 *"When delivery proof is needed: Retrieve POD."* Since
#:                 2026-09-17 this also covers `shipper_signature`, which is
#:                 on the **BOL**, not the POD -- `EVIDENCE_IN_THE_DOCUMENT`
#:                 says which for each, because a remedy naming the wrong
#:                 document fails at the filing cabinet.
#:
#: Reporting them as one list would send a man to delete a placeholder whose
#: answer he actually needs.


#: A header or footer that is talking to whoever *builds* the template rather
#: than to whoever receives the document. Owner ruling, 2026-09-16: **"remove
#: the footer"** -- `Production template | Replace exact {{placeholders}} only |
#: Missing facts remain visible` printed on the bottom of a customer's invoice.
#:
#: **Matched on the instruction, never on the position.** Six of his templates
#: carry that footer and the seventh carries a different one entirely --
#: `Onboarding packet policy | Current approved detention-rate policy controls`
#: -- which is a real statement of terms that belongs on the page. Stripping
#: "the footer" as a position would have quietly deleted it.
_BUILD_INSTRUCTION = re.compile(r"replace\s+exact", re.I)

_RUN_TEXT = re.compile(r"(<w:t[^>]*>)(.*?)(</w:t>)", re.S)


def _pv():
    """The rulings live in one module. Imported late so the engine's document
    filling does not depend on its mapping at import time."""
    from dispatch import publisher_values

    return publisher_values


def _text_parts(archive: zipfile.ZipFile) -> list:
    return [n for n in archive.namelist() if _TEXT_PART.match(n)]


def _is_build_instruction(part: str, xml: str) -> bool:
    return (("header" in part or "footer" in part)
            and bool(_BUILD_INSTRUCTION.search(_visible(xml))))


def _instruction_names(template) -> set:
    """Placeholder names that exist only inside a stripped build instruction.

    `{{placeholders}}` in "Replace exact {{placeholders}} only" is prose. Once
    the instruction is gone it is not a gap in the document, so it must not be
    reported as one -- a report that lists it teaches a man to ignore the list.
    """
    names = set()
    with zipfile.ZipFile(str(template)) as archive:
        for part in _text_parts(archive):
            xml = archive.read(part).decode("utf-8", "replace")
            if _is_build_instruction(part, xml):
                names.update(PLACEHOLDER.findall(_visible(xml)))
    return names


def _blank_runs(xml: str) -> str:
    """Empty every run's words, leaving the part structurally intact.

    The part is deleted from the document's relationships nowhere: a footer
    Word still expects but cannot find is a file it refuses to open. Emptied,
    it prints nothing.
    """
    return _RUN_TEXT.sub(lambda m: m.group(1) + m.group(3), xml)


def _visible(xml: str) -> str:
    """What a reader sees: runs concatenated, tags gone."""
    return re.sub(r"<[^>]+>", "", xml)


def _escape(value: str) -> str:
    """A value going into XML. An ampersand in "Smith & Sons" would otherwise
    produce a document Word refuses to open."""
    return (str(value).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def inventory(template: str | Path) -> dict:
    """Every placeholder in a template, and everything wrong with them.

    The Owner's rule 9: *"Template revisions require a new version identity and
    a placeholder inventory check before approved use."* Read-only.

    Returns `{"names", "split_runs", "malformed"}`. `names` is in document
    order, without duplicates.
    """
    names: list = []
    split: list = []
    malformed: list = []
    with zipfile.ZipFile(str(template)) as archive:
        for part in _text_parts(archive):
            xml = archive.read(part).decode("utf-8", "replace")
            seen = _visible(xml)
            for name in PLACEHOLDER.findall(seen):
                if name not in names:
                    names.append(name)
                # Intact in the raw XML means one uninterrupted run (rule 1).
                if ("{{%s}}" % name) not in xml and name not in split:
                    split.append(name)
            for candidate in _SUSPECT.findall(seen):
                if not PLACEHOLDER.fullmatch(candidate) and candidate not in malformed:
                    malformed.append(candidate)
    return {"names": names, "split_runs": split, "malformed": malformed}


def fill(template: str | Path, values: dict, out_path: str | Path) -> dict:
    """Write a filled copy of `template` to `out_path`, and say what happened.

    **Never writes to the template.** The Library shelf is read-only; this reads
    it and writes somewhere else, always.

    Returns a report:

        template        the template's file name
        output          where the filled document was written
        filled          {placeholder: value} actually replaced
        left_visible    placeholders no value was supplied for -- still standing
                        in the document, which is rule 7 and is not an error
        accounting      those of `left_visible` that are the accounting
                        software's to answer, never Dispatch's
        removed         those of `left_visible` the Owner has struck. Not gaps:
                        the template needs revising
        in_the_pod      those already preserved inside the controlling
                        document -- the POD at the delivery end, the BOL at the
                        pickup end. Not gaps either: retrieve the document
                        `publisher_values.EVIDENCE_IN_THE_DOCUMENT` names
        unused          values handed in that this template never asked for
        split_runs      placeholders Word broke across runs: they will NOT match,
                        and this is the structured validation failure rule 7 asks
                        for
        ok              False when anything was split or malformed

    A report with `ok` False still writes the document, because a partly filled
    document a man can look at beats a refusal he cannot see.
    """
    template = Path(template)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    checked = inventory(template)
    supplied = {k: ("" if v is None else str(v)) for k, v in (values or {}).items()}

    filled: dict = {}
    stripped: list = []
    with zipfile.ZipFile(str(template)) as source:
        parts = set(_text_parts(source))
        # Rewrite the archive wholesale: everything not text is copied byte for
        # byte, so styles, images and numbering survive untouched.
        with zipfile.ZipFile(str(out_path), "w", zipfile.ZIP_DEFLATED) as out:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename in parts:
                    xml = data.decode("utf-8", "replace")
                    if _is_build_instruction(item.filename, xml):
                        xml = _blank_runs(xml)
                        stripped.append(item.filename)
                    else:
                        for name, value in supplied.items():
                            token = "{{%s}}" % name
                            if value == "" or token not in xml:
                                continue
                            xml = xml.replace(token, _escape(value))
                            filled[name] = value
                    data = xml.encode("utf-8")
                out.writestr(item, data)

    left = [n for n in checked["names"] if n not in filled and n not in _instruction_names(template)]
    return {
        "template": template.name,
        "output": str(out_path),
        "filled": filled,
        "stripped": stripped,
        "left_visible": left,
        "accounting": [n for n in left if n in ACCOUNTING_FIELDS],
        "removed": [n for n in left if n in _pv().REMOVED_FIELDS],
        "in_the_pod": [n for n in left if n in _pv().EVIDENCE_IN_POD],
        "unused": sorted(n for n, v in supplied.items()
                         if v != "" and n not in filled),
        "split_runs": list(checked["split_runs"]),
        "malformed": list(checked["malformed"]),
        "ok": not checked["split_runs"] and not checked["malformed"],
    }


def copy_as_is(document: str | Path, out_path: str | Path) -> dict:
    """A fixed company document into the packet, byte for byte.

    The W9, the authority letter, the insurance certificate: nothing is filled
    in and nothing may be altered. `D:\\Memory\\Company Library` holds these and
    is never written to.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(document), str(out_path))
    return {"document": Path(document).name, "output": str(out_path),
            "filled": {}, "left_visible": [], "accounting": [], "unused": [],
            "split_runs": [], "malformed": [], "ok": True}
