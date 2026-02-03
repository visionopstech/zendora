import stripe
from typing import List
from uuid import UUID
from decimal import Decimal

from app.core.config import settings
from app.models.product import Product


# Configure Stripe
stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Service for Stripe payment operations."""
    
    async def create_checkout_session(
        self,
        order_id: UUID,
        products: List[Product],
        quantities: dict[UUID, int],
        visitor_email: str
    ) -> str:
        """
        Create a Stripe Checkout session.
        
        Args:
            order_id: ID of the order
            products: List of Product objects
            quantities: Dict mapping product_id to quantity
            visitor_email: Email of the visitor
            
        Returns:
            str: Stripe Checkout session URL
        """
        # Build line items
        line_items = []
        for product in products:
            quantity = quantities.get(product.id, 1)
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                        'description': product.description or '',
                        'images': product.images[:5] if product.images else []  # Max 5 images
                    },
                    'unit_amount': int(product.price * 100)  # Convert to cents
                },
                'quantity': quantity
            })
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{settings.frontend_url}/order/{order_id}/success",
            cancel_url=f"{settings.frontend_url}/order/{order_id}/cancel",
            metadata={
                'order_id': str(order_id)
            },
            customer_email=visitor_email,
            expires_at=int((stripe.util.convert_to_stripe_object({'time': 'now'})['time'] + 1800))  # 30 minutes
        )
        
        return session.url
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str
    ) -> dict:
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
            settings.stripe_webhook_secret
        )
