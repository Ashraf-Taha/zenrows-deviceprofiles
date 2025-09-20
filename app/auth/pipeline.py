from dataclasses import dataclass

from app.orchestrator.base import (
    BaseExecutor,
    BaseRequestTransformer,
    BaseResponseTransformer,
    BaseValidator,
)
from app.auth.crypto import prefix_from_raw
from app.auth.repository import ApiKeyRepository
from app.auth.service import AuthService, AuthenticatedUser, AuthError


@dataclass
class AuthRequest:
    api_key: str
    prefix: str | None = None


class ApiKeyHeaderValidator(BaseValidator[AuthRequest]):
    def validate(self, request: AuthRequest) -> None:
        if not request.api_key:
            raise AuthError("missing_api_key")


class PrefixTransformer(BaseRequestTransformer[AuthRequest]):
    def transform(self, request: AuthRequest) -> AuthRequest:
        return AuthRequest(api_key=request.api_key, prefix=prefix_from_raw(request.api_key))


class AuthenticateExecutor(BaseExecutor[AuthRequest, AuthenticatedUser]):
    def __init__(self, repo: ApiKeyRepository) -> None:
        self.service = AuthService(repo)

    def execute(self, request: AuthRequest) -> AuthenticatedUser:
        if request.prefix is None:
            raise AuthError("missing_prefix")
        return self.service.authenticate_with_prefix(request.api_key, request.prefix)


class IdentityResponseTransformer(BaseResponseTransformer[AuthenticatedUser]):
    def transform(self, response: AuthenticatedUser) -> AuthenticatedUser:
        return response
