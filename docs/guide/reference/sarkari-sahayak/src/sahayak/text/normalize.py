"""Unicode normalisation, script detection and tokenisation for Hindi/Marathi/English."""

import unicodedata
from typing import Literal

import regex

Lang = Literal["hi", "en", "mixed", "unknown"]

# Letters + combining marks (matras, virama, nukta) + digits.
# NOTE: stdlib `re`'s \w would split Devanagari words.
_TOKEN_RE = regex.compile(r"[\p{L}\p{M}\p{N}]+")
_DEVANAGARI_RE = regex.compile(r"\p{Script=Devanagari}")
_LATIN_RE = regex.compile(r"\p{Script=Latin}")
_ZERO_WIDTH_RE = regex.compile(
    "[\N{ZERO WIDTH SPACE}\N{ZERO WIDTH NON-JOINER}\N{ZERO WIDTH JOINER}"
    "\N{WORD JOINER}\N{ZERO WIDTH NO-BREAK SPACE}]"
)
_SPACE_RE = regex.compile(r"\s+")


def normalize_text(text: str) -> str:
    """NFC-normalise, drop zero-width characters, collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = _ZERO_WIDTH_RE.sub("", text)
    return _SPACE_RE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Lower-cased word tokens that keep Devanagari matras attached."""
    return [t.lower() for t in _TOKEN_RE.findall(normalize_text(text))]


def detect_script(text: str, threshold: float = 0.8) -> Lang:
    """Classify by the share of Devanagari vs Latin letters."""
    deva = len(_DEVANAGARI_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    total = deva + latin
    if total == 0:
        return "unknown"
    if deva / total >= threshold:
        return "hi"
    if latin / total >= threshold:
        return "en"
    return "mixed"
