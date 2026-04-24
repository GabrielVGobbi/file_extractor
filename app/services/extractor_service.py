"""Core orchestration with a 3-layer cost-aware pipeline.

Layers, cheapest first::

    1. Cache (sha256)                     $0
    2. Deterministic parsers              $0
       - XML (NF-e / NFS-e ABRASF)
       - Regex heuristics on OCR text
    3. LLM (Anthropic Claude)             $$   ← last resort

Each extraction emits an ``extraction_method`` tag so callers can track
how many requests actually reach the paid LLM.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError

from app.config import Settings
from app.extractors import router as extractor_router
from app.extractors.heuristic import try_heuristic_extract
from app.llm.client import AnthropicExtractor, LLMExtractionError
from app.schemas.fiscal import ExtractionMetadata, FiscalDocumentData
from app.schemas.response import ErrorResponse, ExtractionResponse
from app.services.cache import ExtractionCache
from app.utils.file_type import detect_file
from app.utils.logging import get_logger
from app.validators.confidence import (
    build_warnings,
    missing_required_fields,
    score,
)
from app.validators.currency import MONEY_FIELDS, normalize_money_fields

logger = get_logger(__name__)


Strategy = Literal["auto", "no_llm", "force_llm", "cache_only"]


class ExtractionServiceError(RuntimeError):
    """Raised when the pipeline cannot produce a usable response."""

    def __init__(self, error: ErrorResponse) -> None:
        super().__init__(error.message)
        self.error = error


class ExtractorService:
    """High-level façade used by the HTTP routes and Celery tasks."""

    def __init__(
        self,
        settings: Settings,
        llm: AnthropicExtractor | None = None,
        cache: ExtractionCache | None = None,
    ) -> None:
        self._settings = settings
        self._llm = llm
        self._cache = cache or ExtractionCache(
            settings.cache_dir, enabled=settings.enable_cache
        )

    def _get_llm(self) -> AnthropicExtractor:
        if self._llm is None:
            self._llm = AnthropicExtractor(self._settings)
        return self._llm

    def extract(
        self,
        *,
        file_bytes: bytes,
        filename: str | None,
        document_type: str = "auto",
        direction: str = "auto",
        organization_id: str | None = None,
        branch_id: str | None = None,
        strategy: Strategy = "auto",
    ) -> ExtractionResponse:
        """Run the pipeline and return a validated response.

        ``strategy`` controls which layers are allowed:

        * ``auto`` (default): cache → heuristic → LLM
        * ``no_llm``: cache → heuristic (fails if heuristic falls short)
        * ``force_llm``: skip heuristic, still writes cache
        * ``cache_only``: cache only, 404-ish if miss
        """
        self._validate_input(file_bytes)

        cache_key = ExtractionCache.key_for(file_bytes)
        if strategy != "force_llm":
            cached = self._cache.get(cache_key)
            if cached:
                return self._response_from_cache(cached)
        if strategy == "cache_only":
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="CACHE_MISS",
                    message="No cached extraction for this file.",
                )
            )

        detected = detect_file(file_bytes, filename)
        if (
            detected.mimetype not in self._settings.accepted_mimetypes_set
            and detected.category == "unknown"
        ):
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="UNSUPPORTED_FILE_TYPE",
                    message=f"Unsupported file type: {detected.mimetype}",
                )
            )

        logger.info(
            "extraction_start",
            filename=filename,
            mimetype=detected.mimetype,
            category=detected.category,
            size=len(file_bytes),
            strategy=strategy,
        )

        try:
            routed = extractor_router.route(file_bytes, detected, self._settings)
        except ValueError as exc:
            raise ExtractionServiceError(
                ErrorResponse(error_code="PARSE_FAILED", message=str(exc))
            ) from exc
        except Exception as exc:
            from app.extractors.ocr.tesseract import OCRDependencyError

            if isinstance(exc, OCRDependencyError):
                raise ExtractionServiceError(
                    ErrorResponse(
                        error_code="OCR_DEPENDENCY_MISSING",
                        message=str(exc),
                    )
                ) from exc
            raise

        raw_data: dict[str, Any]
        extraction_method: str
        text_for_llm: str | None = None
        ocr_warnings: list[str] = []

        # ------------------------------------------------------------------
        # Layer 1b — XML (structured, zero-cost)
        # ------------------------------------------------------------------
        if routed.stage == "structured" and routed.structured_data is not None:
            raw_data = routed.structured_data
            extraction_method = "xml_parser"
        else:
            assert routed.extracted is not None
            if routed.extracted.is_empty:
                raise ExtractionServiceError(
                    ErrorResponse(
                        error_code="EMPTY_EXTRACTED_TEXT",
                        message="Could not extract any text from the document.",
                    )
                )
            ocr_warnings = list(routed.extracted.warnings)
            text_for_llm = routed.extracted.text
            is_ocr = routed.extracted.source == "ocr"

            # ------------------------------------------------------------------
            # Layer 2 — Deterministic regex heuristics
            # ------------------------------------------------------------------
            heuristic_payload: dict[str, Any] | None = None
            if self._settings.enable_heuristic and strategy != "force_llm":
                heuristic = try_heuristic_extract(
                    text_for_llm,
                    hint_type=document_type,
                    min_confidence=self._settings.heuristic_min_confidence,
                )
                if heuristic:
                    heuristic_payload = heuristic.payload
                    logger.info(
                        "heuristic_hit",
                        parser=heuristic.parser,
                        confidence=heuristic.confidence,
                    )

            if heuristic_payload is not None:
                raw_data = heuristic_payload
                extraction_method = "ocr+heuristic" if is_ocr else "heuristic"
            else:
                # ------------------------------------------------------------------
                # Layer 3 — LLM fallback
                # ------------------------------------------------------------------
                if strategy == "no_llm" or self._settings.disable_llm_fallback:
                    raise ExtractionServiceError(
                        ErrorResponse(
                            error_code="HEURISTIC_INSUFFICIENT",
                            message=(
                                "Deterministic parsers could not extract enough "
                                "fields and LLM fallback is disabled."
                            ),
                        )
                    )
                try:
                    llm_result = self._get_llm().extract(
                        text_for_llm, hint_type=document_type
                    )
                except LLMExtractionError as exc:
                    raise ExtractionServiceError(
                        ErrorResponse(error_code="LLM_EXTRACTION_FAILED", message=str(exc))
                    ) from exc
                raw_data = llm_result.payload
                extraction_method = "ocr+llm" if is_ocr else "llm"

        raw_data = normalize_money_fields(dict(raw_data), MONEY_FIELDS)

        if direction != "auto" and not raw_data.get("direction"):
            raw_data["direction"] = direction

        confidence = (
            1.0 if extraction_method == "xml_parser" else round(score(raw_data), 2)
        )
        missing = missing_required_fields(raw_data)
        warnings = build_warnings(raw_data) + ocr_warnings

        raw_data["metadata"] = {
            "extraction_method": extraction_method,
            "confidence": confidence,
            "extracted_at": datetime.now(UTC).isoformat(),
        }

        try:
            model = FiscalDocumentData.model_validate(raw_data)
        except ValidationError as exc:
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="SCHEMA_VALIDATION_FAILED",
                    message="Extracted data does not match the fiscal schema.",
                    partial_data={"errors": exc.errors(), "raw": raw_data},
                )
            ) from exc

        model.metadata = ExtractionMetadata(
            extraction_method=extraction_method,  # type: ignore[arg-type]
            confidence=confidence,
            extracted_at=datetime.now(UTC),
        )

        if missing:
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="EXTRACTION_FAILED",
                    message=(
                        "Não foi possível identificar campos obrigatórios: "
                        + ", ".join(missing)
                    ),
                    partial_data=model.model_dump(mode="json"),
                )
            )

        status = (
            "partial" if confidence < self._settings.confidence_threshold else "success"
        )

        if organization_id:
            warnings.append(f"organization_id={organization_id}")
        if branch_id:
            warnings.append(f"branch_id={branch_id}")

        response = ExtractionResponse(
            status=status,  # type: ignore[arg-type]
            confidence=confidence,
            extraction_method=extraction_method,  # type: ignore[arg-type]
            missing_fields=missing,
            warnings=warnings,
            data=model,
        )

        # Only cache "good" extractions — anything below threshold is
        # potentially wrong and would poison the cache.
        if status == "success":
            self._cache.set(cache_key, response.model_dump(mode="json"))

        logger.info(
            "extraction_complete",
            method=extraction_method,
            confidence=confidence,
            status=status,
            cache_key=cache_key[:12],
        )

        return response

    def extract_text(
        self,
        *,
        file_bytes: bytes,
        filename: str | None,
    ) -> tuple[str, str]:
        """Return ``(raw_text, source)`` where ``source`` is ``text`` | ``ocr``
        | ``xml`` | ``docx``. Used by the ``markdown`` output mode.
        """
        self._validate_input(file_bytes)
        detected = detect_file(file_bytes, filename)

        if detected.category == "xml":
            return file_bytes.decode("utf-8", errors="replace"), "xml"

        routed = extractor_router.route(file_bytes, detected, self._settings)
        if routed.extracted is not None:
            return routed.extracted.text, routed.extracted.source
        # Structured-only (shouldn't happen outside XML):
        return "", "structured"

    def _validate_input(self, file_bytes: bytes) -> None:
        if not file_bytes:
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="EMPTY_FILE",
                    message="Uploaded file is empty.",
                )
            )
        if len(file_bytes) > self._settings.max_file_size_bytes:
            raise ExtractionServiceError(
                ErrorResponse(
                    error_code="FILE_TOO_LARGE",
                    message=(
                        f"File exceeds the {self._settings.max_file_size_mb} MB limit."
                    ),
                )
            )

    def _response_from_cache(self, payload: dict[str, Any]) -> ExtractionResponse:
        """Rehydrate a cached JSON payload and retag it as ``cache``."""
        payload = dict(payload)
        payload["extraction_method"] = "cache"
        data = payload.get("data") or {}
        if isinstance(data, dict):
            metadata = dict(data.get("metadata") or {})
            metadata["extraction_method"] = "cache"
            data["metadata"] = metadata
            payload["data"] = data
        return ExtractionResponse.model_validate(payload)
