"""Settings load from the environment and match the architecture defaults."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import (
    DEFAULT_BUDGET_LOW_MAX,
    DEFAULT_BUDGET_MEDIUM_MAX,
    DEFAULT_CANDIDATE_LIMIT,
    DEFAULT_CATALOG_PATH,
    DEFAULT_DATASET_ID,
    DEFAULT_DATASET_REVISION,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_SSL_VERIFY,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_RESULT_LIMIT,
    Settings,
)

SETTINGS_ENV = (
    "DATASET_ID",
    "DATASET_REVISION",
    "CATALOG_PATH",
    "BUDGET_LOW_MAX",
    "BUDGET_MEDIUM_MAX",
    "CANDIDATE_LIMIT",
    "RESULT_LIMIT",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_TIMEOUT_SECONDS",
    "LLM_SSL_VERIFY",
    "CORS_ORIGINS",
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_architecture(clean_env: None) -> None:
    settings = Settings(_env_file=None)

    assert settings.dataset_id == DEFAULT_DATASET_ID
    assert settings.dataset_revision == DEFAULT_DATASET_REVISION
    assert settings.catalog_path == DEFAULT_CATALOG_PATH
    assert settings.budget_low_max == DEFAULT_BUDGET_LOW_MAX == 500
    assert settings.budget_medium_max == DEFAULT_BUDGET_MEDIUM_MAX == 1500
    assert settings.candidate_limit == DEFAULT_CANDIDATE_LIMIT == 15
    assert settings.result_limit == DEFAULT_RESULT_LIMIT == 5
    assert settings.llm_base_url == DEFAULT_LLM_BASE_URL
    assert settings.llm_model == DEFAULT_LLM_MODEL
    assert settings.llm_timeout_seconds == DEFAULT_LLM_TIMEOUT_SECONDS
    assert settings.llm_ssl_verify is DEFAULT_LLM_SSL_VERIFY
    assert settings.llm_api_key == ""
    assert settings.cors_origins == ""
    assert settings.cors_origin_list() == []


def test_environment_overrides_defaults(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATASET_ID", "example/dataset")
    monkeypatch.setenv("DATASET_REVISION", "abc123")
    monkeypatch.setenv("CATALOG_PATH", "tmp/catalog.parquet")
    monkeypatch.setenv("BUDGET_LOW_MAX", "400")
    monkeypatch.setenv("BUDGET_MEDIUM_MAX", "900")
    monkeypatch.setenv("CANDIDATE_LIMIT", "8")
    monkeypatch.setenv("RESULT_LIMIT", "3")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key-from-env")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " https://thindi.vercel.app , http://localhost:3000 ",
    )

    settings = Settings(_env_file=None)

    assert settings.dataset_id == "example/dataset"
    assert settings.dataset_revision == "abc123"
    assert settings.catalog_path == "tmp/catalog.parquet"
    assert settings.budget_low_max == 400
    assert settings.budget_medium_max == 900
    assert settings.candidate_limit == 8
    assert settings.result_limit == 3
    assert settings.llm_base_url == "https://example.test/v1"
    assert settings.llm_model == "test-model"
    assert settings.llm_api_key == "test-key-from-env"
    assert settings.llm_timeout_seconds == 12
    assert settings.cors_origin_list() == [
        "https://thindi.vercel.app",
        "http://localhost:3000",
    ]


def test_env_file_loads_and_process_environment_wins(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BUDGET_LOW_MAX=400\nLLM_API_KEY=from-file\n",
        encoding="utf-8",
    )

    from_file = Settings(_env_file=env_file)
    assert from_file.budget_low_max == 400
    assert from_file.llm_api_key == "from-file"

    monkeypatch.setenv("LLM_API_KEY", "from-env")
    from_env = Settings(_env_file=env_file)
    assert from_env.llm_api_key == "from-env"
    assert from_env.budget_low_max == 400


def test_api_key_is_hidden_from_repr(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "super-secret-key")
    settings = Settings(_env_file=None)
    assert settings.llm_api_key == "super-secret-key"
    assert "super-secret-key" not in repr(settings)


def test_api_key_is_not_written_into_source() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    key_lines = [
        line for line in example.splitlines() if line.startswith("LLM_API_KEY=")
    ]
    assert key_lines == ["LLM_API_KEY="]

    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "sk-" not in text
        assert "gsk_" not in text
        assert "super-secret-key" not in text
        assert "Bearer gsk_" not in text


def test_gitignore_covers_secrets_snapshot_and_caches() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in (".env", "data/catalog.parquet", "__pycache__/", ".pytest_cache/", ".cache/"):
        assert entry in text


@pytest.mark.parametrize(
    ("low", "medium"),
    [("1500", "500"), ("501", "500")],
)
def test_inverted_budget_cutoffs_are_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, low: str, medium: str
) -> None:
    monkeypatch.setenv("BUDGET_LOW_MAX", low)
    monkeypatch.setenv("BUDGET_MEDIUM_MAX", medium)
    with pytest.raises(ValidationError, match="BUDGET_LOW_MAX"):
        Settings(_env_file=None)


def test_equal_budget_cutoffs_are_allowed(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUDGET_LOW_MAX", "500")
    monkeypatch.setenv("BUDGET_MEDIUM_MAX", "500")
    settings = Settings(_env_file=None)
    assert settings.budget_low_max == settings.budget_medium_max == 500


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CANDIDATE_LIMIT", "0"),
        ("CANDIDATE_LIMIT", "-1"),
        ("RESULT_LIMIT", "0"),
        ("RESULT_LIMIT", "-3"),
        ("CANDIDATE_LIMIT", ""),
        ("RESULT_LIMIT", ""),
    ],
)
def test_invalid_limits_are_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_non_positive_timeout_is_rejected(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
