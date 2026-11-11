"""Split page text into overlapping sentence packs with stable citation ids.

Public API: `split_sentences` (Latin .?! and Devanagari danda/double-danda),
`chunk_page` → list of `Chunk` with ids `<doc_id>#p<page>c<ordinal>`.
"""

from dataclasses import dataclass

import regex

from sahayak.text.normalize import normalize_text

# Sentence ends: Latin . ? ! and the Devanagari danda (।) / double danda (॥).
_SENTENCE_END_RE = regex.compile(r"(?<=[.?!\N{DEVANAGARI DANDA}\N{DEVANAGARI DOUBLE DANDA}])\s+")


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str  # "<doc_id>#p<page>c<ordinal>" — stable across re-ingestion
    doc_id: str
    page: int
    ordinal: int
    text: str


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END_RE.split(normalize_text(text)) if s]


def chunk_page(
    doc_id: str, page: int, text: str, *, max_chars: int = 900, overlap_sentences: int = 1
) -> list[Chunk]:
    """Greedy sentence packing up to `max_chars`, carrying `overlap_sentences` forward."""
    if max_chars <= 0:
        msg = "max_chars must be positive"
        raise ValueError(msg)
    sentences = split_sentences(text)
    chunks: list[Chunk] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*current, sentence])
        if current and len(candidate) > max_chars:
            chunks.append(_make(doc_id, page, len(chunks), current))
            current = current[-overlap_sentences:] if overlap_sentences else []
        current.append(sentence)
    if current:
        chunks.append(_make(doc_id, page, len(chunks), current))
    return chunks


def _make(doc_id: str, page: int, ordinal: int, sentences: list[str]) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}#p{page}c{ordinal}",
        doc_id=doc_id,
        page=page,
        ordinal=ordinal,
        text=" ".join(sentences),
    )
