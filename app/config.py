"""Environment-backed settings.

Values come from the process environment and, when present, a local `.env`
file. Defaults match the architecture. The API key is empty unless the
environment sets it, and it is never written into source.
"""

from typing import Self

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
DEFAULT_DATASET_REVISION = "5738e9eda2fad49ad51c6e0ed26e761d9b947133"
DEFAULT_CATALOG_PATH = "data/catalog.parquet"
DEFAULT_BUDGET_LOW_MAX = 500
DEFAULT_BUDGET_MEDIUM_MAX = 1500
DEFAULT_CANDIDATE_LIMIT = 15
DEFAULT_RESULT_LIMIT = 5
DEFAULT_ADDITIONAL_PREFERENCES_MAX = 500
DEFAULT_LLM_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_LLM_MODEL = "openai/gpt-oss-20b"
DEFAULT_LLM_TIMEOUT_SECONDS = 30.0
DEFAULT_LLM_SSL_VERIFY = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dataset_id: str = Field(default=DEFAULT_DATASET_ID, min_length=1)
    dataset_revision: str = Field(default=DEFAULT_DATASET_REVISION, min_length=1)
    catalog_path: str = Field(default=DEFAULT_CATALOG_PATH, min_length=1)
    budget_low_max: int = DEFAULT_BUDGET_LOW_MAX
    budget_medium_max: int = DEFAULT_BUDGET_MEDIUM_MAX
    candidate_limit: int = Field(default=DEFAULT_CANDIDATE_LIMIT, gt=0)
    result_limit: int = Field(default=DEFAULT_RESULT_LIMIT, gt=0)
    additional_preferences_max: int = Field(
        default=DEFAULT_ADDITIONAL_PREFERENCES_MAX, gt=0
    )
    llm_base_url: str = Field(default=DEFAULT_LLM_BASE_URL, min_length=1)
    llm_model: str = Field(default=DEFAULT_LLM_MODEL, min_length=1)
    llm_api_key: str = Field(default="", repr=False)
    llm_timeout_seconds: float = Field(default=DEFAULT_LLM_TIMEOUT_SECONDS, gt=0)
    llm_ssl_verify: bool = DEFAULT_LLM_SSL_VERIFY
    # Comma-separated browser origins allowed to call the API (Vercel, local static).
    cors_origins: str = ""

    @field_validator(
        "dataset_id",
        "dataset_revision",
        "catalog_path",
        "llm_base_url",
        "llm_model",
        "llm_api_key",
        "cors_origins",
        mode="before",
    )
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a clean origin list."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @field_validator("candidate_limit", "result_limit")
    @classmethod
    def _limits_are_positive_integers(cls, value: int, info: ValidationInfo) -> int:
        if value < 1:
            name = (info.field_name or "limit").upper()
            raise ValueError(f"{name} must be a positive integer")
        return value

    @model_validator(mode="after")
    def _budget_cutoffs_are_ordered(self) -> Self:
        if self.budget_low_max > self.budget_medium_max:
            raise ValueError(
                "BUDGET_LOW_MAX must be less than or equal to BUDGET_MEDIUM_MAX"
            )
        return self


def get_settings() -> Settings:
    """Load settings from the environment."""
    return Settings()
