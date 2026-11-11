from pathlib import Path

import pymupdf

from sahayak.ingest.pdf import extract_pages

LONG_EN = "Regulated entities shall update KYC records periodically as per this Direction."


def make_pdf(tmp_path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)  # built-in Helvetica (Latin only)
    path = tmp_path / "t.pdf"
    doc.save(path)
    return path


def fake_ocr(page: pymupdf.Page) -> str:
    return f"OCR page {page.number + 1}"  # type: ignore[operator]


def test_text_layer_used_for_english_pages(tmp_path: Path) -> None:
    pages = extract_pages(make_pdf(tmp_path, [LONG_EN]), expect_hindi=False, ocr=fake_ocr)
    assert pages[0].method == "text"
    assert "KYC records" in pages[0].text


def test_empty_page_goes_to_ocr(tmp_path: Path) -> None:
    pages = extract_pages(make_pdf(tmp_path, [LONG_EN, ""]), expect_hindi=False, ocr=fake_ocr)
    assert [p.method for p in pages] == ["text", "ocr"]
    assert pages[1].text == "OCR page 2"


def test_hindi_doc_with_latin_only_text_layer_goes_to_ocr(tmp_path: Path) -> None:
    # Simulates a legacy-font PDF: Devanagari shown on screen, Latin gibberish in the text layer.
    gibberish = "dsokbZlh fu;eksa dk ikyu lHkh cSadksa ds fy, vfuok;Z gSA"
    pages = extract_pages(make_pdf(tmp_path, [gibberish]), expect_hindi=True, ocr=fake_ocr)
    assert pages[0].method == "ocr"
