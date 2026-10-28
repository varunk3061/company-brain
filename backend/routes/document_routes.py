from fastapi import APIRouter, Depends, File, UploadFile

from models.document_model import (
    DocumentAccessUpdate,
    DocumentResponse,
    DocumentUploadResponse,
    DocumentViewUrlResponse,
    FolderScanRequest,
)
from services.access.policy import UserContext
from services.document_service import (
    scan_pdf_folder,
    list_documents,
    update_document_access,
    delete_document,
    scan_and_ingest_pdf_folder,
    upload_document,
    get_document_view_url,
)
from services.rag_service import ingest_document
from utils.auth import get_current_user, require_permission

#----------------------------------------------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/documents",
    tags=["Document Management"]
)

#----------------------------------------------------------------------------------------------------------------

@router.post("/scan-folder")
def scan_folder(
    request: FolderScanRequest,
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    return scan_pdf_folder(request.folder_path)

#----------------------------------------------------------------------------------------------------------------

@router.get("/", response_model=list[DocumentResponse])
def get_documents(ctx: UserContext = Depends(get_current_user)):
    return list_documents(ctx)

#----------------------------------------------------------------------------------------------------------------

@router.patch("/{document_uuid}/access", response_model=DocumentResponse)
def update_access(
    document_uuid: str,
    request: DocumentAccessUpdate,
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    return update_document_access(document_uuid, request, actor)

#----------------------------------------------------------------------------------------------------------------

@router.delete("/{document_uuid}")
def remove_document(
    document_uuid: str,
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    return delete_document(document_uuid, actor)


#----------------------------------------------------------------------------------------------------------------

@router.post("/scan-and-ingest")
def scan_and_ingest_folder(
    request: FolderScanRequest,
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    """Register PDFs in a folder and make them searchable."""
    return scan_and_ingest_pdf_folder(request.folder_path)

#----------------------------------------------------------------------------------------------------------------

@router.post("/{document_uuid}/ingest")
def ingest_registered_document(
    document_uuid: str,
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    """(Re)process one registered PDF."""
    return ingest_document(document_uuid)

#----------------------------------------------------------------------------------------------------------------

@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
def upload_pdf(
    file: UploadFile = File(..., description="One PDF, at most MAX_UPLOAD_MB (default 25 MB)."),
    actor: UserContext = Depends(require_permission("documents.manage"))
):
    """Store one PDF in the private R2 bucket, register it and make it searchable."""
    # Plain `def`: FastAPI runs it in a worker thread, so PDF parsing and embedding don't block other requests.
    return upload_document(file, actor)

#----------------------------------------------------------------------------------------------------------------

@router.get("/{document_uuid}/view-url", response_model=DocumentViewUrlResponse)
def document_view_url(
    document_uuid: str,
    ctx: UserContext = Depends(get_current_user)
):
    """Short-lived link to the original PDF. Same visibility rule as answers; 404 when not allowed."""
    return get_document_view_url(document_uuid, ctx)
