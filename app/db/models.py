import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import func

from app.db.base import Base


class DeviceType(enum.Enum):
    desktop = "desktop"
    mobile = "mobile"


class Visibility(enum.Enum):
    private = "private"
    global_ = "global"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    key_hash: Mapped[bytes] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class DeviceProfile(Base):
    __tablename__ = "device_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    device_type: Mapped[DeviceType] = mapped_column(Enum(DeviceType, name="device_type"), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(String, nullable=False)
    custom_headers: Mapped[dict | None] = mapped_column(JSON)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    visibility: Mapped[Visibility] = mapped_column(Enum(Visibility, name="visibility"), nullable=False, server_default=text("'private'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("width BETWEEN 1 AND 10000 AND height BETWEEN 1 AND 10000", name="chk_window"),
        CheckConstraint("country ~ '^[a-z]{2}$'", name="chk_country"),
        Index("idx_profiles_owner", "owner_id", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_profiles_type", "device_type", postgresql_where=text("deleted_at IS NULL")),
        Index("idx_profiles_tmpl", "is_template", postgresql_where=text("deleted_at IS NULL")),
    Index("uniq_owner_name_not_deleted", "owner_id", text("lower(name)"), unique=True, postgresql_where=text("deleted_at IS NULL")),
    )


class DeviceProfileVersion(Base):
    __tablename__ = "device_profile_versions"
    profile_id: Mapped[str] = mapped_column(String, ForeignKey("device_profiles.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False)
