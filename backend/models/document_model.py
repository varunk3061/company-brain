from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.org_model import Classification

#--------------------------------------------------------------------------------------------

class FolderScanRequest(BaseModel):
    folder_path: str = Field(
        ..., min_length=1, description="Path to a folder inside the approved document root."
    )


class AccessGrants(BaseModel):
    """Explicit grants. Each list is checked independently (any match grants access)."""

    model_config = ConfigDict(extra="forbid")

    departments: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    users: List[str] = Field(default_factory=list)


class DocumentAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_code: Optional[str] = Field(default=None, description="Owning department.")
    classification: Classification
    access: AccessGrants = Field(default_factory=AccessGrants)


class DocumentResponse(BaseModel):
    document_uuid: str
    document_name: str
    category: Optional[str] = None
    last_update: datetime
    department_code: Optional[str] = None
    classification: Classification = "restricted"  # legacy rows without a value stay locked down
    access: AccessGrants = Field(default_factory=AccessGrants)
    needs_classification: bool = False
