from app.config import Settings


def test_default_llm_model_uses_active_anthropic_model():
    settings = Settings(_env_file=None)

    assert settings.llm_model == "claude-sonnet-4-6"

