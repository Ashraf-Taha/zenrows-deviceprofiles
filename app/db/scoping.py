from sqlalchemy import and_, or_
from sqlalchemy.sql import Select

from app.db.models import DeviceProfile, Visibility


def scope_profiles(query: Select, user_id: str, include_templates: bool = True) -> Select:
    base = and_(DeviceProfile.deleted_at.is_(None))
    own = and_(DeviceProfile.owner_id == user_id)
    if include_templates:
        tmpl = and_(DeviceProfile.is_template.is_(True), DeviceProfile.visibility == Visibility.global_)
        cond = and_(base, or_(own, tmpl))
    else:
        cond = and_(base, own)
    return query.where(cond)
