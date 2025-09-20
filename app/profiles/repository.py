import uuid
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import DeviceProfile, DeviceProfileVersion
from app.db.scoping import scope_profiles
from app.profiles.dto import CreateProfile, UpdateProfile, headers_list_to_json


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class PreconditionFailed(Exception):
    pass


@dataclass(frozen=True)
class ListFilters:
    is_template: Optional[bool] = None
    device_type: Optional[str] = None
    country: Optional[str] = None
    q: Optional[str] = None
    limit: int = 20
    cursor: Optional[Tuple[str, str]] = None


class DeviceProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, owner_id: str, data: CreateProfile) -> DeviceProfile:
        pid = f"prof_{uuid.uuid4().hex[:12]}"
        dp = DeviceProfile(
            id=pid,
            owner_id=owner_id,
            name=data.name,
            device_type=data.device_type,
            width=data.window.width,
            height=data.window.height,
            user_agent=data.user_agent,
            country=data.country,
            custom_headers=headers_list_to_json(data.custom_headers),
            is_template=data.is_template,
            visibility=data.visibility,
        )
        self.session.add(dp)
        try:
            self.session.flush()
        except IntegrityError as e:
            raise ConflictError(str(e))
        snap = {
            "id": dp.id,
            "owner_id": dp.owner_id,
            "name": dp.name,
            "device_type": dp.device_type.value,
            "window": {"width": dp.width, "height": dp.height},
            "user_agent": dp.user_agent,
            "country": dp.country,
            "custom_headers": dp.custom_headers,
            "is_template": dp.is_template,
            "visibility": dp.visibility.value,
            "version": dp.version,
        }
        self.session.add(
            DeviceProfileVersion(
                profile_id=dp.id, version=1, snapshot=snap, changed_by=owner_id
            )
        )
        self.session.flush()
        return dp

    def get_scoped(self, user_id: str, profile_id: str) -> DeviceProfile:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        q = q.where(DeviceProfile.id == profile_id)
        row = self.session.execute(q).scalars().first()
        if not row:
            raise NotFoundError("profile_not_found")
        return row

    def list_scoped(self, user_id: str, filters: ListFilters) -> List[DeviceProfile]:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        if filters.is_template is not None:
            q = q.where(DeviceProfile.is_template.is_(filters.is_template))
        if filters.device_type is not None:
            q = q.where(DeviceProfile.device_type == filters.device_type)
        if filters.country is not None:
            q = q.where(DeviceProfile.country == filters.country)
        if filters.q is not None:
            q = q.where(DeviceProfile.name.ilike(f"{filters.q}%"))
        q = q.order_by(DeviceProfile.created_at, DeviceProfile.id)
        q = q.limit(filters.limit)
        rows = self.session.execute(q).scalars().all()
        return rows

    def update_optimistic(self, owner_id: str, profile_id: str, data: UpdateProfile) -> DeviceProfile:
        current = self.get_scoped(owner_id, profile_id)
        if current.owner_id != owner_id:
            raise NotFoundError("profile_not_found")
        if data.version is None or data.version != current.version:
            raise PreconditionFailed("version_mismatch")
        if data.name is not None:
            current.name = data.name
        if data.device_type is not None:
            current.device_type = data.device_type
        if data.window is not None:
            current.width = data.window.width
            current.height = data.window.height
        if data.user_agent is not None:
            current.user_agent = data.user_agent
        if data.country is not None:
            current.country = data.country
        if data.custom_headers is not None:
            current.custom_headers = headers_list_to_json(data.custom_headers)
        if data.is_template is not None:
            current.is_template = data.is_template
        if data.visibility is not None:
            current.visibility = data.visibility
        stmt = (
            update(DeviceProfile)
            .where(and_(DeviceProfile.id == profile_id, DeviceProfile.owner_id == owner_id, DeviceProfile.version == data.version))
            .values(version=DeviceProfile.version + 1,
                    name=current.name,
                    device_type=current.device_type,
                    width=current.width,
                    height=current.height,
                    user_agent=current.user_agent,
                    country=current.country,
                    custom_headers=current.custom_headers,
                    is_template=current.is_template,
                    visibility=current.visibility)
            .returning(DeviceProfile)
        )
        try:
            row = self.session.execute(stmt).scalars().one()
        except Exception:
            raise PreconditionFailed("version_mismatch")
        snap = {
            "id": row.id,
            "owner_id": row.owner_id,
            "name": row.name,
            "device_type": row.device_type.value,
            "window": {"width": row.width, "height": row.height},
            "user_agent": row.user_agent,
            "country": row.country,
            "custom_headers": row.custom_headers,
            "is_template": row.is_template,
            "visibility": row.visibility.value,
            "version": row.version,
        }
        self.session.add(
            DeviceProfileVersion(
                profile_id=row.id, version=row.version, snapshot=snap, changed_by=owner_id
            )
        )
        self.session.flush()
        return row

    def soft_delete(self, owner_id: str, profile_id: str) -> None:
        current = self.get_scoped(owner_id, profile_id)
        if current.owner_id != owner_id:
            raise NotFoundError("profile_not_found")
        self.session.execute(
            update(DeviceProfile)
            .where(and_(DeviceProfile.id == profile_id, DeviceProfile.owner_id == owner_id, DeviceProfile.deleted_at.is_(None)))
            .values(deleted_at=func.now())
        )
        self.session.flush()
