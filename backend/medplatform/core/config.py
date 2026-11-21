from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class ConfigurationError(ValueError):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="forbid"
    )

    APP_ENV: Literal["local", "test", "production"] = "local"
    HOST: Literal["127.0.0.1"] = "127.0.0.1"
    PORT: int = Field(default=8000, ge=1, le=65535)
    DATABASE_PATH: Path = Field(default=ROOT / "var" / "app-demo.sqlite3", repr=False)
    AUTH_MODE: Literal["demo", "external"] = "demo"
    LLM_MODE: Literal["mock", "real"] = "mock"
    LLM_BASE_URL: str = Field(default="", repr=False)
    LLM_MODEL: str = ""
    LLM_API_KEY: SecretStr = Field(default_factory=lambda: SecretStr(""), repr=False)
    DEMO_SERVICE_RECEIPT_SUBJECT: str = Field(default="", repr=False)
    DEMO_SERVICE_RECEIPT_TOKEN: SecretStr = Field(
        default_factory=lambda: SecretStr(""), repr=False
    )
    DEMO_FULFILLMENT_RECEIPT_SUBJECT: str = Field(default="", repr=False)
    DEMO_FULFILLMENT_RECEIPT_TOKEN: SecretStr = Field(
        default_factory=lambda: SecretStr(""), repr=False
    )
    LLM_TIMEOUT_SECONDS: int = Field(default=60, ge=1, le=60)
    DIALOGUE_HISTORY_LIMIT: int = Field(default=20, ge=1, le=100)
    RUNNER_POLL_SECONDS: int = Field(default=5, ge=1, le=60)
    RUNNER_MAX_TASKS: int = Field(default=100, ge=1, le=1000)
    CONFIG_VERSION: Literal["s01-config-v1"] = "s01-config-v1"

    @model_validator(mode="after")
    def supported_modes(self):
        if self.APP_ENV == "production" or self.AUTH_MODE != "demo":
            raise ValueError("外部身份适配未接入，不能启动该模式")
        if self.LLM_MODE != "mock":
            raise ValueError("真实模型传输未启用，不能启动该模式")
        return self

    @property
    def database_path(self) -> Path:
        path = self.DATABASE_PATH
        return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.PORT}", f"localhost:{self.PORT}"}

    @property
    def allowed_origins(self) -> set[str]:
        return {"http://" + host for host in self.allowed_hosts}


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError, ValueError:
        # ValidationError can contain raw environment secrets. Never print it.
        raise ConfigurationError(
            "配置不合法或请求的外部能力未接入，请检查配置说明"
        ) from None
