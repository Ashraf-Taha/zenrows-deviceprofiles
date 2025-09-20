from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiKey


@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    user_id: str
    key_hash: bytes
    revoked: bool


class ApiKeyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_prefix(self, prefix: str) -> list[ApiKeyRecord]:
        stmt = select(ApiKey).where(ApiKey.key_prefix == prefix)
        rows = self.session.execute(stmt).scalars().all()
        return [
            ApiKeyRecord(
                id=r.id,
                user_id=r.user_id,
                key_hash=r.key_hash,
                revoked=r.revoked_at is not None,
            )
            for r in rows
        ]
