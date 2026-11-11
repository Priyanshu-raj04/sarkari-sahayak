"""Indian PII detection/redaction: Aadhaar (with Verhoeff), PAN, mobile numbers, emails."""

from dataclasses import dataclass

import regex

from gatekeeper.pii.verhoeff import is_valid

# Aadhaar: 12 digits, first digit 2-9, optional single space/hyphen between 4-digit groups.
_AADHAAR = regex.compile(r"(?<!\d)([2-9]\d{3})[ -]?(\d{4})[ -]?(\d{4})(?!\d)")
# PAN: 5 letters (4th = holder type), 4 digits, 1 letter.
_PAN = regex.compile(r"(?<![A-Z0-9])[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z](?![A-Z0-9])")
# Indian mobile: optional +91 / 0 prefix, 10 digits starting 6-9.
_MOBILE = regex.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{9}(?!\d)")
_EMAIL = regex.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str
    start: int
    end: int


def find_pii(text: str) -> list[Finding]:
    findings: list[Finding] = []
    for m in _AADHAAR.finditer(text):
        if is_valid("".join(m.groups())):  # checksum filters most random 12-digit numbers
            findings.append(Finding("IN_AADHAAR", m.start(), m.end()))
    findings += [Finding("IN_PAN", m.start(), m.end()) for m in _PAN.finditer(text)]
    findings += [Finding("EMAIL", m.start(), m.end()) for m in _EMAIL.finditer(text)]
    taken = [(f.start, f.end) for f in findings]
    for m in _MOBILE.finditer(text):
        if not any(s <= m.start() < e for s, e in taken):  # don't double-flag Aadhaar digits
            findings.append(Finding("IN_MOBILE", m.start(), m.end()))
    return sorted(findings, key=lambda f: f.start)


def redact(text: str) -> str:
    out, last = [], 0
    for f in find_pii(text):
        if f.start < last:  # overlapping match already redacted
            continue
        out += [text[last : f.start], f"[REDACTED_{f.kind}]"]
        last = f.end
    out.append(text[last:])
    return "".join(out)
