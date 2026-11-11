import pytest
from hypothesis import given
from hypothesis import strategies as st

from sahayak.text.chunking import chunk_page, split_sentences


def test_split_sentences_handles_danda_and_latin_punctuation() -> None:
    text = "यह पहला वाक्य है। यह दूसरा है॥ Third one. Fourth?"
    assert split_sentences(text) == ["यह पहला वाक्य है।", "यह दूसरा है॥", "Third one.", "Fourth?"]


def test_chunk_ids_are_stable_and_ordered() -> None:
    text = "वाक्य एक। वाक्य दो। वाक्य तीन।"
    chunks = chunk_page("MD-KYC-2016", 3, text, max_chars=20, overlap_sentences=0)
    assert [c.chunk_id for c in chunks] == [f"MD-KYC-2016#p3c{i}" for i in range(len(chunks))]
    assert chunk_page("MD-KYC-2016", 3, text, max_chars=20, overlap_sentences=0) == chunks


def test_overlap_carries_last_sentence_forward() -> None:
    chunks = chunk_page("D", 1, "Aaaa. Bbbb. Cccc.", max_chars=11, overlap_sentences=1)
    assert [c.text for c in chunks] == ["Aaaa. Bbbb.", "Bbbb. Cccc."]


def test_oversized_sentence_becomes_its_own_chunk() -> None:
    long = "क" * 50 + "।"
    chunks = chunk_page("D", 1, f"छोटा। {long} छोटा।", max_chars=20, overlap_sentences=0)
    assert any(c.text == long for c in chunks)


def test_rejects_non_positive_max_chars() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_page("D", 1, "x.", max_chars=0)


@given(st.lists(st.text(alphabet="कखगabc ", min_size=1, max_size=30), min_size=1, max_size=20))
def test_chunking_never_loses_words(parts: list[str]) -> None:
    text = "। ".join(parts) + "।"
    words_in = set(text.replace("।", " ").split())
    chunks = chunk_page("D", 1, text, max_chars=60, overlap_sentences=0)
    words_out = set(" ".join(c.text for c in chunks).replace("।", " ").split())
    assert words_in == words_out
