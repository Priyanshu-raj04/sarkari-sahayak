"""PDF → page texts. Detects legacy (non-Unicode) Devanagari fonts and falls back to OCR."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import regex

# Kruti Dev / Chanakya etc. encode Devanagari glyphs on Latin code points, so the "text" looks like
# Latin gibberish ("dsokbZlh"). These fonts are recognisable by name.
LEGACY_FONT_RE = regex.compile(r"kruti|chanakya|devlys|walkman|agra|shusha", regex.IGNORECASE)
_DEVANAGARI = regex.compile(r"\p{Script=Devanagari}")
_LATIN = regex.compile(r"\p{Script=Latin}")

OcrFn = Callable[[pymupdf.Page], str]


@dataclass(frozen=True, slots=True)
class PageText:
    page: int  # 1-based
    text: str
    method: str  # "text" | "ocr"


def needs_ocr(page: pymupdf.Page, expect_hindi: bool) -> bool:
    text = str(page.get_text("text"))
    if len(text.strip()) < 30:  # scanned image page
        return True
    fonts = " ".join(f[3] for f in page.get_fonts())  # f[3] = base font name
    if LEGACY_FONT_RE.search(fonts):
        return True
    if expect_hindi:  # a Hindi document whose text layer has no Devanagari is mis-encoded
        deva, latin = len(_DEVANAGARI.findall(text)), len(_LATIN.findall(text))
        return deva < 0.2 * max(1, deva + latin)
    return False


def tesseract_ocr(page: pymupdf.Page, langs: str = "hin+eng", dpi: int = 300) -> str:
    import pytesseract  # noqa: PLC0415 - optional (extra "ingest")
    from PIL import Image  # noqa: PLC0415

    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(img, lang=langs)


def extract_pages(path: Path, *, expect_hindi: bool, ocr: OcrFn = tesseract_ocr) -> list[PageText]:
    out: list[PageText] = []
    with pymupdf.open(path) as doc:
        for i in range(doc.page_count):
            page = doc[i]
            if needs_ocr(page, expect_hindi):
                out.append(PageText(i + 1, ocr(page), "ocr"))
            else:
                out.append(PageText(i + 1, str(page.get_text("text")), "text"))
    return out
