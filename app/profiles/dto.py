from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models import DeviceProfile, DeviceType, Visibility


ALLOWED_COUNTRIES = {
    "us",
    "gb",
    "de",
    "fr",
    "es",
    "it",
    "ca",
    "au",
}


class Window(BaseModel):
    width: int = Field(ge=1, le=10000)
    height: int = Field(ge=1, le=10000)


class HeaderKV(BaseModel):
    key: str
    value: str

    @field_validator("key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        k = v.strip().lower()
        if k in {"host", "content-length"}:
            raise ValueError("header_not_allowed")
        if not k:
            raise ValueError("header_key_empty")
        return k


class CreateProfile(BaseModel):
    name: str
    device_type: DeviceType
    window: Window
    user_agent: str
    country: str
    custom_headers: Optional[List[HeaderKV]] = None
    is_template: bool = False
    visibility: Visibility = Visibility.private

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        c = v.strip().lower()
        if len(c) != 2 or c not in ALLOWED_COUNTRIES:
            raise ValueError("invalid_country")
        return c


class UpdateProfile(BaseModel):
    name: Optional[str] = None
    device_type: Optional[DeviceType] = None
    window: Optional[Window] = None
    user_agent: Optional[str] = None
    country: Optional[str] = None
    custom_headers: Optional[List[HeaderKV]] = None
    is_template: Optional[bool] = None
    visibility: Optional[Visibility] = None
    version: Optional[int] = None

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        c = v.strip().lower()
        if len(c) != 2 or c not in ALLOWED_COUNTRIES:
            raise ValueError("invalid_country")
        return c

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateProfile":
        data = self.model_dump(exclude_none=True)
        if not any(k for k in data.keys() if k != "version"):
            raise ValueError("no_updates_provided")
        return self


class ProfileResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    device_type: DeviceType
    window: Window
    user_agent: str
    country: str
    custom_headers: List[HeaderKV] | None
    is_template: bool
    visibility: Visibility
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    @classmethod
    def from_model(cls, m: DeviceProfile) -> "ProfileResponse":
        headers = None
        if m.custom_headers:
            items = []
            for k, v in m.custom_headers.items():
                items.append(HeaderKV(key=k, value=str(v)))
            headers = items
        return cls(
            id=m.id,
            owner_id=m.owner_id,
            name=m.name,
            device_type=m.device_type,
            window=Window(width=m.width, height=m.height),
            user_agent=m.user_agent,
            country=m.country,
            custom_headers=headers,
            is_template=bool(m.is_template),
            visibility=m.visibility,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
            deleted_at=m.deleted_at,
        )


def headers_list_to_json(headers: Optional[List[HeaderKV]]) -> Optional[Dict[str, Any]]:
    if headers is None:
        return None
    out: Dict[str, Any] = {}
    for h in headers:
        out[h.key] = h.value
    return out
