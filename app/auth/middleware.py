from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth.repository import ApiKeyRepository
from app.auth.service import AuthError, AuthenticatedUser
from app.auth.pipeline import (
    AuthRequest,
    ApiKeyHeaderValidator,
    PrefixTransformer,
    AuthenticateExecutor,
    IdentityResponseTransformer,
)
from app.orchestrator.orchestrator import PipelineOrchestrator
from app.db.session import get_session


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/healthz", "/readyz"}:
            return await call_next(request)
        key = request.headers.get("X-API-Key")
        if not key:
            return JSONResponse({"detail": "missing_api_key"}, status_code=401)
        with get_session() as s:
            repo: ApiKeyRepository = ApiKeyRepository(s)
            orch: PipelineOrchestrator[AuthRequest, AuthenticatedUser] = PipelineOrchestrator(
                validators=[ApiKeyHeaderValidator()],
                request_transformers=[PrefixTransformer()],
                executors=[AuthenticateExecutor(repo)],
                response_transformers=[IdentityResponseTransformer()],
            )
            try:
                user = orch.run(AuthRequest(api_key=key))
            except AuthError as e:
                err = str(e)
                code = 401 if err in {"missing_api_key", "invalid_api_key"} else 400
                return JSONResponse({"detail": err}, status_code=code)
        request.state.user_id = user.user_id
        return await call_next(request)
