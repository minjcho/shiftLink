import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy.engine import make_url
from typing import Literal


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    app_env: Literal["development", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    database_url: SecretStr
    session_secret: SecretStr
    session_cookie_secure: bool = False
    demo_account_switch_enabled: bool = False
    allowed_origins: str = "http://localhost:5173"
    agent_mode: Literal["live", "fake", "replay"] = "live"
    openai_api_key: SecretStr = SecretStr("")
    openai_agent_model: str = ""
    agent_run_deadline_seconds: int = Field(default=60, gt=0)
    agent_max_model_calls: int = Field(default=7, gt=0)
    agent_max_tool_calls: int = Field(default=6, gt=0)
    agent_max_output_tokens: int = Field(default=2000, gt=0)
    search_max_chunks: int = Field(default=5, gt=0)
    search_max_chunk_chars: int = Field(default=2000, gt=0)
    worker_poll_interval_seconds: float = Field(default=2, gt=0)
    job_lease_seconds: int = Field(default=90, gt=0)
    job_max_attempts: int = Field(default=3, gt=0)

    @property
    def origins(self) -> list[str]:
        return [v.strip() for v in self.allowed_origins.split(",") if v.strip()]

    @model_validator(mode="after")
    def validate_runtime(self):
        try:
            url = make_url(self.database_url.get_secret_value())
            if url.drivername != "postgresql+psycopg":
                raise ValueError
        except Exception:
            raise ValueError("DATABASE_URL must use postgresql+psycopg") from None
        if len(self.session_secret.get_secret_value().encode()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 bytes")
        if not self.origins or any(
            urlsplit(v).scheme not in ("http", "https") or not urlsplit(v).netloc
            or urlsplit(v).path or urlsplit(v).query or urlsplit(v).fragment
            or urlsplit(v).username or "*" in v for v in self.origins
        ):
            raise ValueError("ALLOWED_ORIGINS must contain exact HTTP(S) origins")
        if self.job_lease_seconds <= self.agent_run_deadline_seconds:
            raise ValueError("JOB_LEASE_SECONDS must exceed the run deadline")
        if self.app_env == "production" and (
            not self.session_cookie_secure or self.demo_account_switch_enabled
            or url.password in (None, "", "replace_for_local_development")
            or any(not v.startswith("https://") for v in self.origins)
        ):
            raise ValueError("Production requires secure cookies/origins, credentials, and demo switching disabled")
        return self

    def validate_live_worker(self):
        if self.agent_mode == "live" and (
            not self.openai_api_key.get_secret_value() or not self.openai_agent_model.strip()
        ):
            raise ValueError("Live worker requires OPENAI_API_KEY and OPENAI_AGENT_MODEL")


def load_settings() -> Settings:
    # Repository layout is absent in the container; Compose injects its environment.
    root = next((p for p in Path(__file__).resolve().parents if (p / "compose.yaml").is_file()), None)
    if root is not None:
        load_dotenv(root / ".env", override=False)
    values = {name: os.environ[name.upper()] for name in Settings.model_fields if name.upper() in os.environ}
    try:
        return Settings(**values)
    except ValueError:
        # Pydantic errors may contain the original input, including credentials.
        raise RuntimeError("Invalid runtime settings. Check .env.example and docs/ENVIRONMENT.md.") from None
