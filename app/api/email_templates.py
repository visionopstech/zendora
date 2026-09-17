from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.dependencies.auth import require_super_admin
from app.models.user import User
from app.schemas.email_template import (
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)
from app.services.email_template_defaults import SAMPLE_EMAIL_CONTEXTS
from app.services.email_template_service import EmailTemplateService

router = APIRouter()


@router.get("", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """List all email templates (SUPER_ADMIN only)."""
    service = EmailTemplateService(db)
    templates = await service.list()
    return [EmailTemplateResponse.model_validate(template) for template in templates]


@router.get("/{slug}", response_model=EmailTemplateResponse)
async def get_email_template(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Get an email template by slug (SUPER_ADMIN only)."""
    service = EmailTemplateService(db)
    template = await service.get_by_slug(slug)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found",
        )
    return EmailTemplateResponse.model_validate(template)


@router.put("/{slug}", response_model=EmailTemplateResponse)
async def update_email_template(
    slug: str,
    payload: EmailTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Update subject, body, name, description, or is_active (SUPER_ADMIN only)."""
    service = EmailTemplateService(db)
    try:
        template = await service.update(
            slug,
            name=payload.name,
            subject=payload.subject,
            body=payload.body,
            description=payload.description,
            is_active=payload.is_active,
        )
        await db.commit()
        return EmailTemplateResponse.model_validate(template)
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post("/{slug}/preview", response_model=EmailTemplatePreviewResponse)
async def preview_email_template(
    slug: str,
    payload: EmailTemplatePreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Render a template with the given context, or a sample context if omitted."""
    service = EmailTemplateService(db)
    template = await service.get_by_slug(slug)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found",
        )
    context = payload.context if payload.context else SAMPLE_EMAIL_CONTEXTS.get(slug, {})
    subject, body = service.render(template.subject, template.body, context)
    return EmailTemplatePreviewResponse(subject=subject, body=body)
