from fastapi import APIRouter, Depends

from models.document_model import (
    FolderScanRequest,
    DocumentPermissionUpdate
)

from services.document_service import (
    scan_pdf_folder,
    list_documents,
    update_document_roles
)

# IMPORTANT:
# Replace this dependency with your existing admin JWT/role
# authorization dependency before exposing these endpoints.
from utils.auth import get_current_admin

#----------------------------------------------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/documents",
    tags=["Document Management"]
)

#----------------------------------------------------------------------------------------------------------------

@router.post("/scan-folder")
def scan_folder(
    request: FolderScanRequest,
    admin=Depends(get_current_admin)
):
    return scan_pdf_folder(request.folder_path)

#----------------------------------------------------------------------------------------------------------------

@router.get("/")
def get_documents(
    admin=Depends(get_current_admin)
):
    return list_documents()

#----------------------------------------------------------------------------------------------------------------

@router.patch("/{document_uuid}/permissions")
def update_permissions(
    document_uuid: str,
    request: DocumentPermissionUpdate,
    admin=Depends(get_current_admin)
):
    return update_document_roles(
        document_uuid,
        request.allowed_roles
    )

#----------------------------------------------------------------------------------------------------------------