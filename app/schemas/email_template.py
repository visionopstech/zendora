from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EmailTemplateVariable(BaseModel):
    name: str
    description: str


class EmailTemplateResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    subject: str
    body: str
    description: Optional[str] = None
    available_variables: list[EmailTemplateVariable] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplatePreviewRequest(BaseModel):
    context: Optional[dict[str, Any]] = None


class EmailTemplatePreviewResponse(BaseModel):
    subject: str
    body: str
