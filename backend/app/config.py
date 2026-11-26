"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[2]
_BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Backend settings loaded from .env or process environment."""

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_DIR / ".env"), str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deye_base_url: str = Field(default="https://india-developer.deyecloud.com")
    deye_app_id: str = Field(default="")
    deye_app_secret: str = Field(default="")
    deye_email: str = Field(default="")
    deye_password: str = Field(default="")
    deye_device_sns: str = Field(default="260605A076,260603A1D5,260505A373")
    deye_company_id: int = Field(default=0)

    database_url: str = Field(default="sqlite:///./deye_solar.db")
    poll_interval_minutes: int = Field(default=5, ge=1, le=60)
    api_timeout_seconds: float = Field(default=20.0, ge=5.0, le=120.0)
    cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")
    log_level: str = Field(default="INFO")

    @property
    def configured_device_sns(self) -> List[str]:
        """Return deduplicated, stripped list of configured inverter serial numbers."""
        seen = set()
        result: List[str] = []
        for raw in self.deye_device_sns.split(","):
            sn = raw.strip()
            if sn and sn not in seen:
                seen.add(sn)
                result.append(sn)
        return result

    @property
    def cors_origin_list(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def has_credentials(self) -> bool:
        """Return True if all required DeyeCloud credentials are configured."""
        return bool(
            self.deye_app_id.strip()
            and self.deye_app_secret.strip()
            and self.deye_email.strip()
            and self.deye_password.strip()
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
