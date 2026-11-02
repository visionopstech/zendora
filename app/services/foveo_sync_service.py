import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.models.foveo_sync_event import FoveoSyncEvent
from app.models.funeral_home import FuneralHome
from app.models.user import User, UserRole
from app.schemas.foveo_sync import (
    FoveoAddress,
    FoveoEntityStatus,
    FoveoEventType,
    FoveoFamilyBlock,
    FoveoFuneralHomeBlock,
    FoveoSyncEntityResult,
    FoveoSyncRequest,
    FoveoSyncResponse,
    FoveoUserBlock,
)
from app.utils.foveo import is_placeholder_email, normalize_password_hash

logger = logging.getLogger(__name__)

_HOME_EVENTS = {
    FoveoEventType.FUNERAL_HOME_UPDATED,
    FoveoEventType.STREAM_CREATED,
    FoveoEventType.STREAM_UPDATED,
    FoveoEventType.MANUAL,
}
_STREAM_PERSON_EVENTS = {
    FoveoEventType.STREAM_CREATED,
    FoveoEventType.STREAM_UPDATED,
    FoveoEventType.MANUAL,
}
_APPLIED_STATUSES = {
    FoveoEntityStatus.CREATED,
    FoveoEntityStatus.UPDATED,
    FoveoEntityStatus.UNCHANGED,
}


class FoveoSyncService:
    """One-way Foveo → Zendora upsert. Never emails credentials or hashes passwords."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync(self, payload: FoveoSyncRequest) -> FoveoSyncResponse:
        existing = await self._get_event(payload.event_id)
        if existing:
            return FoveoSyncResponse.model_validate(existing.result)

        logger.info(
            "Foveo sync event=%s event_id=%s stream_id=%s",
            payload.event.value,
            payload.event_id,
            payload.foveo_stream_id,
        )

        process_home = payload.event in _HOME_EVENTS
        if process_home and payload.funeral_home is None:
            raise ValidationError("funeral_home is required for this event")

        allow_create = payload.event != FoveoEventType.USER_UPDATED
        response = FoveoSyncResponse()
        funeral_home: Optional[FuneralHome] = None
        main_user: Optional[User] = None
        stream_user: Optional[User] = None

        if process_home and payload.funeral_home is not None:
            response.funeral_home, funeral_home = await self._upsert_funeral_home(
                payload.funeral_home
            )

        if payload.main_director is not None:
            response.main_director, main_user = await self._upsert_user(
                payload.main_director,
                role=UserRole.DIRECTOR,
                funeral_home=funeral_home if process_home else None,
                allow_create=allow_create,
                assign_main=process_home,
            )

        if payload.event in _STREAM_PERSON_EVENTS or (
            payload.event == FoveoEventType.USER_UPDATED and payload.stream_director is not None
        ):
            if payload.stream_director is not None:
                same_as_main = (
                    payload.main_director is not None
                    and payload.stream_director.foveo_user_id
                    == payload.main_director.foveo_user_id
                    and main_user is not None
                    and response.main_director is not None
                    and response.main_director.status in _APPLIED_STATUSES
                )
                if same_as_main:
                    response.stream_director = FoveoSyncEntityResult(
                        status=FoveoEntityStatus.UNCHANGED,
                        id=main_user.id,
                    )
                    stream_user = main_user
                else:
                    response.stream_director, stream_user = await self._upsert_user(
                        payload.stream_director,
                        role=UserRole.DIRECTOR,
                        funeral_home=funeral_home if process_home else None,
                        allow_create=allow_create,
                        assign_main=False,
                    )

        if payload.event in _STREAM_PERSON_EVENTS or (
            payload.event == FoveoEventType.USER_UPDATED and payload.family is not None
        ):
            if payload.family is not None:
                director_id = None
                if stream_user is not None and (
                    response.stream_director is None
                    or response.stream_director.status in _APPLIED_STATUSES
                ):
                    director_id = stream_user.id
                elif main_user is not None and (
                    response.main_director is None
                    or response.main_director.status in _APPLIED_STATUSES
                ):
                    director_id = main_user.id
                response.family, _ = await self._upsert_family(
                    payload.family,
                    funeral_home=funeral_home if process_home else None,
                    director_id=director_id,
                    allow_create=allow_create,
                )

        await self._record_event(payload, response)
        return response

    async def _get_event(self, event_id: UUID) -> Optional[FoveoSyncEvent]:
        result = await self.db.execute(
            select(FoveoSyncEvent).where(FoveoSyncEvent.event_id == event_id)
        )
        return result.scalar_one_or_none()

    async def _record_event(
        self, payload: FoveoSyncRequest, response: FoveoSyncResponse
    ) -> None:
        event = FoveoSyncEvent(
            event_id=payload.event_id,
            received_at=datetime.utcnow(),
            foveo_stream_id=payload.foveo_stream_id,
            result=response.model_dump(mode="json"),
        )
        self.db.add(event)
        await self.db.flush()

    async def _get_funeral_home_by_foveo_id(
        self, foveo_id: int
    ) -> Optional[FuneralHome]:
        result = await self.db.execute(
            select(FuneralHome).where(FuneralHome.foveo_funeral_home_id == foveo_id)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_foveo_id(self, foveo_user_id: int) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.foveo_user_id == foveo_user_id)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _upsert_funeral_home(
        self, block: FoveoFuneralHomeBlock
    ) -> tuple[FoveoSyncEntityResult, FuneralHome]:
        address = _address_dict(block.address)
        email = _normalize_email(block.email)
        existing = await self._get_funeral_home_by_foveo_id(block.foveo_id)
        if existing is None:
            home = FuneralHome(
                id=uuid4(),
                name=block.name,
                email=email,
                phone=block.phone,
                address=address,
                is_active=block.is_active,
                foveo_funeral_home_id=block.foveo_id,
            )
            self.db.add(home)
            await self.db.flush()
            return (
                FoveoSyncEntityResult(status=FoveoEntityStatus.CREATED, id=home.id),
                home,
            )

        changed = (
            existing.name != block.name
            or existing.email != email
            or existing.phone != block.phone
            or existing.address != address
            or existing.is_active != block.is_active
        )
        if changed:
            existing.name = block.name
            existing.email = email
            existing.phone = block.phone
            existing.address = address
            existing.is_active = block.is_active
            await self.db.flush()
            return (
                FoveoSyncEntityResult(status=FoveoEntityStatus.UPDATED, id=existing.id),
                existing,
            )
        return (
            FoveoSyncEntityResult(status=FoveoEntityStatus.UNCHANGED, id=existing.id),
            existing,
        )

    async def _upsert_user(
        self,
        block: FoveoUserBlock,
        *,
        role: UserRole,
        funeral_home: Optional[FuneralHome],
        allow_create: bool,
        assign_main: bool,
        director_id: Optional[UUID] = None,
        deceased_first_name: Optional[str] = None,
        deceased_last_name: Optional[str] = None,
        address: Optional[dict] = None,
        is_family: bool = False,
    ) -> tuple[FoveoSyncEntityResult, Optional[User]]:
        linked = await self._get_user_by_foveo_id(block.foveo_user_id)
        if linked is not None:
            result = await self._update_linked_user(
                linked,
                block,
                funeral_home=funeral_home,
                director_id=director_id,
                deceased_first_name=deceased_first_name,
                deceased_last_name=deceased_last_name,
                address=address,
            )
            if result.status in _APPLIED_STATUSES and assign_main and funeral_home is not None:
                conflict = await self._assign_main_director(funeral_home, linked)
                if conflict is not None:
                    return conflict, linked
            return result, linked

        email = _normalize_email(block.email)
        if is_family and is_placeholder_email(
            email, settings.foveo_placeholder_email_domains
        ):
            return (
                FoveoSyncEntityResult(
                    status=FoveoEntityStatus.SKIPPED_PLACEHOLDER_EMAIL,
                    detail="Placeholder family email is not synced until a real email is set",
                ),
                None,
            )

        if not allow_create:
            return (
                FoveoSyncEntityResult(
                    status=FoveoEntityStatus.SKIPPED,
                    detail="user.updated only updates an already-linked Foveo user",
                ),
                None,
            )

        if not email:
            return (
                FoveoSyncEntityResult(
                    status=FoveoEntityStatus.SKIPPED,
                    detail="email is required to create a user",
                ),
                None,
            )

        existing_email = await self._get_user_by_email(email)
        if existing_email is not None:
            return (
                FoveoSyncEntityResult(
                    status=FoveoEntityStatus.SKIPPED_EXISTING_USER,
                    id=existing_email.id,
                    detail="A Zendora user already owns this email and was left unchanged",
                ),
                None,
            )

        user = User(
            id=uuid4(),
            email=email,
            password_hash=normalize_password_hash(block.password_hash),
            first_name=block.first_name,
            last_name=block.last_name,
            role=role.value,
            is_active=block.is_active,
            foveo_user_id=block.foveo_user_id,
            funeral_home_id=funeral_home.id if funeral_home is not None else None,
            director_id=director_id,
            deceased_first_name=deceased_first_name,
            deceased_last_name=deceased_last_name,
            address=address,
        )
        self.db.add(user)
        await self.db.flush()

        result = FoveoSyncEntityResult(status=FoveoEntityStatus.CREATED, id=user.id)
        if assign_main and funeral_home is not None:
            conflict = await self._assign_main_director(funeral_home, user)
            if conflict is not None:
                return conflict, user
        return result, user

    async def _upsert_family(
        self,
        block: FoveoFamilyBlock,
        *,
        funeral_home: Optional[FuneralHome],
        director_id: Optional[UUID],
        allow_create: bool,
    ) -> tuple[FoveoSyncEntityResult, Optional[User]]:
        return await self._upsert_user(
            block,
            role=UserRole.FAMILY_ADMIN,
            funeral_home=funeral_home,
            allow_create=allow_create,
            assign_main=False,
            director_id=director_id,
            deceased_first_name=block.deceased_first_name,
            deceased_last_name=block.deceased_last_name,
            address=_address_dict(block.address),
            is_family=True,
        )

    async def _update_linked_user(
        self,
        user: User,
        block: FoveoUserBlock,
        *,
        funeral_home: Optional[FuneralHome],
        director_id: Optional[UUID],
        deceased_first_name: Optional[str],
        deceased_last_name: Optional[str],
        address: Optional[dict],
    ) -> FoveoSyncEntityResult:
        new_email = _normalize_email(block.email)
        if new_email and new_email != (user.email or "").lower():
            other = await self._get_user_by_email(new_email)
            if other is not None and other.id != user.id:
                return FoveoSyncEntityResult(
                    status=FoveoEntityStatus.CONFLICT,
                    id=user.id,
                    detail="New email belongs to a different Zendora user; nothing was changed",
                )

        new_hash = (
            normalize_password_hash(block.password_hash)
            if block.password_hash is not None
            else user.password_hash
        )
        new_email_value = new_email or user.email
        funeral_home_id = funeral_home.id if funeral_home is not None else user.funeral_home_id

        changed = (
            user.email != new_email_value
            or user.first_name != block.first_name
            or user.last_name != block.last_name
            or user.is_active != block.is_active
            or user.password_hash != new_hash
            or user.funeral_home_id != funeral_home_id
            or (director_id is not None and user.director_id != director_id)
            or (
                deceased_first_name is not None
                and user.deceased_first_name != deceased_first_name
            )
            or (
                deceased_last_name is not None
                and user.deceased_last_name != deceased_last_name
            )
            or (address is not None and user.address != address)
        )
        if not changed:
            return FoveoSyncEntityResult(status=FoveoEntityStatus.UNCHANGED, id=user.id)

        user.email = new_email_value
        user.first_name = block.first_name
        user.last_name = block.last_name
        user.is_active = block.is_active
        user.password_hash = new_hash
        if funeral_home is not None:
            user.funeral_home_id = funeral_home.id
        if director_id is not None:
            user.director_id = director_id
        if deceased_first_name is not None:
            user.deceased_first_name = deceased_first_name
        if deceased_last_name is not None:
            user.deceased_last_name = deceased_last_name
        if address is not None:
            user.address = address
        await self.db.flush()
        return FoveoSyncEntityResult(status=FoveoEntityStatus.UPDATED, id=user.id)

    async def _assign_main_director(
        self, funeral_home: FuneralHome, user: User
    ) -> Optional[FoveoSyncEntityResult]:
        if funeral_home.director_id is None or funeral_home.director_id == user.id:
            funeral_home.director_id = user.id
            user.funeral_home_id = funeral_home.id
            await self.db.flush()
            return None

        current = await self._get_user_by_id(funeral_home.director_id)
        if current is not None and current.foveo_user_id is None:
            return FoveoSyncEntityResult(
                status=FoveoEntityStatus.CONFLICT,
                id=user.id,
                detail="Funeral home already has a Zendora-native main director; not replaced",
            )

        funeral_home.director_id = user.id
        user.funeral_home_id = funeral_home.id
        await self.db.flush()
        return None


def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    stripped = email.strip().lower()
    return stripped or None


def _address_dict(address: Optional[FoveoAddress]) -> Optional[dict]:
    if address is None:
        return None
    return address.model_dump()
