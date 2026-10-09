from __future__ import annotations

from dataclasses import dataclass, fields
import os


@dataclass(frozen=True)
class Settings:
    database_url: str = "postgresql+psycopg://shiftlink:shiftlink@localhost:5432/shiftlink"
    session_secret: str = ""
    allowed_origins: tuple[str, ...] = ("http://localhost:5173",)
    session_cookie_secure: bool = False
    demo_account_switch_enabled: bool = True
    app_env: str = "development"
    app_timezone: str = "Asia/Seoul"
    agent_mode: str = "live"
    openai_api_key: str = ""
    openai_agent_model: str = ""
    agent_run_deadline_seconds: int = 60
    agent_max_model_calls: int = 7
    agent_max_tool_calls: int = 6
    agent_max_output_tokens: int = 2000
    agent_max_input_bytes: int = 262144
    search_max_chunks: int = 5
    search_max_chunk_chars: int = 2000
    worker_poll_interval_seconds: int = 2
    job_lease_seconds: int = 90
    job_max_attempts: int = 3
    dataset_id: str = "shiftlink-demo"
    demo_now: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        # Explicit process environment only. Never open .env or credential files.
        defaults = cls()
        values = {}
        for field in fields(cls):
            raw = os.environ.get(field.name.upper())
            if raw is None:
                continue
            default = getattr(defaults, field.name)
            if isinstance(default, bool):
                if raw.lower() not in {"true", "false"}:
                    raise ValueError(f"{field.name.upper()} must be true or false")
                values[field.name] = raw.lower() == "true"
            elif isinstance(default, int):
                values[field.name] = int(raw)
            elif field.name == "allowed_origins":
                values[field.name] = tuple(x.strip() for x in raw.split(",") if x.strip())
            else:
                values[field.name] = raw
        return cls(**values)

    def validate(self, *, worker: bool = False) -> None:
        if not self.database_url.startswith("postgresql+"):
            raise ValueError("PostgreSQL is required")
        if len(self.session_secret.encode()) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 bytes")
        if not self.allowed_origins or "*" in self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must contain exact origins")
        if self.app_env not in {"development", "production"}:
            raise ValueError("Invalid APP_ENV")
        if self.agent_mode not in {"live", "fake", "replay"}:
            raise ValueError("Invalid AGENT_MODE")
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, int) and not isinstance(value, bool) and value <= 0:
                raise ValueError(f"{field.name.upper()} must be positive")
        if self.job_lease_seconds <= self.agent_run_deadline_seconds:
            raise ValueError("JOB_LEASE_SECONDS must exceed AGENT_RUN_DEADLINE_SECONDS")
        if not 32768 <= self.agent_max_input_bytes <= 1048576:
            raise ValueError("AGENT_MAX_INPUT_BYTES must be between 32768 and 1048576")
        if self.app_env == "production" and (not self.session_cookie_secure or self.demo_account_switch_enabled):
            raise ValueError("Production requires secure cookies and disabled demo switching")
        if worker and self.agent_mode == "live" and (not self.openai_api_key or not self.openai_agent_model):
            raise ValueError("Live worker requires API key and model configuration")
