from math import ceil
from typing import Generic, List, Optional, Sequence, TypeVar
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class DeliveryAddress(BaseModel):
    """Postal address used for deliveries and funeral home profiles."""

    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"
    additional_info: Optional[str] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope returned by every paginated list endpoint."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def build(
        cls,
        items: Sequence[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        return cls(
            items=list(items),
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if page_size else 0,
        )


class PaginationParams:
    """Query parameters shared by paginated endpoints."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-based page number"),
        page_size: int = Query(
            DEFAULT_PAGE_SIZE,
            ge=1,
            le=MAX_PAGE_SIZE,
            description=f"Items per page (max {MAX_PAGE_SIZE})",
        ),
    ):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class UserRef(BaseModel):
    """Compact user reference embedded in list responses."""

    id: UUID
    full_name: Optional[str] = None
    email: str

    class Config:
        from_attributes = True


class FuneralHomeRef(BaseModel):
    """Compact funeral home reference embedded in list responses."""

    id: UUID
    name: str

    class Config:
        from_attributes = True


class GiftCollectionRef(BaseModel):
    """Compact gift collection reference embedded in list responses."""

    id: UUID
    title: Optional[str] = None
    public_slug: str

    class Config:
        from_attributes = True
