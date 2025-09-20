from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IdempotencyKey


class IdempotencyStore:
    def __init__(self, session: Session, ttl_seconds: Optional[int] = 24 * 60 * 60) -> None:
        self.session = session
        self.ttl_seconds = ttl_seconds

    def get(self, owner_id: str, key: str) -> Optional[dict]:
        q = select(IdempotencyKey).where(IdempotencyKey.key == key, IdempotencyKey.owner_id == owner_id)
        row = self.session.execute(q).scalars().first()
        if not row:
            return None
        if self.ttl_seconds is not None:
            now = datetime.now(timezone.utc)
            created = row.created_at if row.created_at.tzinfo is not None else row.created_at.replace(tzinfo=timezone.utc)
            if created < now - timedelta(seconds=self.ttl_seconds):
                return None
        return row.response

    def save(self, owner_id: str, key: str, response: dict) -> None:
        rec = IdempotencyKey(key=key, owner_id=owner_id, response=response)
        self.session.merge(rec)
        self.session.flush()
