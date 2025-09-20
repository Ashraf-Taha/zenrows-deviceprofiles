from sqlalchemy import select

from app.db.models import DeviceProfile
from app.db.scoping import scope_profiles


def test_given_include_templates_when_scope_then_conditions_include_global_templates():
    q = select(DeviceProfile)
    scoped = scope_profiles(q, user_id="u1", include_templates=True)
    sql = str(scoped)
    assert "deleted_at" in sql
    assert "owner_id" in sql or "visibility" in sql


def test_given_exclude_templates_when_scope_then_only_owner():
    q = select(DeviceProfile)
    scoped = scope_profiles(q, user_id="u1", include_templates=False)
    sql = str(scoped)
    assert "owner_id" in sql