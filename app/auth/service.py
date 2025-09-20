from dataclasses import dataclass

from app.auth.crypto import verify_key
from app.auth.repository import ApiKeyRepository


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str


class AuthService:
    def __init__(self, repo: ApiKeyRepository) -> None:
        self.repo = repo

    def authenticate_with_prefix(self, raw_api_key: str, prefix: str) -> AuthenticatedUser:
        candidates = self.repo.find_by_prefix(prefix)
        for c in candidates:
            if c.revoked:
                continue
            if verify_key(c.key_hash, raw_api_key):
                return AuthenticatedUser(user_id=c.user_id)
        raise AuthError("invalid_api_key")
