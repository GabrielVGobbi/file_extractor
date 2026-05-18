"""Deterministic, LLM-free extraction from plain text.

The :func:`try_heuristic_extract` entry point tries a cascade of
layout-specific parsers (NFS-e ABRASF today; more can be registered) and
returns the first payload whose confidence clears the configured
threshold. When every parser fails or under-performs, it returns
``None`` and the caller falls back to the LLM path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extractors.heuristic import nfse_abrasf, nfse_saopaulo
from app.validators.confidence import score


@dataclass
class HeuristicResult:
    payload: dict[str, Any]
    parser: str
    confidence: float


PARSERS = [
    # More specific layout first — SP NFS-e has a distinct column structure
    ("nfse_saopaulo", nfse_saopaulo.parse),
    ("nfse_abrasf", nfse_abrasf.parse),
]


def try_heuristic_extract(
    text: str,
    *,
    hint_type: str | None = None,
    min_confidence: float = 0.70,
) -> HeuristicResult | None:
    """Run every registered parser and return the best payload above threshold.

    Parsers are expected to be *conservative*: they must return ``None``
    when the input doesn't look like the layout they understand.
    """
    text = (text or "").strip()
    if not text:
        return None

    best: HeuristicResult | None = None
    for name, parser in PARSERS:
        try:
            payload = parser(text, hint_type=hint_type)
        except Exception:  # noqa: BLE001 - heuristics must never crash the pipeline
            continue
        if not payload:
            continue
        confidence = score(payload)
        if best is None or confidence > best.confidence:
            best = HeuristicResult(payload=payload, parser=name, confidence=confidence)

    if best is None or best.confidence < min_confidence:
        return best if best and best.confidence >= 0.50 else None
    return best
