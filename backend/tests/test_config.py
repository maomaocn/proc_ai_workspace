import pytest

from app.core.config import Settings


def test_mock_providers_are_the_keyless_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in (
        "MODEL_PROVIDER",
        "EMBEDDING_PROVIDER",
        "OPENAI_COMPATIBLE_API_KEY",
        "REMOTE_EMBEDDING_API_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    settings = Settings(_env_file=None)

    assert settings.model_provider == "mock"
    assert settings.embedding_provider == "mock"
    assert settings.openai_compatible_api_key == ""
    assert settings.remote_embedding_api_key == ""
