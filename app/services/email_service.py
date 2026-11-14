import logging
import os
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import PASSWORD_RESET_TOKEN_EXPIRE_HOURS
from app.core.database import AsyncSessionLocal
from app.models.email_template import EmailTemplateSlug
from app.models.gift_collection import GiftCollection
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.services.email_context import (
    active_vendor_users,
    buyer_order_context,
    collection_created_context,
    family_admin_order_context,
    group_order_products_by_vendor,
    super_admin_order_context,
    vendor_order_context,
    with_status_change,
)
from app.services.email_template_service import EmailTemplateService

logger = logging.getLogger(__name__)

# Status mail is for an order that has already been paid. REFUNDED, PROCESSING,
# SHIPPING and COMPLETED are later changes. FAILED and CANCELED count only when payment
# previously succeeded.
POST_PAYMENT_STATUSES = frozenset(
    {
        OrderStatus.PAID.value,
        OrderStatus.REFUNDED.value,
        OrderStatus.PROCESSING.value,
        OrderStatus.SHIPPING.value,
        OrderStatus.COMPLETED.value,
    }
)

_PAID_ONLY_STATUSES = frozenset(
    {OrderStatus.FAILED.value, OrderStatus.CANCELED.value}
)


def order_ready_for_status_email(order: Order) -> bool:
    """True when the order has been paid, so a later status email is allowed."""
    if order.status in POST_PAYMENT_STATUSES:
        return True
    return order.status in _PAID_ONLY_STATUSES and order.paid_at is not None


@dataclass
class StatusEmailDelivery:
    audience: str
    email: str
    sent: bool

template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "emails")
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(["html", "xml"]),
)


def _ses_client():
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("ses", **kwargs)


def _from_address() -> str:
    if settings.ses_from_name:
        return f"{settings.ses_from_name} <{settings.ses_from_email}>"
    return settings.ses_from_email


class EmailService:
    """Send emails via Amazon SES, optionally rendered from DB templates."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = _ses_client()
        return self._client

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
    ) -> bool:
        """Send an email via Amazon SES."""
        try:
            body: dict[str, Any] = {
                "Html": {"Data": html_content, "Charset": "UTF-8"},
            }
            if plain_content:
                body["Text"] = {"Data": plain_content, "Charset": "UTF-8"}

            self.client.send_email(
                Source=_from_address(),
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": body,
                },
            )
            return True
        except (BotoCoreError, ClientError, Exception) as exc:
            logger.error("Error sending email to %s: %s", to_email, exc)
            return False

    async def send_templated_email(
        self,
        slug: str,
        to_email: str,
        context: dict[str, Any],
    ) -> bool:
        """Load a DB template by slug, render it, and send."""
        if not self.db:
            logger.error("Cannot send templated email %s: no database session", slug)
            return False
        if not to_email:
            logger.warning("Skipping templated email %s: empty recipient", slug)
            return False

        template_service = EmailTemplateService(self.db)
        template = await template_service.get_by_slug(slug)
        if not template:
            logger.error("Email template %s not found", slug)
            return False
        if not template.is_active:
            logger.warning("Skipping inactive email template %s", slug)
            return False

        subject, html_content = template_service.render(
            template.subject, template.body, context
        )
        return await self.send_email(to_email, subject, html_content)

    async def _super_admin_emails(self) -> list[str]:
        result = await self.db.execute(
            select(User.email).where(
                User.role == UserRole.SUPER_ADMIN.value,
                User.is_active.is_(True),
            )
        )
        return [email for email in result.scalars().all() if email]

    async def notify_order_created(self, order: Order) -> None:
        """Send order-created emails to vendor, family admin, buyer, and super admins."""
        vendor_groups = group_order_products_by_vendor(order)
        for vendor, vendor_products in vendor_groups.values():
            context = vendor_order_context(order, vendor, vendor_products)
            for user in active_vendor_users(vendor):
                await self.send_templated_email(
                    EmailTemplateSlug.ORDER_CREATED_VENDOR.value,
                    user.email,
                    context,
                )

        if order.family_admin and order.family_admin.email:
            await self.send_templated_email(
                EmailTemplateSlug.ORDER_CREATED_FAMILY_ADMIN.value,
                order.family_admin.email,
                family_admin_order_context(order),
            )

        if order.visitor and order.visitor.email:
            await self.send_templated_email(
                EmailTemplateSlug.ORDER_CREATED_BUYER.value,
                order.visitor.email,
                buyer_order_context(order),
            )

        super_admin_context = super_admin_order_context(order)
        for email in await self._super_admin_emails():
            await self.send_templated_email(
                EmailTemplateSlug.ORDER_CREATED_SUPER_ADMIN.value,
                email,
                super_admin_context,
            )

    async def _record_status_email(
        self,
        deliveries: list[StatusEmailDelivery],
        audience: str,
        slug: str,
        to_email: Optional[str],
        context: dict[str, Any],
    ) -> None:
        if not to_email:
            return
        sent = await self.send_templated_email(slug, to_email, context)
        deliveries.append(StatusEmailDelivery(audience=audience, email=to_email, sent=sent))

    async def notify_order_status_changed(
        self,
        order: Order,
        sender: User,
        note: Optional[str] = None,
    ) -> list[StatusEmailDelivery]:
        """Email every party on a paid order about its current status."""
        deliveries: list[StatusEmailDelivery] = []

        vendor_groups = group_order_products_by_vendor(order)
        for vendor, vendor_products in vendor_groups.values():
            context = with_status_change(
                vendor_order_context(order, vendor, vendor_products),
                order,
                sender,
                note,
            )
            for user in active_vendor_users(vendor):
                await self._record_status_email(
                    deliveries,
                    "vendor",
                    EmailTemplateSlug.ORDER_STATUS_CHANGED_VENDOR.value,
                    user.email,
                    context,
                )

        if order.family_admin and order.family_admin.email:
            await self._record_status_email(
                deliveries,
                "family_admin",
                EmailTemplateSlug.ORDER_STATUS_CHANGED_FAMILY_ADMIN.value,
                order.family_admin.email,
                with_status_change(family_admin_order_context(order), order, sender, note),
            )

        if order.visitor and order.visitor.email:
            await self._record_status_email(
                deliveries,
                "buyer",
                EmailTemplateSlug.ORDER_STATUS_CHANGED_BUYER.value,
                order.visitor.email,
                with_status_change(buyer_order_context(order), order, sender, note),
            )

        collection = order.gift_collection
        director = collection.director if collection else None
        if director and director.email:
            await self._record_status_email(
                deliveries,
                "director",
                EmailTemplateSlug.ORDER_STATUS_CHANGED_DIRECTOR.value,
                director.email,
                with_status_change(family_admin_order_context(order), order, sender, note),
            )

        super_admin_context = with_status_change(
            super_admin_order_context(order), order, sender, note
        )
        for email in await self._super_admin_emails():
            await self._record_status_email(
                deliveries,
                "super_admin",
                EmailTemplateSlug.ORDER_STATUS_CHANGED_SUPER_ADMIN.value,
                email,
                super_admin_context,
            )

        return deliveries

    async def notify_collection_created(self, collection: GiftCollection) -> None:
        """Send collection-created emails to family admin, director, and super admins."""
        context = collection_created_context(collection)

        if collection.family_admin and collection.family_admin.email:
            await self.send_templated_email(
                EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value,
                collection.family_admin.email,
                context,
            )

        if collection.director and collection.director.email:
            await self.send_templated_email(
                EmailTemplateSlug.COLLECTION_CREATED_DIRECTOR.value,
                collection.director.email,
                context,
            )

        for email in await self._super_admin_emails():
            await self.send_templated_email(
                EmailTemplateSlug.COLLECTION_CREATED_SUPER_ADMIN.value,
                email,
                context,
            )

    async def send_family_admin_credentials_email(
        self,
        family_admin: User,
        password: str,
    ) -> bool:
        """
        Send credentials email to a newly created family admin.

        Triggered when: a director creates a gift collection for a new family.
        """
        template = jinja_env.get_template("family_admin_credentials.html")
        html_content = template.render(
            family_admin_name=family_admin.display_name or "there",
            family_admin_email=family_admin.email,
            password=password,
            login_url=f"{settings.frontend_url}/login",
        )
        return await self.send_email(
            to_email=family_admin.email,
            subject="Welcome to Zendora - Your Family Admin Credentials",
            html_content=html_content,
        )

    async def send_password_reset_email(
        self,
        to_email: str,
        user_name: str,
        reset_url: str,
    ) -> bool:
        """Send a password-reset link to a user who requested it."""
        template = jinja_env.get_template("password_reset.html")
        html_content = template.render(
            user_name=user_name or "there",
            reset_url=reset_url,
            expire_hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS,
        )
        return await self.send_email(
            to_email=to_email,
            subject="Reset your Zendora password",
            html_content=html_content,
        )

    async def send_gift_collection_published_email(
        self,
        gift_collection: GiftCollection,
        director: User,
    ) -> bool:
        """Notify the director when a family admin publishes a gift collection."""
        template = jinja_env.get_template("gift_collection_published.html")
        html_content = template.render(
            director_name=director.display_name or "Director",
            collection_title=gift_collection.title or "Untitled Gift Collection",
            collection_url=f"{settings.frontend_url}/w/{gift_collection.public_slug}",
            family_admin_email=(
                gift_collection.family_admin.email if gift_collection.family_admin else "Unknown"
            ),
        )
        return await self.send_email(
            to_email=director.email,
            subject=f"Gift Collection Published: {gift_collection.title or 'Untitled'}",
            html_content=html_content,
        )


async def send_collection_created_notifications(collection_id: UUID) -> None:
    """Background task: reload the collection and send created emails."""
    from app.services.gift_collection_service import GiftCollectionService

    async with AsyncSessionLocal() as db:
        try:
            collection_service = GiftCollectionService(db)
            collection = await collection_service.get_by_id(collection_id)
            if not collection:
                logger.error(
                    "Could not load gift collection %s for created emails",
                    collection_id,
                )
                return
            email_service = EmailService(db)
            await email_service.notify_collection_created(collection)
        except Exception:
            logger.exception(
                "Error sending collection-created emails for %s", collection_id
            )
