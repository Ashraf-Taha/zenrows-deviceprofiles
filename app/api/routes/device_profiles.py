from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.db.session import fastapi_session
from app.orchestrator.orchestrator import PipelineOrchestrator
from app.profiles.dto import CreateProfile, UpdateProfile, CloneFromTemplate, ProfileResponse, VersionSnapshotResponse, VersionMeta
from app.profiles.pipeline import (
    CreateExecutor,
    CreateRequest,
    CreateValidator,
    CloneExecutor,
    CloneRequest,
    CloneValidator,
    DeleteExecutor,
    DeleteRequest,
    DeleteValidator,
    GetExecutor,
    GetRequest,
    GetValidator,
    IdentityResponse,
    ListExecutor,
    ListRequest,
    ListResponse,
    ListValidator,
    ListRequestTransformer,
    PatchExecutor,
    PatchRequest,
    PatchValidator,
    VersionsExecutor,
    VersionsRequest,
    VersionsValidator,
    VersionExecutor,
    VersionRequest,
    VersionValidator,
    VersionsPageExecutor,
    VersionsPageRequest,
    VersionsPageValidator,
    VersionsPageResponse,
)
from app.profiles.repository import DeviceProfileRepository, NotFoundError, PreconditionFailed, ConflictError
from app.core.idempotency import IdempotencyStore


router = APIRouter(prefix="/v1/device-profiles", tags=["device-profiles"])


def _repo(session: Session) -> DeviceProfileRepository:
    return DeviceProfileRepository(session)


def _user_id(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="unauthorized")
    return uid


@router.post("/")
def create_profile(payload: dict, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    store = IdempotencyStore(session)
    try:
        owner_id = _user_id(request)
        idem_key = request.headers.get("Idempotency-Key")
        if idem_key:
            cached = store.get(owner_id, idem_key)
            if cached is not None:
                return cached
        if "template_id" in payload:
            clone = CloneFromTemplate.model_validate(payload)
            clone_orch = PipelineOrchestrator[CloneRequest, ProfileResponse](
                validators=[CloneValidator()],
                executors=[CloneExecutor(repo)],
                response_transformers=[IdentityResponse[ProfileResponse]()],
            )
            resp = clone_orch.run(CloneRequest(owner_id=owner_id, payload=clone))
        else:
            create = CreateProfile.model_validate(payload)
            create_orch = PipelineOrchestrator[CreateRequest, ProfileResponse](
                validators=[CreateValidator()],
                executors=[CreateExecutor(repo)],
                response_transformers=[IdentityResponse[ProfileResponse]()],
            )
            resp = create_orch.run(CreateRequest(owner_id=owner_id, payload=create))
        if idem_key:
            payload_json = jsonable_encoder(resp)
            store.save(owner_id, idem_key, payload_json)
        session.commit()
        return resp
    except ConflictError:
        raise HTTPException(status_code=409, detail="conflict")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")
    except ValidationError:
        raise HTTPException(status_code=422, detail="validation_error")


@router.get("/{profile_id}")
def get_profile(profile_id: str, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    orch = PipelineOrchestrator[GetRequest, ProfileResponse](
        validators=[GetValidator()],
        executors=[GetExecutor(repo)],
        response_transformers=[IdentityResponse[ProfileResponse]()],
    )
    try:
        resp = orch.run(GetRequest(user_id=_user_id(request), profile_id=profile_id))
        etag = str(resp.version)
        inm = request.headers.get("If-None-Match")
        if inm is not None and inm == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return JSONResponse(content=jsonable_encoder(resp), headers={"ETag": etag})
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/")
def list_profiles(
    request: Request,
    is_template: bool | None = None,
    device_type: str | None = None,
    country: str | None = None,
    q: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    session: Session = Depends(fastapi_session),
):
    repo = _repo(session)
    orch = PipelineOrchestrator[ListRequest, ListResponse](
        validators=[ListValidator()],
        request_transformers=[ListRequestTransformer()],
        executors=[ListExecutor(repo)],
        response_transformers=[IdentityResponse[ListResponse]()],
    )
    try:
        return orch.run(
            ListRequest(
                user_id=_user_id(request),
                is_template=is_template,
                device_type=device_type,
                country=country,
                q=q,
                limit=limit,
                cursor=cursor,
            )
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_parameters")


@router.patch("/{profile_id}")
def patch_profile(profile_id: str, payload: UpdateProfile, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    orch = PipelineOrchestrator[PatchRequest, ProfileResponse](
        validators=[PatchValidator()],
        executors=[PatchExecutor(repo)],
        response_transformers=[IdentityResponse[ProfileResponse]()],
    )
    try:
        out = orch.run(PatchRequest(owner_id=_user_id(request), profile_id=profile_id, payload=payload))
        session.commit()
        return out
    except PreconditionFailed:
        raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail="version_mismatch")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")
    except ConflictError:
        raise HTTPException(status_code=409, detail="conflict")


@router.delete("/{profile_id}")
def delete_profile(profile_id: str, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    orch = PipelineOrchestrator[DeleteRequest, dict](
        validators=[DeleteValidator()],
        executors=[DeleteExecutor(repo)],
        response_transformers=[IdentityResponse[dict]()],
    )
    try:
        out = orch.run(DeleteRequest(owner_id=_user_id(request), profile_id=profile_id))
        session.commit()
        return out
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")


@router.get("/{profile_id}/versions")
def list_profile_versions(profile_id: str, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    orch = PipelineOrchestrator[VersionsRequest, list[VersionMeta]](
        validators=[VersionsValidator()],
        executors=[VersionsExecutor(repo)],
        response_transformers=[IdentityResponse[list[VersionMeta]]()],
    )
    try:
        return orch.run(VersionsRequest(user_id=_user_id(request), profile_id=profile_id))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_parameters")


@router.get("/{profile_id}/versions:page")
def list_profile_versions_page(
    profile_id: str,
    request: Request,
    limit: int = 20,
    cursor: int | None = None,
    session: Session = Depends(fastapi_session),
):
    repo = _repo(session)
    orch = PipelineOrchestrator[VersionsPageRequest, VersionsPageResponse](
        validators=[VersionsPageValidator()],
        executors=[VersionsPageExecutor(repo)],
        response_transformers=[IdentityResponse[VersionsPageResponse]()],
    )
    try:
        return orch.run(VersionsPageRequest(user_id=_user_id(request), profile_id=profile_id, limit=limit, cursor=cursor))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_parameters")


@router.get("/{profile_id}/versions/{version}")
def get_profile_version(profile_id: str, version: int, request: Request, session: Session = Depends(fastapi_session)):
    repo = _repo(session)
    orch = PipelineOrchestrator[VersionRequest, VersionSnapshotResponse](
        validators=[VersionValidator()],
        executors=[VersionExecutor(repo)],
        response_transformers=[IdentityResponse[VersionSnapshotResponse]()],
    )
    try:
        return orch.run(VersionRequest(user_id=_user_id(request), profile_id=profile_id, version=version))
    except NotFoundError:
        raise HTTPException(status_code=404, detail="not_found")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_parameters")
