"""Ingestion: PDF -> chunks -> embeddings, stored with a copy of the document's access fields."""

import hashlib
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import HTTPException

from database.connection import documents_chunk_collection, documents_collection
from services.embedding_service import get_embedding

load_dotenv()

#-------------------------------------------------------------------------------------

DOCUMENTS_ROOT_VALUE = os.getenv("DOCUMENTS_ROOT", "").strip()
DOCUMENTS_ROOT = Path(DOCUMENTS_ROOT_VALUE).resolve() if DOCUMENTS_ROOT_VALUE else None

ACCESS_FIELDS = ("classification", "department_code", "access")


def chunk_access_fields(document: dict) -> dict:
    """The access fields a chunk must carry (copied from its document)."""

    return {
        "classification": document.get("classification", "restricted"),
        "department_code": document.get("department_code"),
        "access": document.get("access") or {"departments": [], "roles": [], "users": []},
    }


def calculate_file_hash(file_path: Path) -> str:
    """SHA-256 of the actual file contents."""

    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def validate_document_path(file_path: str) -> Path:
    """Allow only existing PDFs inside the approved document directory."""

    if DOCUMENTS_ROOT is None or not DOCUMENTS_ROOT.is_dir():
        raise HTTPException(status_code=500, detail="DOCUMENTS_ROOT is not configured correctly.")

    try:
        path = Path(file_path).resolve(strict=True)
        path.relative_to(DOCUMENTS_ROOT)
    except (ValueError, OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Document path is outside the approved directory.")

    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only existing PDF files are supported.")

    return path

#-------------------------------------------------------------------------------------

def ingest_document(document_uuid: str) -> dict:
    """Create and store chunks and embeddings for one registered PDF."""

    document = documents_collection.find_one({"document_uuid": document_uuid}, {"_id": 0})

    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    path = validate_document_path(document["file_path"])
    file_hash = calculate_file_hash(path)

    # Skip files whose content has already been processed.
    if document.get("file_hash") == file_hash and document.get("status") == "completed":
        return {
            "message": "Document is already up to date.",
            "document_uuid": document_uuid,
            "chunk_count": documents_chunk_collection.count_documents({"document_uuid": document_uuid}),
        }

    now = datetime.now(timezone.utc)

    documents_collection.update_one(
        {"document_uuid": document_uuid},
        {"$set": {"status": "processing", "processing_error": None}},
    )

    try:
        # Imported here so the API starts without the PDF/LangChain packages installed.
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        pages = PyPDFLoader(str(path)).load()

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150, length_function=len)
        split_documents = [c for c in splitter.split_documents(pages) if c.page_content.strip()]

        if not split_documents:
            raise ValueError("No readable text was extracted from PDF.")

        vectors = get_embedding().embed_documents([c.page_content for c in split_documents])

        access = chunk_access_fields(document)

        chunk_records = [
            {
                "chunk_uuid": str(uuid4()),
                "document_uuid": document_uuid,
                "text": chunk.page_content,
                "source": document["document_name"],
                "file_path": str(path),
                # PyPDFLoader uses zero-based page numbers.
                "page": chunk.metadata.get("page", 0) + 1,
                "file_hash": file_hash,
                **access,
                "embedding": vector,
                "created_at": now,
            }
            for chunk, vector in zip(split_documents, vectors)
        ]

        # Replace previous chunks only after extraction and embedding both succeeded.
        documents_chunk_collection.delete_many({"document_uuid": document_uuid})
        documents_chunk_collection.insert_many(chunk_records)

        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {"$set": {
                "file_hash": file_hash,
                "status": "completed",
                "processing_error": None,
                "chunk_count": len(chunk_records),
                "processed_at": now,
            }},
        )

        return {
            "message": "Document ingested successfully.",
            "document_uuid": document_uuid,
            "document_name": document["document_name"],
            "chunk_count": len(chunk_records),
        }

    except Exception as exc:
        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {"$set": {"status": "failed", "processing_error": str(exc)[:500]}},
        )

        traceback.print_exc()  # full detail stays in backend logs

        raise HTTPException(status_code=500, detail="Document ingestion failed. Check backend logs.") from exc
