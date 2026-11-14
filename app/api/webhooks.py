import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.services.payment_service import (  # noqa: F401  (re-exported)
    handle_expired_payment,
    handle_payment_failed,
    handle_successful_payment,
    resolve_order_from_session,
    session_amount_matches_order,
)
from app.services.stripe_service import StripeService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Processes checkout.session.completed / expired and
       payment_intent.payment_failed events
    3. Updates order status
    4. Sends notification emails

    Events are processed before responding. If processing fails the endpoint
    returns 500 so Stripe retries the delivery (handlers are idempotent).
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

    try:
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

            await handle_successful_payment(session)
        elif event_type == "checkout.session.expired":
            await handle_expired_payment(event["data"]["object"])
        elif event_type == "payment_intent.payment_failed":
            await handle_payment_failed(event["data"]["object"])
    except Exception:
        logger.exception("Failed to process Stripe event %s (%s)", event.get("id"), event_type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )

    return {"status": "success"}
