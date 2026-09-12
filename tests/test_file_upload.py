import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.core.exceptions import ValidationError
from app.services.file_service import FileService


JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 154 + b"\xff\xd9"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def make_upload(data: bytes, filename: str = "photo.jpg") -> UploadFile:
    upload = UploadFile(filename=filename, file=SimpleNamespace())

    async def read(_size: int = -1):
        return data

    upload.read = read  # type: ignore[method-assign]
    return upload


def test_detects_jpeg_even_when_client_content_type_is_wrong():
    assert FileService.detect_content_type(JPEG_BYTES) == "image/jpeg"


def test_detects_png():
    assert FileService.detect_content_type(PNG_BYTES) == "image/png"


def test_rejects_non_image_bytes():
    assert FileService.detect_content_type(b"not-an-image") is None


@pytest.mark.asyncio
async def test_save_image_writes_bytes_without_utf8_decode(tmp_path: Path):
    service = FileService(upload_dir=str(tmp_path), max_bytes=1024)
    filename, content_type, size = await service.save_image(make_upload(JPEG_BYTES))

    stored = tmp_path / filename
    assert content_type == "image/jpeg"
    assert size == len(JPEG_BYTES)
    assert stored.read_bytes() == JPEG_BYTES
    assert stored.read_bytes()[158] == 0xFF


@pytest.mark.asyncio
async def test_save_image_rejects_empty_and_unsupported(tmp_path: Path):
    service = FileService(upload_dir=str(tmp_path), max_bytes=1024)

    with pytest.raises(ValidationError, match="empty"):
        await service.save_image(make_upload(b""))

    with pytest.raises(ValidationError, match="Unsupported"):
        await service.save_image(make_upload(b"PK\x03\x04not-a-zip-image"))


@pytest.mark.asyncio
async def test_save_image_rejects_oversized(tmp_path: Path):
    service = FileService(upload_dir=str(tmp_path), max_bytes=10)

    with pytest.raises(ValidationError, match="too large"):
        await service.save_image(make_upload(JPEG_BYTES))


def test_public_url_joins_base_and_filename():
    url = FileService.public_url("https://api.example.com/", f"{uuid4().hex}.jpg")
    assert url.startswith("https://api.example.com/uploads/")
    assert url.endswith(".jpg")
