"""Deterministic, rule-based classification of Sandbox files.

No model is consulted. Every class assigned here is the output of a named rule
matching an extension, a filename pattern, a path segment or a regular
expression over the first `max_bytes` of the file, and every assignment carries
the rule's id so a reader can disagree with a specific rule rather than with an
opaque verdict. The same input produces the same output on every run and on
every machine, which is what makes a second survey comparable to the first.

THE POINT OF THIS MODULE IS THE DOWNGRADES, NOT THE UPGRADES.

A survey of somebody else's working folder is under constant pressure to look
finished. The cheap way to make a map look complete is to promote guesses:
call a set of notes "doctrine" because it is written in imperative sentences,
call an AI-generated summary a "decision" because it contains the word
"decided". This module refuses both, by construction:

  * `Decision` is assigned only when a decision marker AND an identifiable
    human actor are both present AND the file does not read as AI-generated.
    Everything else that mentions a decision becomes a *Decision candidate* --
    a flag on the record, deliberately not a class, so it can never be mistaken
    for the thing itself when the class column is read on its own.
  * `Doctrine` is assigned only when the file matches doctrine already locked
    in this mission or in the DISPATCH repository -- see `LOCKED_DOCTRINE`.
    Everything else that reads as doctrine becomes a *Doctrine candidate*.
  * With no matching rule, the answer is `Unknown`. `Unknown` is a correct
    answer here. It is never traded away to reduce the count of unknowns.

Content evidence is suppressed for files whose sample did not decode as text.
A .docx is a ZIP; its accidental ASCII will match prose heuristics if you let
it. Those files are classified from filename and path context alone, and the
record says so, so nobody reads a content-derived class that was really derived
from compression noise.

NOTHING IN THIS MODULE EVER RETAINS MATCHED TEXT. Rules return booleans and
counts. That is not an accident of style -- it is what allows the reports to
promise that no file's contents are quoted anywhere, which in turn is what lets
the sensitive-material report exist at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .scanner import ScannedFile

# The complete, closed class vocabulary. A class outside this tuple is a bug.
CLASSES: tuple[str, ...] = (
    "Knowledge", "Evidence", "Research", "Decision", "Doctrine", "Draft",
    "Duplicate", "Historical", "Personal", "Sensitive", "Unknown",
)

# Reproduced verbatim in SANDBOX_KNOWLEDGE_MAP. They are the mission's rules of
# interpretation, not a paraphrase of them, and the report generator emits this
# tuple rather than restating it so the two can never drift apart.
INTERPRETATION_RULES: tuple[str, ...] = (
    "Architecture research is not accepted architecture.",
    "Notes are not doctrine.",
    "AI-generated reports are not human decisions.",
    "A file is Decision only if it records an explicit human decision with an "
    "identifiable actor; otherwise it is at most a Decision candidate.",
    "Doctrine is assigned only to material that matches doctrine already locked "
    "in this mission or in the repository; everything else that looks like "
    "doctrine is a Doctrine candidate.",
    "When in doubt, Unknown. Never upgrade confidence to make the map look complete.",
)

# Primary-class precedence, most specific first. A file that trips several rules
# takes the first of these it qualifies for as its primary class and keeps the
# rest as secondary classes, so the primary column answers "what is this, mainly"
# and the secondary column preserves everything else the rules found.
_PRECEDENCE: tuple[str, ...] = (
    "Decision", "Doctrine", "Personal", "Research", "Evidence",
    "Draft", "Knowledge", "Historical", "Unknown",
)


@dataclass(frozen=True)
class DoctrineAnchor:
    """One piece of doctrine already locked, that Sandbox material can match.

    `markers` are lowercase substrings; `minimum` of them must be present for a
    match. Requiring more than one keeps a passing mention of the word "policy"
    from promoting a file to `Doctrine`.
    """

    anchor_id: str
    title: str
    markers: tuple[str, ...]
    minimum: int = 2


LOCKED_DOCTRINE: tuple[DoctrineAnchor, ...] = (
    DoctrineAnchor(
        "TRUTH_VOCABULARY",
        "Truth vocabulary: LIVE, CONFIGURED, UNCONFIGURED, SIMULATED, "
        "UNAVAILABLE, MANUAL, ABSENT, UNVERIFIED — these words, no synonyms.",
        ("live", "configured", "unconfigured", "simulated", "unavailable",
         "manual", "absent", "unverified"),
        minimum=3,
    ),
    DoctrineAnchor(
        "NO_MANUFACTURED_ATTESTATION",
        "An attestation of verification, approval, acceptance, authorisation or "
        "confirmation by the programme's principal is never manufactured, "
        "inferred, defaulted, auto-populated, seeded or fixtured.",
        ("never manufacture", "not manufacture", "manufactured attestation",
         "auto-populate", "attestation"),
        minimum=2,
    ),
    DoctrineAnchor(
        "READ_ONLY_FIRST_PASS",
        "The first pass over the Sandbox is read-only; no file is moved, "
        "renamed, deleted, converted or overwritten.",
        ("read-only", "no files were modified", "read only pass", "first pass"),
        minimum=2,
    ),
    DoctrineAnchor(
        "TESTS_ARE_NOT_OPERATIONAL_PROOF",
        "Repository tests are evidence of software behaviour only, never "
        "operational proof.",
        ("evidence of software behavior", "evidence of software behaviour",
         "not operational proof", "never operational proof"),
        minimum=1,
    ),
    DoctrineAnchor(
        "NO_SECRETS_IN_GIT",
        "Runtime secrets, logs containing secrets, evidence files and backups "
        "are never committed to Git.",
        ("do not commit", "never commit", "secret", "credential"),
        minimum=2,
    ),
    DoctrineAnchor(
        "SOURCES_OF_TRUTH",
        "Repositories contain implementation truth; folders contain research "
        "and knowledge evidence; Mike supplies operational truth and authority.",
        ("implementation truth", "operational truth", "source of truth"),
        minimum=2,
    ),
)

# Status words that are NOT in the locked truth vocabulary. A Sandbox document
# that grades a system's reality with these is describing readiness in a
# vocabulary this programme has retired, which is a conflict a reader must see.
_VOCABULARY_CONFLICT_WORDS: tuple[str, ...] = (
    "PARTIALLY LIVE", "MOSTLY WORKING", "READY", "DONE", "COMPLETE",
    "IN PROGRESS", "STUBBED", "MOCKED", "FAKE", "PENDING", "WORKING",
)

# Case-sensitive and word-bounded. Without the boundary "READY" matches inside
# "ALREADY" and every prose document in the Sandbox reports a false conflict.
_VOCABULARY_CONFLICTS = re.compile(
    r"\b(" + "|".join(_VOCABULARY_CONFLICT_WORDS) + r")\b")


@dataclass(frozen=True)
class Classification:
    """The verdict on one file, with every rule that produced it named.

    `decision_candidate` and `doctrine_candidate` are flags rather than classes
    on purpose. See the module docstring: a candidate that lives in the class
    column is a candidate that gets read as the real thing the moment somebody
    sorts the spreadsheet.
    """

    relpath: str
    primary: str
    secondary: tuple[str, ...]
    reasons: tuple[str, ...]
    dispatch_related: bool
    dispatch_signals: tuple[str, ...]
    decision_candidate: bool = False
    doctrine_candidate: bool = False
    matches_locked_doctrine: tuple[str, ...] = ()
    conflicts_with_locked_doctrine: tuple[str, ...] = ()
    prompt_asset: bool = False
    library_candidate: bool = False
    ai_generated: bool = False
    content_evidence_used: bool = True
    unresolved_question_markers: int = 0
    superseded_markers: int = 0
    attestation_claims: int = 0

    @property
    def all_classes(self) -> tuple[str, ...]:
        return (self.primary,) + self.secondary


# --------------------------------------------------------------------------- rules

@dataclass(frozen=True)
class _Rule:
    """One named pattern that contributes one class."""

    rule_id: str
    klass: str
    pattern: re.Pattern[str]
    where: str  # "path" or "text"


def _rule(rule_id: str, klass: str, expr: str, where: str) -> _Rule:
    return _Rule(rule_id, klass, re.compile(expr, re.IGNORECASE), where)


# Path rules run against the lowercase relative path, so a folder name counts as
# evidence about the files inside it -- which is how humans actually organise.
_PATH_RULES: tuple[_Rule, ...] = (
    _rule("path.draft", "Draft", r"(^|[/_ .\-])(draft|wip|untitled|scratch|rough)([/_ .\-]|$)|~\$|\bcopy of\b|\(\d+\)\.|[ _-]copy([ _.-]|$)", "path"),
    _rule("path.historical", "Historical", r"(^|[/_ .\-])(old|older|archive|archived|legacy|previous|superseded|deprecated|backup|bak|20[01]\d)([/_ .\-]|$)", "path"),
    _rule("path.research", "Research", r"(^|[/_ .\-])(research|analysis|study|options|comparison|exploration|architecture|design|proposal|whitepaper|spike|investigation)([/_ .\-]|$)", "path"),
    _rule("path.knowledge", "Knowledge", r"(^|[/_ .\-])(notes?|readme|guide|howto|how-to|reference|manual|glossary|overview|summary|map|handbook|wiki)([/_ .\-]|$)", "path"),
    _rule("path.evidence", "Evidence", r"(^|[/_ .\-])(evidence|screenshot|screen ?capture|export|extract|receipt|logs?|transcript|dump|snapshot|proof)([/_ .\-]|$)", "path"),
    _rule("path.personal", "Personal", r"(^|[/_ .\-])(resume|cv|personal|private|tax|w-?2|1099|payroll|bank|medical|passport|insurance|family|photos?)([/_ .\-]|$)", "path"),
    _rule("path.decision", "Decision", r"(^|[/_ .\-])(decision|decisions|approved|approval|signed|sign-?off|ruling|verdict|adr)([/_ .\-]|$)", "path"),
    _rule("path.doctrine", "Doctrine", r"(^|[/_ .\-])(doctrine|policy|policies|standard|standards|sop|charter|mandate|governance|constitution)([/_ .\-]|$)", "path"),
)

# Extension rules. A .py file in a Sandbox is knowledge about how something was
# built, not evidence of anything having run -- Evidence is reserved for
# artefacts produced by an event.
_EXTENSION_CLASSES: dict[str, str] = {
    ".md": "Knowledge", ".markdown": "Knowledge", ".txt": "Knowledge",
    ".rst": "Knowledge", ".docx": "Knowledge", ".doc": "Knowledge",
    ".odt": "Knowledge", ".rtf": "Knowledge", ".pdf": "Knowledge",
    ".one": "Knowledge", ".pptx": "Knowledge", ".ppt": "Knowledge",
    ".py": "Knowledge", ".js": "Knowledge", ".ts": "Knowledge",
    ".ps1": "Knowledge", ".sh": "Knowledge", ".bat": "Knowledge",
    ".cmd": "Knowledge", ".sql": "Knowledge", ".ipynb": "Research",
    ".csv": "Evidence", ".tsv": "Evidence", ".xlsx": "Evidence",
    ".xls": "Evidence", ".json": "Evidence", ".xml": "Evidence",
    ".log": "Evidence", ".eml": "Evidence", ".msg": "Evidence",
    ".png": "Evidence", ".jpg": "Evidence", ".jpeg": "Evidence",
    ".gif": "Evidence", ".bmp": "Evidence", ".tif": "Evidence",
    ".tiff": "Evidence", ".zip": "Evidence", ".7z": "Evidence",
    ".rar": "Evidence", ".mp4": "Evidence", ".mov": "Evidence",
    ".wav": "Evidence", ".mp3": "Evidence", ".har": "Evidence",
}

_TEXT_RULES: tuple[_Rule, ...] = (
    _rule("text.research", "Research", r"\b(we (could|might|may|should consider)|option [ab1-9]\b|trade-?offs?|pros and cons|alternatives considered|hypothesis|proof of concept)\b", "text"),
    _rule("text.knowledge", "Knowledge", r"\b(how to|steps?:|procedure|overview|introduction|glossary|definition)\b", "text"),
    _rule("text.evidence", "Evidence", r"\b(traceback \(most recent call last\)|http/1\.1|status: ?\d{3}|\[\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2})", "text"),
    _rule("text.draft", "Draft", r"\b(draft|placeholder|lorem ipsum|xxx|fill this in|\btbd\b)\b", "text"),
    _rule("text.historical", "Historical", r"\b(superseded|deprecated|obsolete|no longer (used|true|accurate)|replaced by|old version)\b", "text"),
)

_DECISION_MARKER = re.compile(
    r"\b(decided|decision[: ]|we will|agreed|approved|accepted|authoris(ed|ation)|"
    r"authoriz(ed|ation)|sign[- ]?off|ruling|resolved that)\b", re.IGNORECASE)

# An identifiable actor: an attestation verb, "by", then something shaped like a
# person's name. Two capitalised words minimum -- a single capitalised token
# matches far too much ("Approved By Default", "Approved by Policy").
# Scoped (?i:...) rather than a whole-pattern IGNORECASE flag: the verb may be
# capitalised or not, but the NAME must be capitalised, and dropping case
# sensitivity there turns "approved by the board" into an identifiable actor.
_ACTOR = re.compile(
    r"(?i:\b(?:decided|approved|accepted|authoriz(?:ed)?|authoris(?:ed)?|"
    r"confirmed|verified|signed[- ]off)\s+by\b)\s*[:\-]?\s*"
    r"([A-Z][A-Za-z.'\-]+(?:\s+[A-Z][A-Za-z.'\-]+)+)")

_AI_GENERATED = re.compile(
    r"(as an ai language model|i am an ai|generated by (chatgpt|claude|gpt|copilot|gemini|bard)|"
    r"\bchatgpt\b|^assistant:|\bcertainly! here('| i)s\b|as a large language model)",
    re.IGNORECASE | re.MULTILINE)

_DOCTRINE_LOOKALIKE = re.compile(
    r"\b(doctrine|policy|must not|shall not|is forbidden|is prohibited|"
    r"non-negotiable|standard operating procedure|governing principle|rule \d)\b",
    re.IGNORECASE)

_UNRESOLVED = re.compile(
    r"\b(todo|tbd|fixme|open question|unresolved|undecided|decide later|"
    r"needs? (a )?decision|awaiting)\b|\?\?\?", re.IGNORECASE)

_SUPERSEDED = re.compile(
    r"\b(superseded|deprecated|obsolete|no longer|replaced by|old version|"
    r"previous approach|abandoned)\b", re.IGNORECASE)

_PROMPT_ASSET_PATH = re.compile(r"prompt|instruction", re.IGNORECASE)
_PROMPT_ASSET_TEXT = re.compile(
    r"(you are (a|an|the)\s+\w+|system prompt|### instructions|<system>|"
    r"role:\s*(system|user|assistant))", re.IGNORECASE)

_LIBRARY_CANDIDATE = re.compile(
    r"\b(template|checklist|boiler ?plate|worksheet|form|playbook|"
    r"standard operating|reusable|pattern library|style guide)\b", re.IGNORECASE)

# Word-boundary matching throughout. "cin" as a bare substring matches
# "principal", "vaccine" and "cinema"; as a word it matches the programme.
_DISPATCH_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(expr, re.IGNORECASE)) for label, expr in (
        ("dispatch", r"\bdispatch\b"),
        ("level-1-transport", r"\blevel[ _-]?1[ _-]?transport\b"),
        ("cin", r"\bcin\b|\bcin[- ]lite\b"),
        ("azp", r"\bazp\b"),
        ("freight", r"\b(freight|load board|lane|deadhead|linehaul)\b"),
        ("broker-carrier", r"\b(broker|carrier|shipper|consignee)\b"),
        ("compliance", r"\b(ifta|eld|hos|dot number|mc number|bol|bill of lading|rate con(firmation)?)\b"),
        ("driver-ops", r"\b(driver|dispatcher|tractor|trailer|settlement|detention)\b"),
        ("route-risk", r"\broute risk\b|\brouting\b"),
        ("contracts", r"\b(naics|set[- ]aside|sam\.gov|solicitation|subcontractor)\b"),
    )
)


def _count(pattern: re.Pattern[str], text: str) -> int:
    """How many times a pattern fires, without ever holding what it matched."""
    total = 0
    for _ in pattern.finditer(text):
        total += 1
    return total


def _matched(rules: Iterable[_Rule], haystack: str) -> list[_Rule]:
    return [rule for rule in rules if rule.pattern.search(haystack)]


def locked_doctrine_matches(text: str) -> tuple[str, ...]:
    """Which locked doctrine anchors this text actually matches.

    Case-folded substring counting rather than anything cleverer: the anchors
    are phrases this programme has written down, and a file either repeats
    enough of one to be talking about it or it does not.
    """
    lowered = text.lower()
    hits: list[str] = []
    for anchor in LOCKED_DOCTRINE:
        present = sum(1 for marker in anchor.markers if marker in lowered)
        if present >= anchor.minimum:
            hits.append(anchor.anchor_id)
    return tuple(hits)


def locked_doctrine_conflicts(text: str, attestation_claims: int) -> tuple[str, ...]:
    """Where this text argues with doctrine that is already locked.

    Two conflicts are detectable without quoting anything:

    *Retired status vocabulary.* A document grading readiness as "READY" or
    "MOSTLY WORKING" is using words this programme replaced with a closed
    eight-word vocabulary. Uppercase-only matching, because the conflict is a
    status label, not the ordinary English word in a sentence.

    *An attestation carried as authority.* A Sandbox file asserting that a named
    person approved something is not proof that they did. This mission may not
    manufacture such an attestation and may not accept a found one as authority;
    it is surfaced so Mike can confirm or deny it himself.
    """
    conflicts: list[str] = []
    if _VOCABULARY_CONFLICTS.search(text):
        conflicts.append("TRUTH_VOCABULARY")
    if attestation_claims:
        conflicts.append("NO_MANUFACTURED_ATTESTATION")
    return tuple(conflicts)


_WORD_SEPARATORS = re.compile(r"[_\-]+")


def signal_haystack(text: str) -> str:
    """Normalise separators before word-boundary matching.

    `dispatch_plan.md` contains no word boundary between "dispatch" and "plan",
    because `_` is a word character -- so `\bdispatch\b` misses the most common
    filename spelling in the entire Sandbox. Underscores and hyphens become
    spaces first, which costs nothing and fixes every such miss at once.
    """
    return _WORD_SEPARATORS.sub(" ", text)


def dispatch_signals(haystack: str) -> tuple[str, ...]:
    normalised = signal_haystack(haystack)
    return tuple(label for label, pattern in _DISPATCH_SIGNALS if pattern.search(normalised))


def classify(scanned: ScannedFile) -> Classification:
    """Assign one primary class, any number of secondary classes, and the reasons.

    Never raises. A file this function cannot reason about comes back `Unknown`
    with the reason recorded, which is a real answer and is treated as one.
    """
    path_hay = scanned.relpath.lower()
    use_content = scanned.text_confidence in ("text", "lossy") and bool(scanned.sample)
    text = scanned.sample if use_content else ""

    votes: dict[str, list[str]] = {}

    def vote(klass: str, rule_id: str) -> None:
        votes.setdefault(klass, []).append(rule_id)

    if scanned.read_error:
        # Inventoried, never skipped -- but nothing about its content is claimed.
        return Classification(
            relpath=scanned.relpath,
            primary="Unknown",
            secondary=(),
            reasons=(f"unreadable.{'link' if scanned.is_symlink else 'error'}: {scanned.read_error}",),
            dispatch_related=bool(dispatch_signals(path_hay)),
            dispatch_signals=dispatch_signals(path_hay),
            content_evidence_used=False,
        )

    for rule in _matched(_PATH_RULES, path_hay):
        vote(rule.klass, rule.rule_id)

    extension_class = _EXTENSION_CLASSES.get(scanned.suffix)
    if extension_class:
        vote(extension_class, f"ext{scanned.suffix}")

    if use_content:
        for rule in _matched(_TEXT_RULES, text):
            vote(rule.klass, rule.rule_id)

    # finditer + a counting generator rather than findall: findall would
    # materialise the matched person's name as a string, and no matched file
    # content is ever allowed to reach a record or a report.
    attestation_claims = _count(_ACTOR, text) if use_content else 0
    ai_generated = bool(_AI_GENERATED.search(text)) if use_content else False
    decision_marker = bool(_DECISION_MARKER.search(text)) if use_content else False
    decision_marker = decision_marker or "Decision" in votes

    # --- the Decision gate -------------------------------------------------
    is_decision = bool(attestation_claims) and decision_marker and not ai_generated
    decision_candidate = decision_marker and not is_decision
    if not is_decision:
        # A path or content hint alone never earns the class itself.
        votes.pop("Decision", None)
    else:
        vote("Decision", "decision.actor_identified")

    # --- the Doctrine gate -------------------------------------------------
    matches = locked_doctrine_matches(text) if use_content else ()
    doctrine_lookalike = bool(_DOCTRINE_LOOKALIKE.search(text)) if use_content else False
    doctrine_lookalike = doctrine_lookalike or "Doctrine" in votes
    if matches:
        vote("Doctrine", "doctrine.matches_locked:" + ",".join(matches))
    else:
        votes.pop("Doctrine", None)
    doctrine_candidate = doctrine_lookalike and not matches

    conflicts = locked_doctrine_conflicts(text, attestation_claims) if use_content else ()

    if ai_generated:
        vote("Research", "ai.generated_report_is_not_a_human_decision")

    primary = "Unknown"
    for klass in _PRECEDENCE:
        if klass in votes:
            primary = klass
            break

    reasons: list[str] = []
    for klass in _PRECEDENCE:
        for rule_id in votes.get(klass, ()):
            reasons.append(f"{klass}<-{rule_id}")
    if primary == "Unknown" and not reasons:
        reasons.append(
            "no filename, path, extension or content rule matched; "
            "Unknown is the answer, not a placeholder"
        )
    if not use_content:
        reasons.append(
            f"content evidence suppressed (sample decoded as {scanned.text_confidence}); "
            "classified from filename and path context only"
        )

    secondary = tuple(klass for klass in _PRECEDENCE if klass in votes and klass != primary)

    hay = path_hay + "\n" + text
    signals = dispatch_signals(hay)
    prompt_asset = bool(_PROMPT_ASSET_PATH.search(path_hay)) or (
        use_content and bool(_PROMPT_ASSET_TEXT.search(text)))
    library_candidate = bool(_LIBRARY_CANDIDATE.search(hay)) and "Personal" not in votes

    return Classification(
        relpath=scanned.relpath,
        primary=primary,
        secondary=secondary,
        reasons=tuple(reasons),
        dispatch_related=bool(signals),
        dispatch_signals=signals,
        decision_candidate=decision_candidate,
        doctrine_candidate=doctrine_candidate,
        matches_locked_doctrine=matches,
        conflicts_with_locked_doctrine=conflicts,
        prompt_asset=prompt_asset,
        library_candidate=library_candidate,
        ai_generated=ai_generated,
        content_evidence_used=use_content,
        unresolved_question_markers=_count(_UNRESOLVED, text) if use_content else 0,
        superseded_markers=_count(_SUPERSEDED, text) if use_content else 0,
        attestation_claims=attestation_claims,
    )
