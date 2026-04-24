"""Configuration models for azdeeploy."""

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    deepseek_api_key: str | None = Field(default=None, alias="AZDEEPPLOY_DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="AZDEEPPLOY_DEEPSEEK_BASE_URL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_api_key(self) -> "Settings":
        """Ensure an API key is present before using the app."""
        if not self.deepseek_api_key or not self.deepseek_api_key.strip():
            raise ValueError(
                "AZDEEPPLOY_DEEPSEEK_API_KEY is not set. Run `azdeeploy init` "
                "or add it to your environment or .env file."
            )
        return self


def load_config() -> Settings:
    """Load and validate application settings."""
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Missing DeepSeek configuration. Set AZDEEPPLOY_DEEPSEEK_API_KEY "
            "in your environment or .env file, or run `azdeeploy init`."
        ) from exc
