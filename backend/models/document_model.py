from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

class FolderScanRequest(BaseModel):
    folder_path: str = Field(
        ..., min_length=1, description="Path to a folder inside the approved document root."
    )

class DocumentPermissionUpdate(BaseModel):
    allowed_roles: List[str] = Field(
        ...,
        description="Roles permitted to access this document."
    )

class DocumentResponse(BaseModel):
    document_uuid: str
    document_name: str
    category: Optional[str] = None
    last_update: datetime
    allowed_roles: List[str] = Field(default_factory=list)