import logging
import uuid

from datetime import datetime, timedelta, timezone

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
from services.graph_service import delete_document_from_graph, update_document_access_in_graph

#-----------------------------------------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)

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

    query = {} if ctx.has("documents.manage") else build_document_filter(ctx)#If the user has documents.manage, the query is {}, meaning all document metadata is retrieved.Otherwise, build_document_filter(ctx) constructs a query based on the user's access.

    return list(
        documents_collection.find(query, PUBLIC_FIELDS).sort("document_name", 1) #sort the documents by name in ascending order before returning 
    )

#-----------------------------------------------------------------------------------------------------------

def update_document_access(document_uuid: str, data: DocumentAccessUpdate, actor: UserContext):
    """Set owner department, classification and explicit grants for a document."""

    if data.department_code is not None and not departments_collection.find_one(
        {"code": data.department_code, "status": "active"}
    ):
        raise HTTPException(status_code=422, detail="Unknown or inactive department.")

    grants = data.access

    #That means no invalid departments were found.
    #it checks the frontend send deaprtment, role, and user codes against the database to ensure they are valid. 
    #it uses set to differentate between the provided codes and the existing ones in the database
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

    #later you record the old and new access information in the audit log.
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

    # Keep Neo4j access fields in step with MongoDB.
    try :
        update_document_access_in_graph(
            document_uuid,
            after["department_code"],
            after["classification"],
            after["access"]
        )
    except Exception:
        logger.exception("Graph access update failed for %s", document_uuid)

    #update the audit log with the changes made to the document's access information.
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

    # Keep Neo4j in step with MongoDB. A graph error must not block the delete
    try : 
        delete_document_from_graph(document_uuid)
    except Exception:
        logger.exception("Graph delete failed for %s; Neo4j data for it is orphaned", document_uuid)

    doc_name = doc.get("document_name") or document_uuid
    audit_service.record(actor, "document.delete", doc_name, before={"document_name": doc_name})

    return {
        "message": "Document deleted successfully.",
        "document_uuid": document_uuid
    }


#-----------------------------------------------------------------------------------------------------------
#helper function to remove the / from path and keep only the file name
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

    data = _read_upload(file) #it stores binary data of the uploaded PDF file in the variable 
    pdf = read_pdf(data, extract_text=False)  # size, %PDF- header, readable, not password-protected
    content_hash = sha256_hex(data) #it applies the SHA-256 hash function to the binary data of the uploaded PDF file and returns the resulting hash value as a hexadecimal string. 

    # Same bytes already registered by an earlier upload?
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

    storage_service.put_pdf(object_key, data, content_hash)#The original PDF is now stored in your private Cloudflare R2 bucket.

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
