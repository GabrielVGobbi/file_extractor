"""FastAPI application entrypoint."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import extract, health, jobs
from app.config import get_settings
from app.utils.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)
    logger.info(
        "app_start",
        env=settings.app_env,
        version=__version__,
        ocr_engine=settings.ocr_engine,
        celery=settings.enable_celery,
        poppler_path=settings.poppler_path,
        poppler_ok=settings.poppler_ok,
        tesseract_ok=settings.tesseract_ok,
    )
    if settings.poppler_path and not settings.poppler_ok:
        logger.warning(
            "poppler_missing",
            poppler_path=settings.poppler_path,
            hint=(
                "pdfinfo not found under POPPLER_PATH. Scanned-PDF and image "
                "extraction will fail. Download Poppler from "
                "https://github.com/oschwartz10612/poppler-windows/releases and "
                "point POPPLER_PATH at the folder containing pdfinfo.exe."
            ),
        )
    if os.name == "nt" and settings.tesseract_cmd and not settings.tesseract_ok:
        logger.warning(
            "tesseract_missing",
            tesseract_cmd=settings.tesseract_cmd,
            hint=(
                "tesseract.exe not found at TESSERACT_CMD. Install from "
                "https://github.com/UB-Mannheim/tesseract/wiki and update the "
                "path in .env."
            ),
        )
    yield
    logger.info("app_stop")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Fiscal Document Extractor API",
        version=__version__,
        description=(
            "Serviço standalone que extrai dados de documentos brasileiros "
            "(NF-e, NFS-e, contas de consumo, locação, boletos e faturas) "
            "e devolve JSON estruturado para controladoria fiscal e ERP."
        ),
        lifespan=lifespan,
        debug=settings.app_debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(extract.router)
    app.include_router(jobs.router)

    return app


app = create_app()
