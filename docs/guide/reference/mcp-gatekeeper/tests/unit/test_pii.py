import pytest
from hypothesis import given
from hypothesis import strategies as st

from gatekeeper.pii.redactor import find_pii, redact
from gatekeeper.pii.verhoeff import check_digit, is_valid

VALID_AADHAAR = "234123412346"  # synthetic test number with a correct Verhoeff digit


def test_verhoeff_known_vector() -> None:
    assert check_digit("236") == "3"
    assert is_valid("2363")
    assert not is_valid("2364")
    assert is_valid(VALID_AADHAAR)
    assert not is_valid("23412341234x")


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        ("मेरा आधार 2341 2341 2346 है", ["IN_AADHAAR"]),
        ("aadhaar 2341-2341-2346", ["IN_AADHAAR"]),
        ("random 234123412345 number", []),  # wrong checksum → not Aadhaar, not mobile
        ("PAN: ABCPE1234F", ["IN_PAN"]),
        ("PAN ABCDE1234F", []),  # 4th letter D is not a valid holder type
        ("call +91 9876543210 now", ["IN_MOBILE"]),
        ("फोन 09876543210", ["IN_MOBILE"]),
        ("mail me at a.b@example.in", ["EMAIL"]),
        ("RBI circular 2016-17/123", []),
    ],
)
def test_find_pii(text: str, kinds: list[str]) -> None:
    assert [f.kind for f in find_pii(text)] == kinds


def test_redact_mixed_hindi_text() -> None:
    text = "आधार 2341 2341 2346, PAN ABCPE1234F, फोन +91 9876543210"
    assert redact(text) == (
        "आधार [REDACTED_IN_AADHAAR], PAN [REDACTED_IN_PAN], फोन [REDACTED_IN_MOBILE]"
    )


@given(st.text())
def test_redaction_is_idempotent(text: str) -> None:
    once = redact(text)
    assert redact(once) == once
