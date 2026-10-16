import os
import uuid

from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from database.connection import documents_collection

#-----------------------------------------------------------------------------------------------------------

load_dotenv()

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
                "allowed_roles" : [],
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

def list_documents():
    """Return registered documents without internal file paths."""

    return list(
        documents_collection.find(
            {},
            {
                "_id" : 0,
                "document_uuid": 1,
                "document_name": 1,
                "category": 1,
                "last_update": 1,
                "allowed_roles": 1
            }
        ).sort("document_name", 1)
    )

#-----------------------------------------------------------------------------------------------------------

def update_document_roles( document_uuid: str, allowed_roles: list[str] ):
    """Update the roles allowed to access a document."""

    # Normalize and reject empty or duplicate role names.
    roles = [role.strip() for role in allowed_roles]

    if any(not role for role in roles):
        raise HTTPException(
            status_code=422,
            detail="Role names cannot be empty."
        )

    roles = list(dict.fromkeys(roles))

    result = documents_collection.update_one(
        {"document_uuid":document_uuid},
        {"$set":{"allowed_roles":roles}} 
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    return documents_collection.find_one(
        {"document_uuid": document_uuid},
        {
            "_id": 0,
            "document_uuid": 1,
            "document_name": 1,
            "category": 1,
            "last_update": 1,
            "allowed_roles": 1
        }
    )