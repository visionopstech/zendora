"""Payment event handling shared by Stripe webhooks and order reconciliation.

Error contract: the ``handle_*`` coroutines roll back and *re-raise* unexpected
errors so the webhook endpoint can answer 5xx and Stripe retries the event.
All handlers are idempotent, so retries are safe.
"""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.core.exceptions import NotFoundException
from app.models.order import Order, OrderStatus
from app.services.financial_service import FinancialService
from app.services.order_service import OrderService
from app.services.stripe_service import StripeService

logger = logging.getLogger(__name__)

# Statuses from which a confirmed payment moves the order to PAID.
PAYABLE_STATUSES = {OrderStatus.PENDING.value, OrderStatus.FAILED.value}
# Statuses that mean the order was already paid and moved on in fulfilment.
ALREADY_PAID_STATUSES = {
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPING.value,
}
# Statuses that may still turn out to be paid (reconciliation candidates).
UNCONFIRMED_STATUSES = PAYABLE_STATUSES


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
        try:
            parsed_id = UUID(order_id)
        except (TypeError, ValueError):
            parsed_id = None
        if parsed_id:
            order = await order_service.get_by_id(parsed_id, load_products=load_products)
            if order:
                return order

    session_id = session.get("id")
    if session_id:
        return await order_service.get_by_stripe_session_id(session_id)

    return None


async def handle_successful_payment(session: dict) -> None:
    """Mark the order PAID, credit commission and notify (idempotent)."""
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
            status = order.status

            if status in PAYABLE_STATUSES:
                await order_service.mark_as_paid(order_id)
                # Persist PAID on its own: a later failure while crediting
                # commission must never revert a confirmed payment.
                await db.commit()
                was_paid = False
            elif status in ALREADY_PAID_STATUSES:
                was_paid = True
            else:
                logger.warning(
                    "Ignoring payment for order %s in status %s (session %s)",
                    order_id,
                    status,
                    session.get("id"),
                )
                return

            try:
                commission_credited = await financial_service.credit_order_commission(
                    order_id
                )
            except NotFoundException:
                commission_credited = False
            await db.commit()

            if was_paid and not commission_credited:
                logger.info("Order %s already processed", order_id)
                return

            order = await order_service.get_by_id(order_id, load_products=True)
            if not order:
                logger.error("Could not reload order %s after payment", order_id)
                return

            logger.info("Order %s marked as paid", order_id)
        except Exception:
            logger.exception("Error handling successful payment")
            await db.rollback()
            raise

        # Notification is best-effort; it must not trigger a webhook retry.
        try:
            from app.services.email_service import EmailService

            email_service = EmailService(db)
            await email_service.notify_order_created(order)
        except Exception:
            logger.exception("Failed to send order notification for order %s", order_id)


async def _mark_pending_order_failed(
    order_service: OrderService, db, order: Order, reason: str
) -> bool:
    """Move a PENDING order to FAILED; never touch any other status."""
    if order.status != OrderStatus.PENDING.value:
        logger.info(
            "Skipping failure (%s) for order %s in status %s",
            reason,
            order.id,
            order.status,
        )
        return False

    await order_service.mark_as_failed(order.id)
    await db.commit()
    logger.info("Order %s marked as failed (%s)", order.id, reason)
    return True


async def handle_expired_payment(session: dict) -> None:
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

            await _mark_pending_order_failed(
                order_service, db, order, "session expired"
            )
        except Exception:
            logger.exception("Error handling expired payment")
            await db.rollback()
            raise


async def handle_payment_failed(payment_intent: dict) -> None:
    """Handle a failed payment attempt (e.g. declined card)."""
    metadata = payment_intent.get("metadata") or {}
    order_id = metadata.get("order_id")
    if not order_id:
        logger.warning(
            "payment_intent %s has no order_id metadata; cannot mark order failed",
            payment_intent.get("id"),
        )
        return

    try:
        parsed_id = UUID(order_id)
    except (TypeError, ValueError):
        logger.warning("Invalid order_id metadata on payment_intent %s", order_id)
        return

    async with AsyncSessionLocal() as db:
        try:
            order_service = OrderService(db)
            order = await order_service.get_by_id(parsed_id)
            if not order:
                logger.warning(
                    "Could not resolve order %s for failed payment_intent %s",
                    order_id,
                    payment_intent.get("id"),
                )
                return

            # A later successful retry on the same session moves FAILED -> PAID.
            await _mark_pending_order_failed(
                order_service, db, order, "payment attempt failed"
            )
        except Exception:
            logger.exception("Error handling failed payment")
            await db.rollback()
            raise


async def reconcile_order_status(order: Order) -> bool:
    """Sync an unconfirmed order with Stripe; returns True if status changed.

    Covers lost or failed webhooks. Never raises: Stripe/API errors are logged
    so callers (e.g. order reads) keep working.
    """
    if order.status not in UNCONFIRMED_STATUSES:
        return False

    session_id = order.stripe_session_id
    if not session_id or not session_id.startswith("cs_"):
        return False

    previous_status = order.status
    try:
        session = await StripeService().retrieve_checkout_session(session_id)
        if session.get("payment_status") == "paid":
            await handle_successful_payment(session)
        elif session.get("status") == "expired":
            await handle_expired_payment(session)
        else:
            return False
    except Exception:
        logger.exception("Failed to reconcile order %s with Stripe", order.id)
        return False

    async with AsyncSessionLocal() as db:
        current = await OrderService(db).get_by_id(order.id)
        return bool(current and current.status != previous_status)
