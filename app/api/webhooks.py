import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

import stripe
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.core.database import AsyncSessionLocal
from app.core.exceptions import NotFoundException
from app.models.order import Order, OrderStatus
from app.services.financial_service import FinancialService
from app.services.order_service import OrderService
from app.services.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter()


def session_amount_matches_order(order: Order, session: dict) -> bool:
    """Compare Stripe amount_total (cents) with the order total."""
    amount_total = session.get("amount_total")
    if amount_total is None:
        logger.warning(
            "Stripe session %s missing amount_total; skipping amount validation",
            session.get("id"),
        )
        return True

    expected_cents = int((order.total_amount * 100).quantize(Decimal("1")))
    if amount_total != expected_cents:
        logger.error(
            "Amount mismatch for order %s: expected %s cents, got %s from Stripe session %s",
            order.id,
            expected_cents,
            amount_total,
            session.get("id"),
        )
        return False
    return True


async def resolve_order_from_session(
    order_service: OrderService,
    session: dict,
    *,
    load_products: bool = False,
) -> Optional[Order]:
    """Resolve an order from checkout session metadata or Stripe session id."""
    metadata = session.get("metadata") or {}
    order_id = metadata.get("order_id")
    if order_id:
        order = await order_service.get_by_id(UUID(order_id), load_products=load_products)
        if order:
            return order

    session_id = session.get("id")
    if session_id:
        return await order_service.get_by_stripe_session_id(session_id)

    return None


@router.post("/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Handle Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Processes checkout.session.completed events
    3. Updates order status
    4. Sends notification emails
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    stripe_service = StripeService()

    try:
        event = stripe_service.verify_webhook_signature(payload, sig_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        payment_status = session.get("payment_status")
        if payment_status != "paid":
            logger.info(
                "Ignoring checkout.session.completed for session %s with payment_status=%s",
                session.get("id"),
                payment_status,
            )
            return {"status": "ignored", "reason": "payment_not_paid"}

        background_tasks.add_task(handle_successful_payment, session)
    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        background_tasks.add_task(handle_expired_payment, session)

    return {"status": "success"}


async def handle_successful_payment(session: dict):
    """Handle successful payment completion."""
    async with AsyncSessionLocal() as db:
        try:
            order_service = OrderService(db)
            financial_service = FinancialService(db)

            order = await resolve_order_from_session(
                order_service, session, load_products=True
            )
            if not order:
                logger.error(
                    "Could not resolve order for Stripe session %s",
                    session.get("id"),
                )
                return

            if not session_amount_matches_order(order, session):
                return

            order_id = order.id
            was_paid = order.status == OrderStatus.PAID.value

            if not was_paid:
                await order_service.mark_as_paid(order.id)

            try:
                commission_credited = await financial_service.credit_order_commission(
                    order.id
                )
            except NotFoundException:
                commission_credited = False
            await db.commit()

            if was_paid and not commission_credited:
                logger.info("Order %s already processed", order_id)
                return

            await db.refresh(order, ["visitor", "admin", "wishlist", "products"])
            await db.refresh(order.wishlist, ["manager"])

            logger.info("Order %s marked as paid", order_id)

            from app.services.email_service import EmailService

            email_service = EmailService()
            await email_service.send_purchase_confirmation_emails(order)

        except Exception:
            logger.exception("Error handling successful payment")
            await db.rollback()


async def handle_expired_payment(session: dict):
    """Handle expired checkout session."""
    async with AsyncSessionLocal() as db:
        try:
            order_service = OrderService(db)

            order = await resolve_order_from_session(order_service, session)
            if not order:
                logger.warning(
                    "Could not resolve order for expired Stripe session %s",
                    session.get("id"),
                )
                return

            if order.status == OrderStatus.PAID.value:
                logger.info(
                    "Skipping expire handler for already paid order %s",
                    order.id,
                )
                return

            await order_service.mark_as_failed(order.id)
            await db.commit()

            logger.info("Order %s marked as failed (session expired)", order.id)

        except Exception:
            logger.exception("Error handling expired payment")
            await db.rollback()
