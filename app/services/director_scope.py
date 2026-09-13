from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.models.gift_collection import GiftCollection
from app.models.order import Order
from app.models.user import User, UserRole


@dataclass(frozen=True)
class DirectorScope:
    """How a director's list/get queries should be filtered."""

    funeral_home_id: Optional[UUID] = None
    director_id: Optional[UUID] = None
    is_main: bool = False


def is_main_director(user: User) -> bool:
    """True when this director is the main director of their assigned funeral home."""
    if user.role != UserRole.DIRECTOR.value or not user.funeral_home_id:
        return False
    funeral_home = getattr(user, "funeral_home", None)
    if funeral_home is not None:
        return funeral_home.director_id == user.id
    directed = getattr(user, "directed_funeral_home", None)
    return directed is not None and directed.id == user.funeral_home_id


def director_data_scope(user: User) -> DirectorScope:
    """Main directors see the whole home; other directors see only their own rows."""
    if is_main_director(user):
        return DirectorScope(funeral_home_id=user.funeral_home_id, is_main=True)
    return DirectorScope(director_id=user.id, is_main=False)


def director_can_read_family(user: User, family: User) -> bool:
    if is_main_director(user):
        return (
            user.funeral_home_id is not None
            and family.funeral_home_id == user.funeral_home_id
        )
    return family.director_id == user.id


def director_can_read_collection(user: User, collection: GiftCollection) -> bool:
    if is_main_director(user):
        return (
            user.funeral_home_id is not None
            and collection.funeral_home_id == user.funeral_home_id
        )
    return collection.director_id == user.id


def director_can_read_order(user: User, order: Order) -> bool:
    if is_main_director(user):
        return (
            user.funeral_home_id is not None
            and order.funeral_home_id == user.funeral_home_id
        )
    return (
        order.gift_collection is not None
        and order.gift_collection.director_id == user.id
    )
