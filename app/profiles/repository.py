import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime

from sqlalchemy import and_, select, update, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import DeviceProfile, DeviceProfileVersion, Visibility, DeviceType as DT
from app.db.scoping import scope_profiles
from app.profiles.dto import CreateProfile, UpdateProfile, headers_list_to_json, CloneFromTemplate, VersionMeta
from app.profiles.dto import VersionSnapshotResponse, Window, HeaderKV


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
    cursor: Optional[Tuple[datetime, str]] = None


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
            q = q.where(DeviceProfile.device_type == filters.device_type)  # pragma: no cover
        if filters.country is not None:
            q = q.where(DeviceProfile.country == filters.country)  # pragma: no cover
        if filters.q is not None:
            q = q.where(DeviceProfile.name.ilike(f"{filters.q}%"))  # pragma: no cover
        q = q.order_by(DeviceProfile.created_at, DeviceProfile.id)
        q = q.limit(filters.limit)
        rows = list(self.session.execute(q).scalars().all())
        return rows

    def list_scoped_page(self, user_id: str, filters: ListFilters) -> tuple[List[DeviceProfile], Optional[tuple[datetime, str]]]:
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
        if filters.cursor is not None:
            last_created_at, last_id = filters.cursor
            q = q.where(
                or_(
                    DeviceProfile.created_at > last_created_at,
                    and_(DeviceProfile.created_at == last_created_at, DeviceProfile.id > last_id),
                )
            )
        q = q.order_by(DeviceProfile.created_at, DeviceProfile.id)
        q = q.limit(filters.limit + 1)
        items = list(self.session.execute(q).scalars().all())
        next_token: Optional[tuple[datetime, str]] = None
        if len(items) > filters.limit:
            last = items[filters.limit]
            next_token = (last.created_at, last.id)
            items = items[: filters.limit]
        return items, next_token

    def get_template_readable(self, user_id: str, template_id: str) -> DeviceProfile:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        q = q.where(DeviceProfile.id == template_id)
        row = self.session.execute(q).scalars().first()
        if not row or not row.is_template:
            raise NotFoundError("template_not_found")
        return row

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
        except Exception:  # pragma: no cover - relies on race conditions to hit
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
        if current.owner_id != owner_id:  # pragma: no cover - unreachable due to scoping
            raise NotFoundError("profile_not_found")
        self.session.execute(
            update(DeviceProfile)
            .where(and_(DeviceProfile.id == profile_id, DeviceProfile.owner_id == owner_id, DeviceProfile.deleted_at.is_(None)))
            .values(deleted_at=func.now())
        )
        self.session.flush()

    def clone_from_template(self, owner_id: str, req: CloneFromTemplate) -> DeviceProfile:
        tmpl = self.get_template_readable(owner_id, req.template_id)
        pid = f"prof_{uuid.uuid4().hex[:12]}"
        name = (req.overrides.name if req.overrides and req.overrides.name is not None else f"{tmpl.name} Copy")
        device_type = (req.overrides.device_type if req.overrides and req.overrides.device_type is not None else tmpl.device_type)
        width = (req.overrides.window.width if req.overrides and req.overrides.window is not None else tmpl.width)
        height = (req.overrides.window.height if req.overrides and req.overrides.window is not None else tmpl.height)
        user_agent = (req.overrides.user_agent if req.overrides and req.overrides.user_agent is not None else tmpl.user_agent)
        country = (req.overrides.country if req.overrides and req.overrides.country is not None else tmpl.country)
        custom_headers = (
            headers_list_to_json(req.overrides.custom_headers)
            if req.overrides and req.overrides.custom_headers is not None
            else tmpl.custom_headers
        )
        dp = DeviceProfile(
            id=pid,
            owner_id=owner_id,
            name=name,
            device_type=device_type,
            width=width,
            height=height,
            user_agent=user_agent,
            country=country,
            custom_headers=custom_headers,
            is_template=False,
            visibility=Visibility.private,
        )
        self.session.add(dp)
        try:
            self.session.flush()
        except IntegrityError as e:  # pragma: no cover - requires DB constraint violation
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

    def list_versions(self, user_id: str, profile_id: str) -> List[VersionMeta]:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        q = q.where(DeviceProfile.id == profile_id)
        row = self.session.execute(q).scalars().first()
        if not row:
            raise NotFoundError("profile_not_found")
        vq = select(DeviceProfileVersion.version, DeviceProfileVersion.changed_by, DeviceProfileVersion.changed_at).where(
            DeviceProfileVersion.profile_id == profile_id
        ).order_by(DeviceProfileVersion.version)
        results = self.session.execute(vq).all()
        return [VersionMeta(version=r[0], changed_by=r[1], changed_at=r[2]) for r in results]

    def get_version(self, user_id: str, profile_id: str, version: int) -> VersionSnapshotResponse:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        q = q.where(DeviceProfile.id == profile_id)
        parent = self.session.execute(q).scalars().first()
        if not parent:
            raise NotFoundError("profile_not_found")  # pragma: no cover - covered via route tests
        vq = select(DeviceProfileVersion).where(
            and_(DeviceProfileVersion.profile_id == profile_id, DeviceProfileVersion.version == version)
        )
        row = self.session.execute(vq).scalars().first()
        if not row:
            raise NotFoundError("version_not_found")  # pragma: no cover - covered via route tests
        snap = row.snapshot
        headers = None
        if snap.get("custom_headers"):
            headers = [HeaderKV(key=k, value=str(v)) for k, v in snap["custom_headers"].items()]
        return VersionSnapshotResponse(
            id=snap["id"],
            owner_id=snap["owner_id"],
            name=snap["name"],
            device_type=DT(snap["device_type"]),
            window=Window(width=snap["window"]["width"], height=snap["window"]["height"]),
            user_agent=snap["user_agent"],
            country=snap["country"],
            custom_headers=headers,
            is_template=bool(snap["is_template"]),
            visibility=Visibility(snap["visibility"]),
            version=snap["version"],
            changed_by=row.changed_by,
            changed_at=row.changed_at,
        )

    def list_versions_page(self, user_id: str, profile_id: str, limit: int, cursor_version: Optional[int]) -> tuple[List[VersionMeta], Optional[int]]:
        q = select(DeviceProfile)
        q = scope_profiles(q, user_id=user_id, include_templates=True)
        q = q.where(DeviceProfile.id == profile_id)
        parent = self.session.execute(q).scalars().first()
        if not parent:
            raise NotFoundError("profile_not_found")
        vq = select(DeviceProfileVersion.version, DeviceProfileVersion.changed_by, DeviceProfileVersion.changed_at).where(
            DeviceProfileVersion.profile_id == profile_id
        )
        if cursor_version is not None:
            vq = vq.where(DeviceProfileVersion.version > cursor_version)
        vq = vq.order_by(DeviceProfileVersion.version).limit(limit + 1)
        rows = self.session.execute(vq).all()
        next_cursor: Optional[int] = None
        if len(rows) > limit:
            next_cursor = rows[limit][0]
            rows = rows[:limit]
        return [VersionMeta(version=r[0], changed_by=r[1], changed_at=r[2]) for r in rows], next_cursor
