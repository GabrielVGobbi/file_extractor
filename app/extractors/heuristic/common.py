"""Regex primitives shared by heuristic parsers.

Focus: Brazilian fiscal document text as it typically comes out of OCR
(pytesseract) or PyMuPDF. Patterns are intentionally forgiving of extra
whitespace, line breaks and common OCR noise (``O``↔``0``, ``I``↔``1``).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

CNPJ_RE = re.compile(r"\b(\d{2}[.\s]?\d{3}[.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2})\b")
CPF_RE = re.compile(r"\b(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})\b")
ACCESS_KEY_RE = re.compile(r"\b(\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4})\b")
CEP_RE = re.compile(r"\b(\d{5}[-\s]?\d{3})\b")
MONEY_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})")
PHONE_RE = re.compile(r"\(?(\d{2})\)?\s*\d{4,5}[-\s]?\d{4}")
DATE_TIME_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)")
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
COMPETENCE_RE = re.compile(r"\b(\d{2}/\d{4})\b")
NUMBER_SERIES_RE = re.compile(r"\b(\d{1,9})\s*[/\-]\s*([A-Z0-9]{1,3})\b")
CNAE_RE = re.compile(r"\b(\d{4}[-\s]?\d[/\s]?\d{2}[-\s]?\d{2})\b")
SERVICE_CODE_RE = re.compile(r"\b(\d{2}[.,]\d{2})\b")
UF_RE = re.compile(r"\b([A-Z]{2})\b")

STATES = {
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB",
    "PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO",
}


def normalize_whitespace(s: str) -> str:
    """Collapse whitespace / non-breaking spaces produced by OCR."""
    return re.sub(r"[ \t\xa0]+", " ", s).strip()


def normalize_for_match(s: str) -> str:
    """ASCII-fold + uppercase for robust section-header lookup."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_only.upper()


def digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def to_cents(value: str | None) -> int | None:
    """Convert a Brazilian currency literal to integer cents.

    Accepts ``"950,00"``, ``"1.234,56"``, ``"1234.56"`` and OCR variants
    with stray spaces. Returns ``None`` for unparseable input.
    """
    if value is None:
        return None
    raw = value.strip().replace("R$", "").replace(" ", "")
    if not raw:
        return None
    # If both separators exist, the rightmost is the decimal separator.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return int(round(float(raw) * 100))
    except ValueError:
        return None


def parse_datetime(text: str) -> datetime | None:
    """Extract the first ``DD/MM/YYYY[ HH:MM[:SS]]`` occurrence."""
    m = DATE_TIME_RE.search(text)
    if m:
        raw_date, raw_time = m.group(1), m.group(2)
        fmt = "%d/%m/%Y %H:%M:%S" if raw_time.count(":") == 2 else "%d/%m/%Y %H:%M"
        try:
            return datetime.strptime(f"{raw_date} {raw_time}", fmt)
        except ValueError:
            pass
    m = DATE_RE.search(text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%m/%Y")
        except ValueError:
            return None
    return None


def parse_competence(text: str) -> date | None:
    """Parse ``MM/YYYY`` into the first day of that month."""
    m = COMPETENCE_RE.search(text)
    if not m:
        return None
    try:
        month, year = m.group(1).split("/")
        return date(int(year), int(month), 1)
    except ValueError:
        return None


def first_cnpj(text: str) -> str | None:
    m = CNPJ_RE.search(text)
    if not m:
        return None
    return _format_cnpj(digits_only(m.group(1)))


def first_cpf_or_cnpj(text: str) -> str | None:
    m = CNPJ_RE.search(text)
    if m:
        digits = digits_only(m.group(1))
        if len(digits) == 14:
            return _format_cnpj(digits)
    m = CPF_RE.search(text)
    if m:
        digits = digits_only(m.group(1))
        if len(digits) == 11:
            return _format_cpf(digits)
    return None


def _format_cnpj(digits: str) -> str:
    if len(digits) != 14:
        return digits
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _format_cpf(digits: str) -> str:
    if len(digits) != 11:
        return digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def section_between(
    text: str,
    start_headers: list[str],
    end_headers: list[str],
) -> str | None:
    """Return the slice of ``text`` between the first hit of ``start_headers``
    and the first subsequent hit of any ``end_headers``.

    Matching is ASCII-folded + uppercase to tolerate OCR diacritic noise.
    """
    upper = normalize_for_match(text)
    start_idx = -1
    for header in start_headers:
        idx = upper.find(normalize_for_match(header))
        if idx != -1 and (start_idx == -1 or idx < start_idx):
            start_idx = idx
    if start_idx == -1:
        return None

    end_idx = len(text)
    for header in end_headers:
        idx = upper.find(normalize_for_match(header), start_idx + 1)
        if idx != -1 and idx < end_idx:
            end_idx = idx
    return text[start_idx:end_idx]
