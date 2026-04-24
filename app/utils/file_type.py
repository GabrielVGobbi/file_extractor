"""File type detection using magic bytes + filename fallback.

``python-magic`` is preferred when available (depends on libmagic1 on Linux
and the bundled DLLs on Windows via ``python-magic-bin``). If the native
library is missing we fall back to ``mimetypes`` + a small magic-bytes
sniffer that covers every format the extractor supports.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:  # pragma: no cover - import side effect depends on platform
    import magic as _magic  # type: ignore
except Exception:  # pragma: no cover
    _magic = None


Category = Literal["pdf", "image", "xml", "docx", "unknown"]


@dataclass(frozen=True)
class DetectedFile:
    """Result of the file sniffing routine."""

    mimetype: str
    category: Category
    extension: str


_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),  # second-level check below
    (b"PK\x03\x04", "application/zip"),  # DOCX is a zip
)


def _sniff_magic(data: bytes) -> str | None:
    if not data:
        return None
    for sig, mime in _SIGNATURES:
        if data.startswith(sig):
            if mime == "image/webp" and b"WEBP" not in data[:16]:
                continue
            return mime
    stripped = data.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        return "application/xml"
    return None


def _categorize(mimetype: str) -> Category:
    if mimetype == "application/pdf":
        return "pdf"
    if mimetype.startswith("image/"):
        return "image"
    if mimetype in {"text/xml", "application/xml"}:
        return "xml"
    if mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "docx"
    if mimetype == "application/zip":
        # DOCX is a zip under the hood — require the filename hint to disambiguate.
        return "docx"
    return "unknown"


def detect_file(data: bytes, filename: str | None = None) -> DetectedFile:
    """Detect mimetype and category from a byte buffer + optional filename.

    The filename is used only as a disambiguator (e.g. ``.docx`` vs ``.zip``).
    """
    # Cheap magic-bytes sniff first — handles every format we support and is
    # deterministic across OSes. ``python-magic`` is only used to disambiguate
    # edge cases the sniffer could not identify.
    mimetype: str | None = _sniff_magic(data[:4096])

    if not mimetype and _magic is not None:
        try:
            mimetype = _magic.from_buffer(data[:4096], mime=True)
        except Exception:  # pragma: no cover
            mimetype = None
        if mimetype in {"application/octet-stream", ""}:
            mimetype = None

    extension = Path(filename).suffix.lower() if filename else ""

    if not mimetype and extension:
        guessed, _ = mimetypes.guess_type(filename or "")
        mimetype = guessed

    if mimetype == "application/zip" and extension == ".docx":
        mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    if not mimetype:
        mimetype = "application/octet-stream"

    return DetectedFile(mimetype=mimetype, category=_categorize(mimetype), extension=extension)
