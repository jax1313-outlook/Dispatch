"""Detection of sensitive material — path and category only, never contents.

THE CONSTRAINT THIS MODULE IS BUILT AROUND: a report that tells Mike "there is
a live AWS key in this file" must not itself become a second copy of that key.
A sensitive-material report that quotes its evidence is a credential-harvesting
document with a reassuring title, and it will be emailed, pasted into a chat and
eventually committed, because that is what reports are for.

So the detectors here are structurally incapable of leaking. Every one of them
reduces to a count: `_count` iterates matches and increments an integer, and the
match object goes out of scope without its text ever being bound to a name. The
`SensitiveFinding` record has four fields -- relative path, category, detector
id, and how many times the detector fired -- and there is no fifth field for an
excerpt, no `context` parameter, no `--show-matches` flag. A count is metadata
about content; it is not content.

The file is read once, in memory, from the sample the scanner already holds. No
second read, no temporary copy, nothing written to disk, so there is no window
in which a decrypted or extracted copy of a secret exists anywhere.

Detectors are deliberately eager. A false positive costs Mike thirty seconds of
looking at a file he wrote; a false negative means a credential travels into a
reorganisation plan unflagged. Where those two errors are that asymmetric, the
correct threshold is low.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .classifier import _count
from .scanner import ScannedFile

# The four categories the mission names. A finding always lands in exactly one.
CATEGORY_CREDENTIALS = "credentials"
CATEGORY_PERSONAL = "personal_data"
CATEGORY_FINANCIAL = "financial_data"
CATEGORY_THIRD_PARTY = "third_party_confidential"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_CREDENTIALS, CATEGORY_PERSONAL, CATEGORY_FINANCIAL, CATEGORY_THIRD_PARTY,
)


@dataclass(frozen=True)
class SensitiveFinding:
    """What a detector found, described without reproducing any of it.

    There is no field here that can hold file content, and that is the whole
    design. `tests/test_sandbox_survey.py` feeds the survey a fixture containing
    a fabricated credential and asserts that the credential string appears in
    none of the generated outputs.
    """

    relpath: str
    category: str
    detector: str
    hits: int


@dataclass(frozen=True)
class _Detector:
    detector_id: str
    category: str
    pattern: re.Pattern[str]
    scope: str  # "text" or "path"


def _det(detector_id: str, category: str, expr: str, scope: str = "text") -> _Detector:
    return _Detector(detector_id, category, re.compile(expr, re.IGNORECASE), scope)


_DETECTORS: tuple[_Detector, ...] = (
    # -- credentials ------------------------------------------------------
    _det("credential_assignment", CATEGORY_CREDENTIALS,
         r"\b(password|passwd|pwd|secret|api[_-]?key|apikey|access[_-]?key|"
         r"client[_-]?secret|auth[_-]?token|private[_-]?key|connection[_-]?string)"
         r"\b\s*[:=]\s*\S{6,}"),
    _det("private_key_block", CATEGORY_CREDENTIALS,
         r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    _det("aws_access_key_id", CATEGORY_CREDENTIALS, r"\bAKIA[0-9A-Z]{16}\b"),
    _det("bearer_token_header", CATEGORY_CREDENTIALS,
         r"\bauthorization\s*:\s*(bearer|basic)\s+\S{8,}"),
    _det("url_embedded_credentials", CATEGORY_CREDENTIALS,
         r"\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:[^\s/@]+@"),
    _det("credential_filename", CATEGORY_CREDENTIALS,
         r"(^|/)(\.env(\..*)?|credentials?|id_rsa|id_ed25519|.*\.(pem|pfx|p12|keytab|jks|ppk))$",
         scope="path"),
    # -- personal data ----------------------------------------------------
    _det("us_ssn", CATEGORY_PERSONAL, r"\b\d{3}-\d{2}-\d{4}\b"),
    _det("email_address", CATEGORY_PERSONAL, r"\b[\w.+\-]+@[\w\-]+\.[A-Za-z]{2,}\b"),
    _det("date_of_birth", CATEGORY_PERSONAL,
         r"\b(date of birth|d\.o\.b\.?|\bdob\b)\s*[:=]"),
    _det("government_id", CATEGORY_PERSONAL,
         r"\b(passport|driver'?s licen[cs]e|licen[cs]e number|cdl number)\b\s*[:=#]"),
    # `(?<![a-z0-9])`/`(?![a-z0-9])` rather than `\b`: `_` is a word character,
    # so `\bresume\b` does not match `resume_final.txt` -- which is exactly how
    # such a file is named in practice.
    _det("personal_filename", CATEGORY_PERSONAL,
         r"(^|/)[^/]*(?<![a-z0-9])(resume|cv|passport|medical|health|"
         r"birth[_-]?certificate)(?![a-z0-9])", scope="path"),
    # -- financial --------------------------------------------------------
    _det("bank_routing", CATEGORY_FINANCIAL,
         r"\b(routing|aba)\s*(number|no\.?|#)?\s*[:=#]\s*\d{9}\b"),
    _det("bank_account", CATEGORY_FINANCIAL,
         r"\b(account)\s*(number|no\.?|#)\s*[:=#]\s*\d{6,}"),
    _det("payment_card", CATEGORY_FINANCIAL, r"\b(?:\d[ \-]?){15,19}\b"),
    _det("financial_filename", CATEGORY_FINANCIAL,
         r"(^|/)[^/]*(?<![a-z0-9])(payroll|invoice|w-?2|1099|tax[_-]?return|"
         r"bank[_-]?statement|settlement[_-]?statement|salary)(?![a-z0-9])",
         scope="path"),
    # -- third-party confidential -----------------------------------------
    _det("confidentiality_marking", CATEGORY_THIRD_PARTY,
         r"\b(strictly confidential|company confidential|proprietary and confidential|"
         r"internal use only|do not distribute|non[- ]disclosure agreement|\bnda\b)\b"),
    _det("third_party_filename", CATEGORY_THIRD_PARTY,
         r"(^|/)[^/]*(?<![a-z0-9])(nda|confidential|proprietary)(?![a-z0-9])",
         scope="path"),
)

# Digit runs long enough to look like a card number are everywhere in log files
# and hashes, so `payment_card` is gated on a Luhn check. Without it every
# Sandbox with a build log in it reports a payment-card finding.
_DIGITS_ONLY = re.compile(r"[^0-9]")


def _luhn_ok(digits: str) -> bool:
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _count_payment_cards(text: str) -> int:
    """Count Luhn-valid card-shaped runs.

    The matched digits are normalised and checked, then dropped. They are never
    returned, stored or logged -- the function's entire output is an integer.
    """
    total = 0
    for match in re.finditer(r"\b(?:\d[ \-]?){15,19}\b", text):
        if _luhn_ok(_DIGITS_ONLY.sub("", match.group(0))):
            total += 1
    return total


def detect(scanned: ScannedFile) -> tuple[SensitiveFinding, ...]:
    """Every sensitive-material finding for one file, as path + category only.

    Path detectors run even when the file could not be read: a file named
    `id_rsa` that we were refused permission to open is still a credential
    sitting in the Sandbox, and the report has to say so.
    """
    findings: list[SensitiveFinding] = []
    path_hay = scanned.relpath.lower()
    use_content = scanned.text_confidence in ("text", "lossy") and bool(scanned.sample)
    text = scanned.sample if use_content else ""

    for detector in _DETECTORS:
        if detector.scope == "path":
            hits = _count(detector.pattern, path_hay)
        elif not use_content:
            continue
        elif detector.detector_id == "payment_card":
            hits = _count_payment_cards(text)
        else:
            hits = _count(detector.pattern, text)
        if hits:
            findings.append(SensitiveFinding(
                relpath=scanned.relpath, category=detector.category,
                detector=detector.detector_id, hits=hits,
            ))
    return tuple(findings)
