from app.core.config import settings


def test_given_defaults_when_loaded_then_expected_values():
    assert settings.env == "dev"
    assert settings.port == 8080
    assert settings.log_level == "info"


def test_given_env_overrides_when_loaded_then_applied(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    from app.core.config import Settings

    s = Settings()
    assert s.env == "test"
    assert s.port == 9090
    assert s.log_level == "debug"
