"""Run the configured OCR engine end-to-end on a local PDF/image file.

Usage:
    python scripts/test_ocr.py path/to/file.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.extractors.ocr.factory import get_ocr  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/test_ocr.py <file.pdf|image>")
        return 1

    path = Path(sys.argv[1])
    data = path.read_bytes()
    settings = get_settings()
    ocr = get_ocr(settings)

    print(f"engine:       {ocr.name}")
    print(f"poppler_path: {settings.poppler_path}")
    print(f"tesseract:    {settings.tesseract_cmd}")
    print(f"language:     {settings.ocr_language}")
    print(f"dpi:          {settings.ocr_dpi}")
    print()

    if path.suffix.lower() == ".pdf":
        result = ocr.recognize_pdf(data)
    else:
        result = ocr.recognize_image(data)

    print(f"pages: {result.page_count}")
    print(f"chars: {len(result.text)}")
    print()
    print("--- FIRST 800 CHARS ---")
    print(result.text[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
