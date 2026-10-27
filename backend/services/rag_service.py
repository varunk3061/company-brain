import os
import hashlib
import traceback


from typing import Union
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from database.connection import (
    documents_collection,
    documents_chunk_collection,
)
from services.embedding_service import get_embedding
from services.graph_service import sync_document_to_graph


load_dotenv()

DOCUMENTS_ROOT = os.getenv("DOCUMENTS_ROOT")

#-------------------------------------------------------------------------------------------------------------

def chunk_access_fields(document: dict) -> dict:
    """Copy document access permissions to each chunk."""
    access = document.get("access") or {}

    return {
        "access": access,
        "allowed_roles": access.get("roles", []),
        "allowed_departments": access.get("departments", []),
        "allowed_users": access.get("users", []),
    }

#-------------------------------------------------------------------------------------------------------------

def calculate_file_hash(file_path: str) -> str:
    """Calculate a SHA-256 hash to detect file changes."""
    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(8192), b""):
            sha256.update(block)

    return sha256.hexdigest()

#-------------------------------------------------------------------------------------------------------------

def validate_document_path(file_path: str) -> Path:
    """Validate that the document exists and is a PDF."""
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document file not found: {path}",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail="The provided path is not a file.",
        )

    if path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF documents are supported.",
        )

    return path

#-------------------------------------------------------------------------------------------------------------

def sync_document_graph(document: dict, chunks: list) -> dict:
    """Synchronize a document and its chunks with Neo4j."""
    try:
        sync_document_to_graph(document, chunks)

        documents_collection.update_one(
            {"document_uuid": document["document_uuid"]},
            {
                "$set": {
                    "graph_sync_status": "indexed",
                    "graph_sync_error": None,
                }
            },
        )

        return {
            "graph_sync_status": "indexed",
        }

    except Exception as exc:
        traceback.print_exc()

        documents_collection.update_one(
            {"document_uuid": document["document_uuid"]},
            {
                "$set": {
                    "graph_sync_status": "failed",
                    "graph_sync_error": str(exc),
                }
            },
        )

        return {
            "graph_sync_status": "failed",
            "graph_sync_error": str(exc),
        }

#-------------------------------------------------------------------------------------------------------------

def ingest_document(document: Union[dict, str]):
    """
    Process a PDF document:
    1. Validate its path.
    2. Check whether the file has changed.
    3. Split its content into chunks.
    4. Generate embeddings and save chunks in MongoDB.
    5. Synchronize the document and chunks with Neo4j.
    """

    if isinstance(document, str):
        found = documents_collection.find_one({"document_uuid": document})
        if not found:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document}' was not found in the database.",
            )
        document = dict(found)

    document_uuid = document.get("document_uuid")
    file_path = document.get("file_path")

    if not document_uuid:
        raise HTTPException(
            status_code=400,
            detail="document_uuid is required.",
        )

    if not file_path:
        raise HTTPException(
            status_code=400,
            detail="file_path is required.",
        )

    path = validate_document_path(file_path)
    file_hash = calculate_file_hash(str(path))

    # Keep the stored document metadata up to date.
    document["file_path"] = str(path)
    document["file_hash"] = file_hash

    existing_document = documents_collection.find_one(
        {"document_uuid": document_uuid}
    )

    if existing_document:
        document.update(existing_document)
        document["file_path"] = str(path)
        document["file_hash"] = file_hash

    # IMPORTANT:
    # Even if the file is unchanged, synchronize its existing MongoDB
    # chunks to Neo4j. Previously, this early return skipped graph sync.
    if (
        existing_document
        and existing_document.get("file_hash") == file_hash
        and existing_document.get("status") == "completed"
    ):
        existing_chunks = list(
            documents_chunk_collection.find(
                {"document_uuid": document_uuid}
            )
        )

        graph_result = sync_document_graph(
            existing_document,
            existing_chunks,
        )

        return {
            "message": "Document is already up to date.",
            "document_uuid": document_uuid,
            "chunk_count": len(existing_chunks),
            **graph_result,
        }

    try:
        # Load PDF pages.
        loader = PyPDFLoader(str(path))
        pages = loader.load()

        # Split the document into manageable chunks.
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            length_function=len,
        )

        split_chunks = splitter.split_documents(pages)

        if not split_chunks:
            raise HTTPException(
                status_code=400,
                detail="No readable text found in the PDF.",
            )

        access_fields = chunk_access_fields(document)
        created_at = datetime.now(timezone.utc)

        # Remove old chunks before saving the newly processed version.
        documents_chunk_collection.delete_many(
            {"document_uuid": document_uuid}
        )

        chunk_records = []

        for chunk in split_chunks:
            text_content = chunk.page_content.strip()

            if not text_content:
                continue

            # Generate a vector embedding for the chunk.
            embedding = get_embedding(text_content)

            # PyPDFLoader uses zero-based page metadata.
            page_number = chunk.metadata.get("page", 0) + 1

            chunk_record = {
                "chunk_uuid": str(uuid4()),
                "document_uuid": document_uuid,
                "text": text_content,
                "source": path.name,
                "file_path": str(path),
                "page": page_number,
                "file_hash": file_hash,
                "embedding": embedding,
                "created_at": created_at,
                **access_fields,
            }

            chunk_records.append(chunk_record)

        if not chunk_records:
            raise HTTPException(
                status_code=400,
                detail="No valid text chunks could be created.",
            )

        # Save the document's processing status and metadata.
        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {
                "$set": {
                    "document_name": document.get(
                        "document_name", path.name
                    ),
                    "file_path": str(path),
                    "file_hash": file_hash,
                    "status": "processing",
                    "updated_at": created_at,
                },
                "$setOnInsert": {
                    "document_uuid": document_uuid,
                    "created_at": created_at,
                },
            },
            upsert=True,
        )

        # Store all generated chunks in MongoDB.
        documents_chunk_collection.insert_many(chunk_records)

        # Prepare the latest document metadata for Neo4j.
        graph_document = documents_collection.find_one(
            {"document_uuid": document_uuid}
        )

        if not graph_document:
            raise RuntimeError(
                "Document metadata was not found after saving."
            )

        # Sync document and chunks to Neo4j.
        graph_result = sync_document_graph(
            graph_document,
            chunk_records,
        )

        # Mark ingestion complete. A graph failure is recorded separately
        # so you can retry graph synchronization without losing that status.
        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {
                "$set": {
                    "status": "completed",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        return {
            "message": "Document ingested successfully.",
            "document_uuid": document_uuid,
            "chunk_count": len(chunk_records),
            **graph_result,
        }

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()

        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {
                "$set": {
                    "status": "failed",
                    "ingestion_error": str(exc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        raise HTTPException(
            status_code=500,
            detail=f"Document ingestion failed: {str(exc)}",
        ) from exc
