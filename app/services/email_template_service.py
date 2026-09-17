from datetime import datetime
from typing import Any, Optional

from jinja2 import ChainableUndefined
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.email_template import EmailTemplate

_jinja_env = SandboxedEnvironment(
    autoescape=True,
    undefined=ChainableUndefined,
)


class EmailTemplateService:
    """Load, update, and render slug-keyed email templates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self) -> list[EmailTemplate]:
        result = await self.db.execute(select(EmailTemplate).order_by(EmailTemplate.slug))
        return list(result.scalars().all())

    async def get_by_slug(self, slug: str) -> Optional[EmailTemplate]:
        result = await self.db.execute(
            select(EmailTemplate).where(EmailTemplate.slug == slug)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        slug: str,
        *,
        name: Optional[str] = None,
        subject: Optional[str] = None,
        body: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> EmailTemplate:
        template = await self.get_by_slug(slug)
        if not template:
            raise NotFoundException("Email template not found")

        if name is not None:
            template.name = name
        if subject is not None:
            template.subject = subject
        if body is not None:
            template.body = body
        if description is not None:
            template.description = description
        if is_active is not None:
            template.is_active = is_active

        template.updated_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(template)
        return template

    def render(self, subject: str, body: str, context: dict[str, Any]) -> tuple[str, str]:
        """Render subject and HTML body with the given context."""
        rendered_subject = _jinja_env.from_string(subject).render(**context)
        rendered_body = _jinja_env.from_string(body).render(**context)
        return rendered_subject, rendered_body
