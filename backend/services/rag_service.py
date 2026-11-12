# Prepares a document for search: splits the text into chunks of 800 characters, turns each chunk into a vector, saves it in MongoDB, and copies the document’s access rules onto every chunk.

import logging

from typing import Union
from uuid import uuid4
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import HTTPException

from database.connection import (
    documents_collection,
    documents_chunk_collection,
)
from services import storage_service
from services.embedding_service import get_embedding
from services.graph_service import sync_document_to_graph
from services.pdf_service import read_pdf, sha256_hex


load_dotenv()

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

#-------------------------------------------------------------------------------------------------------------

def chunk_access_fields(document: dict) -> dict:
    """Copy document access permissions to each chunk.

    `classification` and `department_code` are required by the vector-search permission filter
    (services/access/policy.py): without them a chunk is only visible through explicit grants.
    """
    access = document.get("access") or {}

    return {
        "classification": document.get("classification", "restricted"),
        "department_code": document.get("department_code"),
        "access": access, #access is a dictionary that contains the access permissions for the document. 
        "allowed_roles": access.get("roles", []),
        "allowed_departments": access.get("departments", []),
        "allowed_users": access.get("users", []),
    }

#-------------------------------------------------------------------------------------------------------------

def load_document_bytes(document: dict) -> tuple: #fetch the pdf from r2
    """Return a document's bytes and file name from private R2 storage."""

    object_key = document.get("object_key")

    if object_key:
        return storage_service.get_pdf_bytes(object_key), document.get("document_name") or "document.pdf"

    raise HTTPException(
        status_code=400,
        detail="This document has no R2 object. Upload it again.",
    )

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

    except Exception:
        logger.exception("Graph sync failed for %s", document["document_uuid"])

        # Neo4j error text can contain query and host details: it stays in the log.
        error = "Graph sync failed. Check the backend logs."

        documents_collection.update_one(
            {"document_uuid": document["document_uuid"]},
            {
                "$set": {
                    "graph_sync_status": "failed",
                    "graph_sync_error": error,
                }
            },
        )

        return {
            "graph_sync_status": "failed",
            "graph_sync_error": error,
        }

#-------------------------------------------------------------------------------------------------------------

def _mark_failed(document_uuid: str, reason: str) -> None:
    documents_collection.update_one(
        {"document_uuid": document_uuid},
        {
            "$set": {
                "status": "failed",
                "ingestion_error": str(reason)[:500],
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

#-------------------------------------------------------------------------------------------------------------

def ingest_document(document: Union[dict, str]): #it accepts either a document dictionary or a document UUID string as input. 
    """
    it uses the document's UUID to retrieve
    Process a PDF document:
    1. Load its bytes from private R2 storage.
    2. Check whether the content has changed.
    3. Split its text into chunks.
    4. Generate embeddings and save chunks in MongoDB.
    5. Synchronize the document and chunks with Neo4j.
    """

    if isinstance(document, str): #checks if the input is a string
        found = documents_collection.find_one({"document_uuid": document})
        if not found:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document}' was not found in the database.",
            )
        document = dict(found) #convert the found document from the database into a dictionary format

    document_uuid = document.get("document_uuid")

    if not document_uuid:
        raise HTTPException(
            status_code=400,
            detail="document_uuid is required.",
        )

    # The stored record is the source of truth for access fields and the storage location.
    existing_document = documents_collection.find_one(
        {"document_uuid": document_uuid}
    )

    if existing_document:
        document = {**document, **existing_document}#It merges two dictionaries. checks the new document dictionary with the existing one from the database, giving priority to the existing document's

    data, file_name = load_document_bytes(document) #fetches the PDF bytes and file name from private R2 storage 
    file_hash = sha256_hex(data) #bytes of pdf are hashed using SHA-256
    document["file_hash"] = file_hash #it checks the documet file hash with the existing one in the database 

    # Even if the file is unchanged, synchronize its existing MongoDB chunks to Neo4j.
    if (#Check whether ingestion is already completed
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
        # Imported here so the API starts without the text-splitter package loaded.
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        content = read_pdf(data, extract_text=True)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
        )

        # Page numbers are 1-based, create the langchain Document objects with metadata for each page.
        split_chunks = splitter.create_documents(
            content.pages,
            metadatas=[{"page": index + 1} for index in range(len(content.pages))],
        )

        pieces = [
            (chunk.page_content.strip(), chunk.metadata.get("page"))
            for chunk in split_chunks
            if chunk.page_content.strip()
        ]
        # pieces = [
        #     ("Employees must follow company policies...", 1),
        #     ("Leave applications must be submitted...", 1),
        #     ("The HR department manages employee records...", 2)
        # ]

        if not pieces:
            raise HTTPException(
                status_code=422,
                detail="No readable text found in the PDF. Scanned (image-only) PDFs are not supported yet.",
            )

        # One batched call is much faster than embedding chunk by chunk.
        vectors = get_embedding().embed_documents([text for text, _ in pieces]) 

        access_fields = chunk_access_fields(document)
        created_at = datetime.now(timezone.utc)
        source_name = document.get("document_name") or file_name

        chunk_records = [ #it is list comprehension that creates a list of dictionaries, where each dictionary represents a chunk of text extracted from the PDF document
            {
                "chunk_uuid": str(uuid4()),
                "document_uuid": document_uuid,
                "text": text,
                "source": source_name,
                "page": page,
                "file_hash": file_hash,
                "embedding": vector,
                "created_at": created_at,
                **access_fields,
            }
            for (text, page), vector in zip(pieces, vectors)
        ]

        # Save the document's processing status and metadata.
        documents_collection.update_one(
            {"document_uuid": document_uuid},
            {
                "$set": {
                    "document_name": source_name,
                    "file_hash": file_hash,
                    "page_count": content.page_count,
                    "status": "processing",
                    "ingestion_error": None,
                    "updated_at": created_at,
                },
                "$setOnInsert": { #These fields are set only if MongoDB creates a new document.
                    "document_uuid": document_uuid,
                    "created_at": created_at,
                },
            },
            upsert=True, #If the document exists → update it.If the document doesn't exist → insert a new one.
        )

        # Replace the previous chunks only after extraction and embedding both succeeded.
        documents_chunk_collection.delete_many(
            {"document_uuid": document_uuid}
        )
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
                    "chunk_count": len(chunk_records),
                    "processed_at": datetime.now(timezone.utc),
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

    except HTTPException as exc:
        _mark_failed(document_uuid, exc.detail)
        raise

    except Exception as exc:
        logger.exception("Ingestion failed for %s", document_uuid)  # full detail stays in the backend logs
        _mark_failed(document_uuid, "Document ingestion failed.")

        raise HTTPException(
            status_code=500,
            detail="Document ingestion failed. Check the backend logs.",
        ) from exc
