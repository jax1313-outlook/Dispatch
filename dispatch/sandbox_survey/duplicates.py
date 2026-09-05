"""Exact and near-duplicate detection, with the evidence for every match.

A Sandbox that has been worked in for years is mostly copies. "Copy of plan.md",
"plan (2).md", "plan_FINAL.md", "plan_FINAL_v2.md" -- and the reorganisation
question Mike actually has to answer is not "are these similar" but "on what
grounds do you say so". A duplicate report that asserts a match without showing
its working cannot be checked, and an unfalsifiable claim about somebody's files
is exactly the kind of thing this survey must not produce.

So every group here carries `evidence`: for exact matches the shared SHA-256 and
the byte size; for near matches the specific signal, its numeric score, and the
inputs to that score.

Two independent near-duplicate signals run, because they fail in opposite
directions:

*Normalised-token shingling.* Jaccard similarity over 5-token shingles of the
decoded sample. Catches the same document lightly edited, reformatted, or saved
from Word instead of Markdown -- cases where filenames diverged completely. It
cannot see past the sample window and it says nothing useful about binary files.

*Normalised name plus size proximity.* Strips the copy markers Windows and
humans add ("copy of", " (2)", "- Copy", "_v3", trailing dates) and pairs files
whose stripped names are identical and whose sizes are within a few percent.
Catches binaries, spreadsheets and PDFs that the shingling signal is blind to,
and catches copies whose contents diverged past the shingling threshold.

Neither signal ever asserts that a file should be deleted. Duplicate detection
here produces `Duplicate` as a *secondary* class and a numbered, reversible
proposal in PROPOSED_ORGANIZATION_ACTIONS. Nothing is merged, and there is no
code path in this package that could merge anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .scanner import ScannedFile

# Jaccard over 5-token shingles. 0.60 was chosen against the failure that
# matters: at 0.80 a Word-to-Markdown re-save of the same document scores below
# threshold and the pair is missed; at 0.40 two unrelated meeting notes with
# similar boilerplate headers pair up. 0.60 separates them, and because every
# group carries its score, a reader who disagrees can see exactly how close the
# call was rather than having to trust the threshold.
NEAR_DUPLICATE_THRESHOLD = 0.60
SHINGLE_SIZE = 5
MIN_TOKENS_FOR_SHINGLING = 20

# Size proximity for the name-based signal, as a fraction of the larger file.
SIZE_PROXIMITY = 0.10

# Shingling is O(n^2) in the number of text files. A Sandbox with 20,000 text
# files would be 200 million set intersections, which is not a survey, it is a
# hang. Past this many candidates the signal is skipped and the omission is
# reported as a note -- a stated gap, never a silent one.
MAX_SHINGLE_CANDIDATES = 1_500

_TOKEN = re.compile(r"[a-z0-9]+")

# Copy markers, stripped in order. `(2)`, `- Copy`, `copy of`, `_v3`, `final`,
# and trailing ISO/US dates are the ones that actually occur in Windows folders.
_NAME_NOISE: tuple[re.Pattern[str], ...] = tuple(re.compile(expr, re.IGNORECASE) for expr in (
    r"^copy\s+of\s+",
    r"\s*[-_ ]\s*copy(\s*\(\d+\))?$",
    r"\s*\(\d+\)$",
    r"\s*[-_ ]\s*v\d+(\.\d+)*$",
    r"\s*[-_ ]\s*(final|latest|new|old|draft|clean|updated?)$",
    r"[-_ ]\d{4}[-_ ]?\d{2}[-_ ]?\d{2}$",
    r"[-_ ]\d{1,2}[-_ ]\d{1,2}[-_ ]\d{2,4}$",
    r"\s*\(\d+\)$",
))


@dataclass(frozen=True)
class DuplicateGroup:
    """A set of files a named signal says are the same, and why it says so."""

    kind: str            # "exact" or "near"
    signal: str          # the rule that fired
    members: tuple[str, ...]
    evidence: str
    score: float = 1.0


@dataclass
class DuplicateReport:
    exact: list[DuplicateGroup] = field(default_factory=list)
    near: list[DuplicateGroup] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def all_groups(self) -> list[DuplicateGroup]:
        return self.exact + self.near


def normalise_name(name: str) -> str:
    """Strip the copy markers humans and Windows add, leaving the stem's identity.

    Applied repeatedly because they stack: ``Copy of plan - Copy (2).md``.
    """
    stem = name.rsplit(".", 1)[0] if "." in name else name
    previous = None
    while previous != stem:
        previous = stem
        for pattern in _NAME_NOISE:
            stem = pattern.sub("", stem).strip()
    return re.sub(r"[\s_\-]+", " ", stem).strip().lower()


def shingles(text: str, size: int = SHINGLE_SIZE) -> frozenset[str]:
    """Normalised-token shingles. Case, punctuation and whitespace are discarded.

    Discarding them is what makes the signal survive a Word re-save, a Markdown
    reflow and a change of quote characters -- the three edits most likely to
    separate two copies of the same document in a Windows folder.
    """
    tokens = _TOKEN.findall(text.lower())
    if len(tokens) < size:
        return frozenset()
    return frozenset(
        " ".join(tokens[index:index + size]) for index in range(len(tokens) - size + 1)
    )


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0


def _exact_groups(files: Sequence[ScannedFile]) -> list[DuplicateGroup]:
    by_hash: dict[str, list[ScannedFile]] = {}
    for item in files:
        # Empty files all share one hash and are not meaningfully duplicates of
        # each other; grouping them produces one enormous useless group.
        if not item.sha256 or item.size == 0:
            continue
        by_hash.setdefault(item.sha256, []).append(item)

    groups: list[DuplicateGroup] = []
    for digest, members in sorted(by_hash.items()):
        if len(members) < 2:
            continue
        groups.append(DuplicateGroup(
            kind="exact",
            signal="sha256_identical",
            members=tuple(sorted(item.relpath for item in members)),
            evidence=(
                f"{len(members)} files share SHA-256 {digest} and are byte-identical "
                f"at {members[0].size:,} bytes each"
            ),
            score=1.0,
        ))
    return groups


def _name_size_groups(
    files: Sequence[ScannedFile], already: set[str]
) -> list[DuplicateGroup]:
    by_name: dict[str, list[ScannedFile]] = {}
    for item in files:
        if item.relpath in already or item.size == 0:
            continue
        by_name.setdefault(normalise_name(item.name), []).append(item)

    groups: list[DuplicateGroup] = []
    for stem, members in sorted(by_name.items()):
        if len(members) < 2 or not stem:
            continue
        ordered = sorted(members, key=lambda item: item.relpath)
        largest = max(item.size for item in ordered)
        smallest = min(item.size for item in ordered)
        spread = (largest - smallest) / largest if largest else 0.0
        if spread > SIZE_PROXIMITY:
            continue
        groups.append(DuplicateGroup(
            kind="near",
            signal="normalised_name_and_size",
            members=tuple(item.relpath for item in ordered),
            evidence=(
                f"filenames normalise to {stem!r} once copy markers are stripped; "
                f"sizes range {smallest:,}-{largest:,} bytes, a spread of "
                f"{spread * 100:.1f}% (threshold {SIZE_PROXIMITY * 100:.0f}%)"
            ),
            score=round(1.0 - spread, 4),
        ))
    return groups


def _shingle_groups(
    files: Sequence[ScannedFile], already: set[str], report: DuplicateReport
) -> list[DuplicateGroup]:
    candidates = [
        item for item in files
        if item.relpath not in already
        and item.text_confidence in ("text", "lossy")
        and item.sample
    ]
    if len(candidates) > MAX_SHINGLE_CANDIDATES:
        report.notes.append(
            f"near-content shingling was not run: {len(candidates)} text files exceed the "
            f"{MAX_SHINGLE_CANDIDATES} candidate ceiling. Exact-hash and normalised-name "
            "duplicate detection still ran over every file. This is a stated gap, not a "
            "claim that no near-content duplicates exist."
        )
        return []

    prints: list[tuple[ScannedFile, frozenset[str]]] = []
    for item in candidates:
        shingle_set = shingles(item.sample)
        if len(shingle_set) >= MIN_TOKENS_FOR_SHINGLING - SHINGLE_SIZE + 1:
            prints.append((item, shingle_set))

    groups: list[DuplicateGroup] = []
    for left_index in range(len(prints)):
        left, left_set = prints[left_index]
        for right_index in range(left_index + 1, len(prints)):
            right, right_set = prints[right_index]
            score = jaccard(left_set, right_set)
            if score < NEAR_DUPLICATE_THRESHOLD:
                continue
            shared = len(left_set & right_set)
            groups.append(DuplicateGroup(
                kind="near",
                signal="token_shingling",
                members=tuple(sorted((left.relpath, right.relpath))),
                evidence=(
                    f"Jaccard {score:.3f} over {SHINGLE_SIZE}-token normalised shingles of "
                    f"the read sample: {shared} shingles shared of {len(left_set)} and "
                    f"{len(right_set)} (threshold {NEAR_DUPLICATE_THRESHOLD})"
                ),
                score=round(score, 4),
            ))
    return groups


def find_duplicates(files: Iterable[ScannedFile]) -> DuplicateReport:
    """Exact groups first, then near groups over what is left.

    Exact matches are subtracted from the near-duplicate candidate pool because
    reporting a byte-identical pair a second time as "94% similar" adds nothing
    and makes the near-duplicate section look larger than it is.
    """
    ordered = sorted(files, key=lambda item: item.relpath)
    report = DuplicateReport()
    report.exact = _exact_groups(ordered)
    consumed = {member for group in report.exact for member in group.members}
    report.near = _name_size_groups(ordered, consumed)
    report.near.extend(_shingle_groups(ordered, consumed, report))
    report.near.sort(key=lambda group: (group.signal, group.members))
    return report
