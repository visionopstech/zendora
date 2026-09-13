from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import OrderCommission
from app.models.gift_collection import GiftCollection
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.services.director_scope import director_data_scope


class DirectorStatisticsService:
    """Aggregates dashboard statistics for a director."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_statistics(self, director: User) -> dict:
        scope = director_data_scope(director)

        collection_filters = []
        family_filters = [User.role == UserRole.FAMILY_ADMIN.value]
        order_filters = []

        if scope.is_main and scope.funeral_home_id:
            collection_filters.append(GiftCollection.funeral_home_id == scope.funeral_home_id)
            family_filters.append(User.funeral_home_id == scope.funeral_home_id)
            order_filters.append(Order.funeral_home_id == scope.funeral_home_id)
        else:
            collection_filters.append(GiftCollection.director_id == director.id)
            family_filters.append(User.director_id == director.id)
            order_filters.append(
                Order.gift_collection_id.in_(
                    select(GiftCollection.id).where(GiftCollection.director_id == director.id)
                )
            )

        total_gift_collections = await self._count(GiftCollection, collection_filters)
        total_families_enrolled = await self._count(User, family_filters)
        orders_count = await self._count(Order, order_filters)

        paid_filters = [*order_filters, Order.status == OrderStatus.PAID.value]
        sales_result = await self.db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(*paid_filters)
        )
        sales = Decimal(str(sales_result.scalar() or 0))

        commission_query = (
            select(func.coalesce(func.sum(OrderCommission.director_profit_amount), 0))
            .select_from(OrderCommission)
            .join(Order, Order.id == OrderCommission.order_id)
            .where(*paid_filters)
        )
        commission_result = await self.db.execute(commission_query)
        total_commissions = Decimal(str(commission_result.scalar() or 0))

        return {
            "total_gift_collections": total_gift_collections,
            "total_families_enrolled": total_families_enrolled,
            "orders_count": orders_count,
            "sales": sales.quantize(Decimal("0.01")),
            "total_commissions": total_commissions.quantize(Decimal("0.01")),
        }

    async def _count(self, model, filters) -> int:
        query = select(func.count()).select_from(model)
        if filters:
            query = query.where(*filters)
        result = await self.db.execute(query)
        return result.scalar() or 0
