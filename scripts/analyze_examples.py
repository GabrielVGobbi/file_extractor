"""Analyze example PDFs: extract text, classify and summarize structure."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.classifiers.document import classify_document  # noqa: E402
from app.extractors.pdf import extract_pdf_text  # noqa: E402

EXAMPLES = [
    ROOT / "docs/examples/vivo.pdf",
    ROOT / "docs/examples/contas_aguas/sabesp.pdf",
    ROOT / "docs/examples/contas_luz/enel.pdf",
    ROOT / "docs/examples/danfes/NF_24935_MAHAL_MAI_VENC16.06.26.pdf",
    ROOT / "docs/examples/faturas_locacao/10060001447 - L1 (1).pdf",
    ROOT / "docs/examples/notas_fiscais_servico/NF_18679286_VERISURE_MAI_VENC05.06.26.PDF.pdf",
]


def analyze(path: Path) -> dict:
    data = path.read_bytes()
    pdf = extract_pdf_text(data)
    classification = classify_document(pdf.extracted.text)
    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = doc.page_count
    preview = pdf.extracted.text[:500].replace("\n", " ").strip()
    return {
        "file": str(path.relative_to(ROOT)),
        "pages": page_count,
        "chars": len(pdf.extracted.text.strip()),
        "is_scanned": pdf.is_scanned,
        "category": classification.category,
        "subtype": classification.subtype,
        "classification_confidence": classification.confidence,
        "text_preview": preview,
    }


def main() -> None:
    results = [analyze(p) for p in EXAMPLES]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
