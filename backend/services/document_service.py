import logging
import os
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from database.connection import (
    departments_collection, documents_chunk_collection, documents_collection,
    roles_collection, users_collection,
)
from services import audit_service, storage_service
from services.access.policy import UserContext, build_document_filter, can_view
from services.pdf_service import MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, read_pdf, sha256_hex
from models.document_model import DocumentAccessUpdate

#-----------------------------------------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)

#-----------------------------------------------------------------------------------------------------------

# The only directory tree this API is allowed to scan 
# DOCUMENTS_ROOT = Path(
#     os.getenv("DOCUMENTS_ROOT", "")
# ).resolve()

DOCUMENTS_ROOT_VALUE = os.getenv("DOCUMENTS_ROOT", "").strip()

DOCUMENTS_ROOT = (
    Path(DOCUMENTS_ROOT_VALUE).resolve()
    if DOCUMENTS_ROOT_VALUE
    else None
)

#-----------------------------------------------------------------------------------------------------------

def validate_folder_path(folder_path: str):
    """Ensure the required folder is inside approved root."""

    if DOCUMENTS_ROOT is None:
        raise HTTPException(
            status_code=500,
            detail="DOCUMENTS_ROOT is not configured in .env."
        )

    if not DOCUMENTS_ROOT.is_dir():
        raise HTTPException(
            status_code=500,
            detail="DOCUMENTS_ROOT must point to an existing directory."
        )

    requested_path = Path(folder_path)

    if not requested_path.is_absolute():
        requested_path = DOCUMENTS_ROOT / requested_path

    try : 
        requested_path = requested_path.resolve(strict=True)
        requested_path.relative_to(DOCUMENTS_ROOT)
    except (ValueError, OSError, RuntimeError):
        raise HTTPException(
            status_code=400,
            detail="Folder must exist inside the approved documents root."
        )

    if not requested_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="The supplied path is not a directory."
        )

    return requested_path

#-----------------------------------------------------------------------------------------------------------

def scan_pdf_folder(folder_path: str):
    """Register PDF metadata in MongoDB"""

    folder = validate_folder_path(folder_path)

    created = []
    skipped = []
    errors = []

    # Search the selected folder and its subfolders.
    for pdf_path in folder.rglob("*"):
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            continue

        try :
            resolved_path = pdf_path.resolve(strict=True)
            resolved_path.relative_to(DOCUMENTS_ROOT)

            stat = resolved_path.stat()

            document_name = resolved_path.name
            file_path = os.path.normcase(str(resolved_path))

            # Use the file's actual modification time.
            last_update = datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc
            )

            existing = documents_collection.find_one(
                {"file_path": file_path},
                {"_id": 0, "document_uuid": 1}
            )

            if existing:
                # Do Not overwrite the admin's category or allowed roles.
                documents_collection.update_one(
                    {"file_path" : file_path},
                    {
                        "$set" : {
                            "document_name" : document_name,
                            "last_update" : last_update
                        }
                    }
                )

                skipped.append({
                    "document_name" : document_name,
                    "reason" : "Already registered; metadata checked"
                })
                continue

            document = {
                "document_uuid" : str(uuid.uuid4()),
                "document_name" : document_name,
                "category" : None,
                "last_update" : last_update,
                # Safe defaults for a freshly scanned file; an admin must classify it.
                "department_code" : None,
                "classification" : "internal",
                "access" : {"departments": [], "roles": [], "users": []},
                "needs_classification" : True,
                "file_path" : file_path
            }

            documents_collection.insert_one(document)

            created.append({
                "document_uuid" : document["document_uuid"],
                "document_name" : document_name
            })

        except DuplicateKeyError:
             # Another scan may have registered this file concurrently.
            skipped.append({
                "document_name": pdf_path.name,
                "reason": "Already registered"
            })

        except (OSError, PermissionError) as exc:
            errors.append({
                "document_name": pdf_path.name,
                "reason": str(exc)
            })

    return {
        "message": "Folder scan completed",
        "created_count": len(created),
        "existing_count": len(skipped),
        "error_count": len(errors),
        "created": created,
        "existing": skipped,
        "errors": errors
    }

#-----------------------------------------------------------------------------------------------------------

PUBLIC_FIELDS = {
    "_id": 0,
    "document_uuid": 1,
    "document_name": 1,
    "category": 1,
    "last_update": 1,
    "department_code": 1,
    "classification": 1,
    "access": 1,
    "needs_classification": 1,
    "size_bytes": 1,
    "page_count": 1,
    "status": 1,
    "chunk_count": 1,
}


def list_documents(ctx: UserContext):
    """Return documents the caller may see. Managers see all metadata (never content) for governance."""

    query = {} if ctx.has("documents.manage") else build_document_filter(ctx)

    return list(
        documents_collection.find(query, PUBLIC_FIELDS).sort("document_name", 1)
    )

#-----------------------------------------------------------------------------------------------------------

def update_document_access(document_uuid: str, data: DocumentAccessUpdate, actor: UserContext):
    """Set owner department, classification and explicit grants for a document."""

    if data.department_code is not None and not departments_collection.find_one(
        {"code": data.department_code, "status": "active"}
    ):
        raise HTTPException(status_code=422, detail="Unknown or inactive department.")

    grants = data.access

    unknown_departments = set(grants.departments) - {
        d["code"] for d in departments_collection.find({"code": {"$in": grants.departments}}, {"code": 1})
    }
    unknown_roles = set(grants.roles) - {
        r["code"] for r in roles_collection.find({"code": {"$in": grants.roles}}, {"code": 1})
    }
    unknown_users = set(grants.users) - {
        u["user_uuid"] for u in users_collection.find({"user_uuid": {"$in": grants.users}}, {"user_uuid": 1})
    }

    if unknown_departments or unknown_roles or unknown_users:
        raise HTTPException(status_code=422, detail="Access list contains unknown departments, roles or users.")

    before = documents_collection.find_one({"document_uuid": document_uuid}, PUBLIC_FIELDS)

    if not before:
        raise HTTPException(status_code=404, detail="Document not found.")

    after = {
        "department_code": data.department_code,
        "classification": data.classification,
        "access": {
            "departments": list(dict.fromkeys(grants.departments)),
            "roles": list(dict.fromkeys(grants.roles)),
            "users": list(dict.fromkeys(grants.users)),
        },
        "needs_classification": False,
    }

    documents_collection.update_one({"document_uuid": document_uuid}, {"$set": after})

    # Chunks carry a copy of the access fields: keep it in step so the next query already sees the change.
    documents_chunk_collection.update_many(
        {"document_uuid": document_uuid},
        {"$set": {k: after[k] for k in ("department_code", "classification", "access")}},
    )

    doc_name = before.get("document_name") or document_uuid
    audit_service.record(
        actor, "document.access.update", doc_name,
        before={k: before.get(k) for k in ("department_code", "classification", "access")},
        after={k: after[k] for k in ("department_code", "classification", "access")},
    )

    return documents_collection.find_one({"document_uuid": document_uuid}, PUBLIC_FIELDS)

#-----------------------------------------------------------------------------------------------------------

def delete_document(document_uuid: str, actor: UserContext):
    """Delete a document: its stored PDF (R2), its record and its chunks."""

    doc = documents_collection.find_one({"document_uuid": document_uuid}, {"document_name": 1, "object_key": 1})

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    # Remove the stored file first: if R2 fails, nothing is deleted and the admin can retry.
    # Deleting a key that is already gone succeeds, so retries are safe.
    if doc.get("object_key"):
        storage_service.delete_object(doc["object_key"])

    documents_collection.delete_one({"document_uuid": document_uuid})
    documents_chunk_collection.delete_many({"document_uuid": document_uuid})

    doc_name = doc.get("document_name") or document_uuid
    audit_service.record(actor, "document.delete", doc_name, before={"document_name": doc_name})

    return {
        "message": "Document deleted successfully.",
        "document_uuid": document_uuid
    }


#-----------------------------------------------------------------------------------------------------------

def scan_and_ingest_pdf_folder(folder_path: str):
    """Register the PDFs in a folder, then chunk and embed each one so it becomes searchable."""

    from services.rag_service import ingest_document  # heavy imports stay lazy

    scan_result = scan_pdf_folder(folder_path)
    folder = validate_folder_path(folder_path)

    ingestion_results = []
    ingestion_errors = []

    for pdf_path in folder.rglob("*"):
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            continue

        try:
            resolved_path = pdf_path.resolve(strict=True)
            resolved_path.relative_to(DOCUMENTS_ROOT)

            document = documents_collection.find_one(
                {"file_path": os.path.normcase(str(resolved_path))},
                {"_id": 0, "document_uuid": 1, "document_name": 1},
            )

            if not document:
                ingestion_errors.append({"document_name": pdf_path.name, "reason": "PDF was not registered in documents."})
                continue

            ingestion_results.append({
                "document_uuid": document["document_uuid"],
                "document_name": document["document_name"],
                "result": ingest_document(document["document_uuid"]),
            })

        except Exception as exc:
            ingestion_errors.append({
                "document_name": pdf_path.name,
                "reason": getattr(exc, "detail", None) or str(exc),
                "error_type": type(exc).__name__,
            })

    return {
        **scan_result,
        "ingested_count": len(ingestion_results),
        "ingestion_results": ingestion_results,
        "ingestion_errors": ingestion_errors,
        "message": "Folder scan and ingestion finished.",
    }

#-----------------------------------------------------------------------------------------------------------

def _clean_filename(name) -> str:
    """Keep only the file's own name (no folders), without control characters, at most 200 chars."""

    base = str(name or "").replace("\\", "/").split("/")[-1]
    base = "".join(c for c in base if c.isprintable()).strip()

    if len(base) > 200:
        stem, dot, ext = base.rpartition(".")
        base = (stem[: 200 - len(ext) - 1] + dot + ext) if dot else base[:200]

    return base or "document.pdf"


def _read_upload(file) -> bytes:
    """Read at most the size limit + 1 byte, so an oversized file is rejected without reading all of it."""

    data = file.file.read(MAX_UPLOAD_BYTES + 1)

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"The file is larger than {MAX_UPLOAD_MB} MB.")

    return data


def upload_document(file, actor: UserContext):
    """Store an uploaded PDF in the private R2 bucket, register it, then chunk and embed it."""

    from services.rag_service import ingest_document  # heavy imports stay lazy

    document_name = _clean_filename(file.filename)

    if not document_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    data = _read_upload(file)
    pdf = read_pdf(data, extract_text=False)  # size, %PDF- header, readable, not password-protected
    content_hash = sha256_hex(data)

    # Same bytes already registered (by an earlier upload, or by the legacy folder scan)?
    duplicate = documents_collection.find_one(
        {"$or": [{"content_hash": content_hash}, {"file_hash": content_hash}]},
        {"_id": 0, "document_name": 1},
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"This PDF is already uploaded as '{duplicate.get('document_name')}'.",
        )

    document_uuid = str(uuid.uuid4())
    object_key = storage_service.object_key_for(document_uuid)
    now = datetime.now(timezone.utc)

    storage_service.put_pdf(object_key, data, content_hash)

    document = {
        "document_uuid": document_uuid,
        "document_name": document_name,
        "category": None,
        "object_key": object_key,
        "content_hash": content_hash,
        "size_bytes": len(data),
        "page_count": pdf.page_count,
        "pdf_metadata": pdf.metadata,
        # Safe defaults for a new file; an admin must classify it.
        "department_code": None,
        "classification": "internal",
        "access": {"departments": [], "roles": [], "users": []},
        "needs_classification": True,
        "status": "uploaded",
        "uploaded_by": actor.user_uuid,
        "created_at": now,
        "last_update": now,
    }

    try:
        documents_collection.insert_one(document)

    except DuplicateKeyError as exc:
        storage_service.delete_object(object_key)  # keep the bucket clean

        if "content_hash" in str((exc.details or {}).get("keyPattern", "")):
            # Same content uploaded at the same moment by another request.
            raise HTTPException(status_code=409, detail="This PDF is already uploaded.") from exc

        # Another unique index (for example an old one on `file_path`) rejected a record without that field.
        logger.error("Document insert blocked by a unique index: %s", (exc.details or {}).get("keyPattern"))
        raise HTTPException(status_code=500, detail="Could not register the document. Check the backend logs.") from exc

    except Exception:
        storage_service.delete_object(object_key)
        raise

    audit_service.record(
        actor, "document.upload", document_uuid,
        after={"document_name": document_name, "size_bytes": len(data), "page_count": pdf.page_count},
    )

    # The file is safely stored and registered; an ingestion problem is reported, not raised,
    # so the admin can fix it and re-run POST /api/documents/{uuid}/ingest without uploading again.
    try:
        ingestion = {"status": "completed", **ingest_document(document_uuid)}
    except HTTPException as exc:
        ingestion = {"status": "failed", "detail": exc.detail}

    return {
        "message": "Document uploaded.",
        "document": documents_collection.find_one({"document_uuid": document_uuid}, PUBLIC_FIELDS),
        "ingestion": ingestion,
    }

#-----------------------------------------------------------------------------------------------------------

def get_document_view_url(document_uuid: str, ctx: UserContext):
    """Short-lived link to the original PDF, issued only if the caller may read the document."""

    doc = documents_collection.find_one(
        {"document_uuid": document_uuid},
        {"_id": 0, "document_uuid": 1, "document_name": 1, "object_key": 1,
         "classification": 1, "department_code": 1, "access": 1},
    )

    # Same answer for "does not exist" and "not allowed", so a refusal never confirms a document exists.
    # Admin permissions grant management, not reading: everyone goes through can_view.
    if not doc or not can_view(ctx, doc):
        raise HTTPException(status_code=404, detail="Document not found.")

    if not doc.get("object_key"):
        raise HTTPException(status_code=409, detail="This document has no stored file to view. Upload it again.")

    url = storage_service.presigned_view_url(doc["object_key"], doc.get("document_name") or "document.pdf")

    audit_service.record(ctx, "document.view", document_uuid)

    return {"url": url, "expires_in": storage_service.PRESIGNED_URL_TTL_SECONDS}
