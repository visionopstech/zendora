import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationError


ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

_MAGIC_PREFIXES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


class FileService:
    """Store uploaded images as bytes. Never decode file contents as text."""

    def __init__(self, upload_dir: Optional[str] = None, max_bytes: Optional[int] = None):
        self.upload_dir = Path(upload_dir or settings.upload_dir)
        self.max_bytes = max_bytes if max_bytes is not None else settings.max_upload_bytes
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def detect_content_type(data: bytes) -> Optional[str]:
        for prefix, content_type in _MAGIC_PREFIXES:
            if data.startswith(prefix):
                return content_type
        if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        return None

    async def save_image(self, upload: UploadFile) -> tuple[str, str, int]:
        """
        Persist an image upload.

        Returns:
            (stored_filename, content_type, size)
        """
        data = await upload.read()
        size = len(data)
        if size == 0:
            raise ValidationError("Uploaded file is empty")
        if size > self.max_bytes:
            raise ValidationError(
                f"File is too large. Maximum size is {self.max_bytes} bytes"
            )

        content_type = self.detect_content_type(data)
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                "Unsupported file type. Upload a JPEG, PNG, GIF, or WebP image"
            )

        filename = f"{uuid.uuid4().hex}{ALLOWED_CONTENT_TYPES[content_type]}"
        destination = self.upload_dir / filename
        destination.write_bytes(data)
        return filename, content_type, size

    @staticmethod
    def public_url(request_base_url: str, filename: str) -> str:
        base = request_base_url.rstrip("/")
        return f"{base}/uploads/{filename}"
