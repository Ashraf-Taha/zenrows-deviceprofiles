from dataclasses import dataclass, replace
from typing import List, Optional, Tuple, TypeVar, Generic
from datetime import datetime
import base64

from app.orchestrator.base import (
    BaseExecutor,
    BaseRequestTransformer,
    BaseResponseTransformer,
    BaseValidator,
)
from app.profiles.dto import CreateProfile, UpdateProfile, ProfileResponse, CloneFromTemplate
from app.profiles.repository import DeviceProfileRepository, ListFilters
from app.profiles.dto import ALLOWED_COUNTRIES
from app.db.models import DeviceType
from app.profiles.dto import VersionMeta, VersionSnapshotResponse


@dataclass
class CreateRequest:
    owner_id: str
    payload: CreateProfile


class CreateValidator(BaseValidator[CreateRequest]):
    def validate(self, request: CreateRequest) -> None:
        request.payload.model_validate(request.payload.model_dump())


class CreateExecutor(BaseExecutor[CreateRequest, ProfileResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: CreateRequest) -> ProfileResponse:
        dp = self.repo.create(request.owner_id, request.payload)
        return ProfileResponse.from_model(dp)


T = TypeVar("T")


class IdentityResponse(BaseResponseTransformer[T], Generic[T]):
    def transform(self, response: T) -> T:
        return response


@dataclass
class GetRequest:
    user_id: str
    profile_id: str


class GetValidator(BaseValidator[GetRequest]):
    def validate(self, request: GetRequest) -> None:
        if not request.profile_id:
            raise ValueError("missing_id")


class GetExecutor(BaseExecutor[GetRequest, ProfileResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: GetRequest) -> ProfileResponse:
        dp = self.repo.get_scoped(request.user_id, request.profile_id)
        return ProfileResponse.from_model(dp)


@dataclass
class ListRequest:
    user_id: str
    is_template: Optional[bool] = None
    device_type: Optional[str] = None
    country: Optional[str] = None
    q: Optional[str] = None
    limit: int = 20
    cursor: Optional[str] = None
    cursor_decoded: Optional[Tuple[datetime, str]] = None


@dataclass
class ListResponse:
    data: List[ProfileResponse]
    next_cursor: Optional[str]

class ListValidator(BaseValidator[ListRequest]):
    def validate(self, request: ListRequest) -> None:
        if request.limit < 1 or request.limit > 100:
            raise ValueError("invalid_limit")
        if request.device_type is not None and request.device_type not in {e.value for e in DeviceType}:
            raise ValueError("invalid_device_type")
        if request.country is not None:
            c = request.country.strip().lower()
            if len(c) != 2 or c not in ALLOWED_COUNTRIES:
                raise ValueError("invalid_country")

class ListRequestTransformer(BaseRequestTransformer[ListRequest]):
    def transform(self, request: ListRequest) -> ListRequest:
        country = request.country.strip().lower() if request.country is not None else None
        device_type = request.device_type.strip().lower() if request.device_type is not None else None
        q = request.q.strip() if request.q is not None else None
        decoded: Optional[Tuple[datetime, str]] = None
        if request.cursor:
            try:
                raw = base64.b64decode(request.cursor).decode("utf-8")
                parts = raw.split("|", 1)
                if len(parts) != 2:
                    raise ValueError
                ts = datetime.fromisoformat(parts[0])
                decoded = (ts, parts[1])
            except Exception:
                raise ValueError("invalid_cursor")
        return replace(request, country=country, device_type=device_type, q=q, cursor_decoded=decoded)


class ListExecutor(BaseExecutor[ListRequest, ListResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: ListRequest) -> ListResponse:
        filters = ListFilters(
            is_template=request.is_template,
            device_type=request.device_type,
            country=request.country,
            q=request.q,
            limit=request.limit,
            cursor=request.cursor_decoded,
        )
        rows, next_t = self.repo.list_scoped_page(request.user_id, filters)
        next_cursor = None
        if next_t is not None:
            iso = next_t[0].isoformat()
            token = base64.b64encode(f"{iso}|{next_t[1]}".encode("utf-8")).decode("utf-8")
            next_cursor = token
        return ListResponse(
            data=[ProfileResponse.from_model(r) for r in rows],
            next_cursor=next_cursor,
        )


@dataclass
class PatchRequest:
    owner_id: str
    profile_id: str
    payload: UpdateProfile


class PatchValidator(BaseValidator[PatchRequest]):
    def validate(self, request: PatchRequest) -> None:
        request.payload.model_validate(request.payload.model_dump())
        if request.payload.version is None:
            raise ValueError("missing_version")


class PatchExecutor(BaseExecutor[PatchRequest, ProfileResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: PatchRequest) -> ProfileResponse:
        row = self.repo.update_optimistic(request.owner_id, request.profile_id, request.payload)
        return ProfileResponse.from_model(row)


@dataclass
class DeleteRequest:
    owner_id: str
    profile_id: str


class DeleteValidator(BaseValidator[DeleteRequest]):
    def validate(self, request: DeleteRequest) -> None:
        if not request.profile_id:
            raise ValueError("missing_id")


class DeleteExecutor(BaseExecutor[DeleteRequest, dict]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: DeleteRequest) -> dict:
        self.repo.soft_delete(request.owner_id, request.profile_id)
        return {"deleted": True}


@dataclass
class CloneRequest:
    owner_id: str
    payload: CloneFromTemplate


class CloneValidator(BaseValidator[CloneRequest]):
    def validate(self, request: CloneRequest) -> None:
        request.payload.model_validate(request.payload.model_dump())


class CloneExecutor(BaseExecutor[CloneRequest, ProfileResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: CloneRequest) -> ProfileResponse:
        dp = self.repo.clone_from_template(request.owner_id, request.payload)
        return ProfileResponse.from_model(dp)


@dataclass
class VersionsRequest:
    user_id: str
    profile_id: str


class VersionsValidator(BaseValidator[VersionsRequest]):
    def validate(self, request: VersionsRequest) -> None:
        if not request.profile_id:
            raise ValueError("missing_id")


class VersionsExecutor(BaseExecutor[VersionsRequest, List[VersionMeta]]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: VersionsRequest) -> List[VersionMeta]:
        return self.repo.list_versions(request.user_id, request.profile_id)


@dataclass
class VersionRequest:
    user_id: str
    profile_id: str
    version: int


class VersionValidator(BaseValidator[VersionRequest]):
    def validate(self, request: VersionRequest) -> None:
        if not request.profile_id:
            raise ValueError("missing_id")
        if request.version is None or request.version < 1:
            raise ValueError("invalid_version")


class VersionExecutor(BaseExecutor[VersionRequest, VersionSnapshotResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: VersionRequest) -> VersionSnapshotResponse:
        return self.repo.get_version(request.user_id, request.profile_id, request.version)


@dataclass
class VersionsPageRequest:
    user_id: str
    profile_id: str
    limit: int = 20
    cursor: int | None = None


@dataclass
class VersionsPageResponse:
    data: List[VersionMeta]
    next_cursor: int | None


class VersionsPageValidator(BaseValidator[VersionsPageRequest]):
    def validate(self, request: VersionsPageRequest) -> None:
        if not request.profile_id:
            raise ValueError("missing_id")
        if request.limit < 1 or request.limit > 100:
            raise ValueError("invalid_limit")


class VersionsPageExecutor(BaseExecutor[VersionsPageRequest, VersionsPageResponse]):
    def __init__(self, repo: DeviceProfileRepository) -> None:
        self.repo = repo

    def execute(self, request: VersionsPageRequest) -> VersionsPageResponse:
        items, next_cur = self.repo.list_versions_page(request.user_id, request.profile_id, request.limit, request.cursor)
        return VersionsPageResponse(data=items, next_cursor=next_cur)
