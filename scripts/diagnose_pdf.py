"""Inspect a PDF and print whether our pipeline would OCR it or not.

Usage:

    python scripts/diagnose_pdf.py path/to/file.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

from app.extractors.pdf import _SCAN_TEXT_THRESHOLD, extract_pdf_text  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/diagnose_pdf.py <file.pdf>")
        return 1

    path = Path(sys.argv[1])
    data = path.read_bytes()

    with fitz.open(stream=data, filetype="pdf") as doc:
        print(f"file:        {path}")
        print(f"size:        {len(data)} bytes")
        print(f"page_count:  {doc.page_count}")
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            print(f"  page {i}: {len(text)} chars of embedded text")

    result = extract_pdf_text(data)
    print()
    print(f"threshold:   {_SCAN_TEXT_THRESHOLD} chars/page")
    print(f"is_scanned:  {result.is_scanned}")
    print(f"route:       {'OCR engine (needs Poppler + Tesseract)' if result.is_scanned else 'pymupdf → LLM'}")
    if result.extracted.text:
        preview = result.extracted.text[:280].replace("\n", " ")
        print()
        print(f"preview:     {preview}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
