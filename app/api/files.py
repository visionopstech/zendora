from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.file import FileUploadResponse
from app.services.file_service import FileService

router = APIRouter()


@router.post("", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(..., description="Image file (JPEG, PNG, GIF, or WebP)"),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image and get a public URL to store on logo/header/gallery fields.

    Send `multipart/form-data` with the file in a field named `file`.
    Do not send the file as a JSON body — that is what produced the UTF-8 decode error.
    """
    service = FileService()
    filename, content_type, size = await service.save_image(file)
    return FileUploadResponse(
        url=service.public_url(str(request.base_url), filename),
        filename=filename,
        content_type=content_type,
        size=size,
    )
