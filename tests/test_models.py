from app.db.base import Base


def test_given_models_when_metadata_collected_then_tables_present():
    names = {t.name for t in Base.metadata.sorted_tables}
    assert "users" in names
    assert "api_keys" in names
    assert "device_profiles" in names
    assert "device_profile_versions" in names
    assert "idempotency_keys" in names
