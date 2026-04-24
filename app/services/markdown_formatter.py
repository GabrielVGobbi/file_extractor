"""Render the raw text extracted from a document as lightweight markdown.

The goal is *not* to beautify — callers who ask for this format want the
unadulterated OCR text to feed their own pipeline. We only:

* strip trailing whitespace per line,
* collapse >2 blank lines in a row,
* promote plain-text section headers (``ALL CAPS`` lines) to ``##``.
"""

from __future__ import annotations

import re

_HEADER_LINE = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9 ,.:;/()\-—+%$R\$°ºª'\"]{6,}$")


def to_markdown(text: str, *, title: str | None = None) -> str:
    if not text:
        return title or ""

    lines = text.splitlines()
    out: list[str] = []
    if title:
        out.append(f"# {title.strip()}")
        out.append("")

    blank_streak = 0
    for raw in lines:
        line = raw.rstrip()
        if not line:
            blank_streak += 1
            if blank_streak <= 1:
                out.append("")
            continue
        blank_streak = 0

        stripped = line.strip()
        if _HEADER_LINE.match(stripped) and 3 <= len(stripped.split()) <= 10:
            out.append(f"## {stripped}")
        else:
            out.append(line)

    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out) + "\n"
