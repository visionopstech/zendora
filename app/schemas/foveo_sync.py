import enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class FoveoEventType(str, enum.Enum):
    """Every event Foveo may send. One request schema covers all of them."""

    FUNERAL_HOME_UPDATED = "funeral_home.updated"
    STREAM_CREATED = "stream.created"
    STREAM_UPDATED = "stream.updated"
    USER_UPDATED = "user.updated"
    MANUAL = "manual"


class FoveoEntityStatus(str, enum.Enum):
    """Per-entity outcome in the sync response."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    SKIPPED_PLACEHOLDER_EMAIL = "skipped_placeholder_email"
    SKIPPED_EXISTING_USER = "skipped_existing_user"
    CONFLICT = "conflict"


class FoveoAddress(BaseModel):
    """Postal address. Any field may be omitted when Foveo does not have it."""

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    additional_info: Optional[str] = None


class FoveoUserBlock(BaseModel):
    """Director (main or stream) payload."""

    foveo_user_id: int
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password_hash: Optional[str] = None
    is_active: bool = True


class FoveoFamilyBlock(FoveoUserBlock):
    """Family admin payload, including stream-derived deceased name and address."""

    deceased_first_name: Optional[str] = None
    deceased_last_name: Optional[str] = None
    address: Optional[FoveoAddress] = None


class FoveoFuneralHomeBlock(BaseModel):
    """Funeral home profile. Syncs even when the home has no stream."""

    foveo_id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[FoveoAddress] = None
    is_active: bool = True


class FoveoSyncRequest(BaseModel):
    """Single payload shape for every Foveo event."""

    event_id: UUID
    event: FoveoEventType
    foveo_stream_id: Optional[int] = None
    funeral_home: Optional[FoveoFuneralHomeBlock] = None
    main_director: Optional[FoveoUserBlock] = None
    stream_director: Optional[FoveoUserBlock] = None
    family: Optional[FoveoFamilyBlock] = None


class FoveoSyncEntityResult(BaseModel):
    """Outcome for one funeral home or user in the payload."""

    status: FoveoEntityStatus
    id: Optional[UUID] = None
    detail: Optional[str] = None


class FoveoSyncResponse(BaseModel):
    """Per-entity results. Missing keys mean that block was not in the event."""

    funeral_home: Optional[FoveoSyncEntityResult] = None
    main_director: Optional[FoveoSyncEntityResult] = None
    stream_director: Optional[FoveoSyncEntityResult] = None
    family: Optional[FoveoSyncEntityResult] = None
