import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, List
from uuid import UUID

import stripe

from app.core.config import settings
from app.models.product import Product

# Configure Stripe
stripe.api_key = settings.stripe_secret_key

CHECKOUT_SESSION_EXPIRY_SECONDS = 1800


@dataclass(frozen=True)
class CheckoutSessionResult:
    """Stripe Checkout session identifiers."""

    url: str
    session_id: str


def price_to_cents(price: Decimal) -> int:
    """Convert a decimal dollar amount to Stripe's integer cents."""
    return int((price * 100).quantize(Decimal("1")))


def normalize_product_images(images: Any) -> List[str]:
    """Return up to five HTTPS image URLs for Stripe product_data."""
    if not images:
        return []

    if isinstance(images, list):
        candidates = images
    elif isinstance(images, dict):
        candidates = list(images.values())
    else:
        return []

    urls: List[str] = []
    for item in candidates:
        if hasattr(item, "url"):
            item = item.url
        elif isinstance(item, dict):
            item = item.get("url")
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        if len(urls) >= 5:
            break
    return urls


class StripeService:
    """Service for Stripe payment operations."""

    def _build_line_items(
        self,
        products: List[Product],
        quantities: dict[UUID, int],
    ) -> List[dict]:
        line_items = []
        for product in products:
            quantity = quantities.get(product.id, 1)
            line_items.append(
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": product.name,
                            "description": product.description or "",
                            "images": normalize_product_images(product.images),
                        },
                        "unit_amount": price_to_cents(product.price),
                    },
                    "quantity": quantity,
                }
            )
        return line_items

    def _create_checkout_session_sync(
        self,
        order_id: UUID,
        products: List[Product],
        quantities: dict[UUID, int],
        visitor_email: str,
    ) -> CheckoutSessionResult:
        line_items = self._build_line_items(products, quantities)

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=f"{settings.frontend_url}/order/{order_id}/success",
            cancel_url=f"{settings.frontend_url}/order/{order_id}/cancel",
            metadata={"order_id": str(order_id)},
            customer_email=visitor_email,
            expires_at=int(time.time()) + CHECKOUT_SESSION_EXPIRY_SECONDS,
        )

        return CheckoutSessionResult(url=session.url, session_id=session.id)

    async def create_checkout_session(
        self,
        order_id: UUID,
        products: List[Product],
        quantities: dict[UUID, int],
        visitor_email: str,
    ) -> CheckoutSessionResult:
        """
        Create a Stripe Checkout session.

        Args:
            order_id: ID of the order
            products: List of Product objects
            quantities: Dict mapping product_id to quantity
            visitor_email: Email of the visitor

        Returns:
            CheckoutSessionResult with hosted checkout URL and session id (cs_...)
        """
        return await asyncio.to_thread(
            self._create_checkout_session_sync,
            order_id,
            products,
            quantities,
            visitor_email,
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> dict:
        """
        Verify Stripe webhook signature.

        Args:
            payload: Request body
            signature: Stripe signature header

        Returns:
            dict: Verified event object

        Raises:
            stripe.error.SignatureVerificationError: If signature is invalid
        """
        return stripe.Webhook.construct_event(
            payload,
            signature,
            settings.stripe_webhook_secret,
        )
