import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sahayak.text.normalize import detect_script, normalize_text, tokenize


def test_stdlib_re_breaks_devanagari_which_is_why_we_use_regex() -> None:
    assert re.findall(r"\w+", "किताबें") != ["किताबें"]  # documents the pitfall


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("किताबें पढ़ो", ["किताबें", "पढ़ो"]),
        ("KYC-नियम 2016", ["kyc", "नियम", "2016"]),
        ("  Re-KYC   norms  ", ["re", "kyc", "norms"]),
    ],
)
def test_tokenize_keeps_matras_and_lowercases_latin(text: str, expected: list[str]) -> None:
    assert tokenize(text) == expected


def test_normalize_removes_zero_width_and_collapses_space() -> None:
    assert normalize_text("के\N{ZERO WIDTH JOINER}वाईसी \n\n नियम") == "केवाईसी नियम"


def test_nfc_decomposes_nukta_letters_so_both_pdf_forms_match() -> None:
    # QA is a Unicode *composition exclusion*: NFC turns it into KA + NUKTA.
    precomposed = "\N{DEVANAGARI LETTER QA}"
    decomposed = "\N{DEVANAGARI LETTER KA}\N{DEVANAGARI SIGN NUKTA}"
    assert normalize_text(precomposed) == normalize_text(decomposed) == decomposed


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("केवाईसी नियम क्या हैं?", "hi"),
        ("What are the KYC norms?", "en"),
        ("KYC ke liye documents kaunse", "en"),  # romanised Hinglish looks Latin
        ("KYC norms और नियम", "mixed"),
        ("12345 ???", "unknown"),
    ],
)
def test_detect_script(text: str, lang: str) -> None:
    assert detect_script(text) == lang


@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    assert normalize_text(once) == once
