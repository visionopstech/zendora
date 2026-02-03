from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.core.database import AsyncSessionLocal
from app.services.stripe_service import StripeService
from app.services.order_service import OrderService
from app.core.config import settings

router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle Stripe webhook events.
    
    This endpoint:
    1. Verifies the webhook signature
    2. Processes checkout.session.completed events
    3. Updates order status
    4. Sends notification emails
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )
    
    stripe_service = StripeService()
    
    try:
        # Verify webhook signature
        event = stripe_service.verify_webhook_signature(payload, sig_header)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    # Handle the event
    event_type = event['type']
    
    if event_type == 'checkout.session.completed':
        session = event['data']['object']
        
        # Process payment in background
        background_tasks.add_task(
            handle_successful_payment,
            session
        )
    elif event_type == 'checkout.session.expired':
        session = event['data']['object']
        
        # Mark order as failed
        background_tasks.add_task(
            handle_expired_payment,
            session
        )
    
    return {"status": "success"}


async def handle_successful_payment(session: dict):
    """
    Handle successful payment completion.
    
    Args:
        session: Stripe checkout session object
    """
    # Create a new database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            order_service = OrderService(db)
            
            # Get order ID from metadata
            order_id = session['metadata'].get('order_id')
            
            if not order_id:
                print(f"Error: No order_id in session metadata")
                return
            
            # Get order
            from uuid import UUID
            order = await order_service.get_by_id(UUID(order_id), load_products=True)
            
            if not order:
                print(f"Error: Order {order_id} not found")
                return
            
            # Mark as paid
            await order_service.mark_as_paid(order.id)
            await db.commit()
            
            # Reload order with relationships
            await db.refresh(order, ['visitor', 'admin', 'wishlist', 'products'])
            await db.refresh(order.wishlist, ['manager'])
            
            print(f"Order {order_id} marked as paid")
            
            # Send notification emails
            from app.services.email_service import EmailService
            email_service = EmailService()
            await email_service.send_purchase_confirmation_emails(order)
            
        except Exception as e:
            print(f"Error handling successful payment: {str(e)}")
            await db.rollback()


async def handle_expired_payment(session: dict):
    """
    Handle expired checkout session.
    
    Args:
        session: Stripe checkout session object
    """
    async with AsyncSessionLocal() as db:
        try:
            order_service = OrderService(db)
            
            # Get order ID from metadata
            order_id = session['metadata'].get('order_id')
            
            if not order_id:
                return
            
            # Get order
            from uuid import UUID
            order = await order_service.get_by_id(UUID(order_id))
            
            if not order:
                return
            
            # Mark as failed
            await order_service.mark_as_failed(order.id)
            await db.commit()
            
            print(f"Order {order_id} marked as failed (session expired)")
            
        except Exception as e:
            print(f"Error handling expired payment: {str(e)}")
            await db.rollback()
