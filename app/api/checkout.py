import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.order import CheckoutRequest, CheckoutResponse
from app.services.gift_collection_service import GiftCollectionService
from app.services.product_service import ProductService
from app.services.visitor_service import VisitorService
from app.services.order_service import OrderService
from app.services.stripe_service import StripeService
from app.models.gift_collection import GiftCollectionStatus

router = APIRouter()


@router.post("/{public_slug}/checkout", response_model=CheckoutResponse)
async def initiate_checkout(
    public_slug: str,
    checkout_data: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate checkout for a public gift collection.

    This endpoint:
    1. Validates the gift collection is published
    2. Gets or creates the visitor user
    3. Validates all gifts exist
    4. Creates a pending order
    5. Creates a Stripe Checkout session
    6. Returns the checkout URL
    """
    collection_service = GiftCollectionService(db)
    product_service = ProductService(db)
    visitor_service = VisitorService(db)
    order_service = OrderService(db)
    stripe_service = StripeService()

    collection = await collection_service.get_by_slug(public_slug, load_products=True)

    if not collection or collection.status != GiftCollectionStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift collection not found",
        )

    visitor = await visitor_service.get_or_create_visitor(
        email=checkout_data.visitor_email,
        full_name=checkout_data.visitor_name,
    )

    products = await product_service.get_by_ids(checkout_data.product_ids)

    if len(products) != len(checkout_data.product_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more products not found",
        )

    collection_product_ids = {item.product_id for item in collection.products}
    for product_id in checkout_data.product_ids:
        if product_id not in collection_product_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {product_id} is not in this gift collection",
            )

    quantities = {product.id: 1 for product in products}

    temp_session_id = f"pending_{uuid.uuid4()}"

    order = await order_service.create_order(
        visitor_id=visitor.id,
        gift_collection_id=collection.id,
        family_admin_id=collection.family_admin_id,
        stripe_session_id=temp_session_id,
        products=products,
        quantities=quantities,
    )

    try:
        checkout_session = await stripe_service.create_checkout_session(
            order_id=order.id,
            products=products,
            quantities=quantities,
            visitor_email=checkout_data.visitor_email,
        )

        order.stripe_session_id = checkout_session.session_id

        await db.commit()

        return CheckoutResponse(
            order_id=order.id,
            checkout_url=checkout_session.url,
            total_amount=order.total_amount,
        )
    except Exception as e:
        await order_service.mark_as_failed(order.id)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        )
