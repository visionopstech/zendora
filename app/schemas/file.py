from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Public URL and metadata for a stored upload."""

    url: str
    filename: str
    content_type: str
    size: int
