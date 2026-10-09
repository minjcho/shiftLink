import pytest
from pydantic import ValidationError
from app.core.config import Settings


@pytest.mark.parametrize("updates",[
    {"database_url":"sqlite:///wrong.db"}, {"session_secret":"short"}, {"allowed_origins":"*"},
    {"allowed_origins":"http://localhost:5173/path"}, {"job_lease_seconds":60},
    {"app_env":"production"}, {"job_max_attempts":0},
])
def test_invalid_settings(settings,updates):
    with pytest.raises(ValidationError):Settings(**(settings.model_dump()|updates))


def test_api_can_start_without_model_but_live_worker_cannot(settings):
    with pytest.raises(ValueError):settings.validate_live_worker()


def test_container_layout_uses_injected_environment(monkeypatch, settings):
    from app.core import config
    monkeypatch.setattr(config, "__file__", "/app/app/core/config.py")
    monkeypatch.setenv("DATABASE_URL", settings.database_url.get_secret_value())
    monkeypatch.setenv("SESSION_SECRET", settings.session_secret.get_secret_value())
    assert config.load_settings().app_env == "development"
