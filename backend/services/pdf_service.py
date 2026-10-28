"""Validate PDFs and read their text and metadata from bytes (no file on disk needed)."""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO

from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------------

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB") or 25)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# The PDF header must appear within the first 1024 bytes (PDF spec).
PDF_MAGIC = b"%PDF-"

#-------------------------------------------------------------------------------------

@dataclass
class PdfContent:
    page_count: int
    metadata: dict
    # One entry per page, in order (1-based page = index + 1). Empty when text was not requested.
    pages: list = field(default_factory=list)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _as_utc(value):
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _clean_text(value, limit: int = 300):
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] or None


def read_pdf(data: bytes, extract_text: bool = True) -> PdfContent:
    """Check the bytes really are a readable, unencrypted PDF within the size limit, then read it."""

    if not data:
        raise HTTPException(status_code=422, detail="The file is empty.")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"The file is larger than {MAX_UPLOAD_MB} MB.")

    if PDF_MAGIC not in data[:1024]:
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))

        if reader.is_encrypted:
            # Owner-password-only PDFs open with an empty password; real passwords are rejected.
            try:
                opened = reader.decrypt("")
            except Exception:
                opened = 0
            if not opened:
                raise HTTPException(status_code=422, detail="Password-protected PDFs are not supported.")

        page_count = len(reader.pages)

    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Unreadable PDF: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=422, detail="The PDF file is damaged or unreadable.") from exc

    if page_count == 0:
        raise HTTPException(status_code=422, detail="The PDF has no pages.")

    metadata = {"title": None, "author": None, "created_at": None}

    try:
        info = reader.metadata
        if info:
            metadata = {
                "title": _clean_text(info.title),
                "author": _clean_text(info.author),
                "created_at": _as_utc(info.creation_date),
            }
    except Exception:  # metadata is optional; a broken info dictionary must not block the upload
        pass

    pages = []

    if extract_text:
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                logger.warning("Could not extract text from a page: %s", exc)
                pages.append("")

    return PdfContent(page_count=page_count, metadata=metadata, pages=pages)
