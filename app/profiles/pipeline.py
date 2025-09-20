from dataclasses import dataclass
from typing import List, Optional

from app.orchestrator.base import (
    BaseExecutor,
    BaseRequestTransformer,
    BaseResponseTransformer,
    BaseValidator,
)
from app.profiles.dto import CreateProfile, UpdateProfile, ProfileResponse, CloneFromTemplate
from app.profiles.repository import DeviceProfileRepository, ListFilters


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


class IdentityResponse(BaseResponseTransformer[ProfileResponse]):
    def transform(self, response: ProfileResponse) -> ProfileResponse:
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


@dataclass
class ListResponse:
    data: List[ProfileResponse]
    next_cursor: Optional[str]


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
        )
        rows = self.repo.list_scoped(request.user_id, filters)
        return ListResponse(
            data=[ProfileResponse.from_model(r) for r in rows],
            next_cursor=None,
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
