import json
from pathlib import Path

from src.config import AppConfig, FREE_MODELS, load_config, save_config


def test_default_config_created(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg = load_config(cfg_path, env_path=None)

    assert cfg_path.exists()
    assert cfg.openrouter_api_key == ""
    assert cfg.model == FREE_MODELS[0]["id"]
    assert cfg.batch_size == 50


def test_save_and_load_roundtrip(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    original = AppConfig(
        openrouter_api_key="test-key-123",
        model="qwen/qwen3.6-plus:free",
        batch_size=100,
        max_tokens_per_batch=5000,
        language="en",
    )
    save_config(original, cfg_path)
    loaded = load_config(cfg_path, env_path=None)

    assert loaded.openrouter_api_key == "test-key-123"
    assert loaded.model == "qwen/qwen3.6-plus:free"
    assert loaded.batch_size == 100
    assert loaded.max_tokens_per_batch == 5000
    assert loaded.language == "en"


def test_invalid_json_raises(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("not valid json {{{", encoding="utf-8")

    try:
        load_config(cfg_path, env_path=None)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "CONFIG_INVALID" in str(exc)


def test_env_overrides_config(tmp_path: Path):
    cfg_path = tmp_path / "config.json"
    env_path = tmp_path / ".env"

    save_config(AppConfig(openrouter_api_key="from-config"), cfg_path)
    env_path.write_text("OPENROUTER_API_KEY=from-env\n", encoding="utf-8")

    loaded = load_config(cfg_path, env_path=env_path)
    assert loaded.openrouter_api_key == "from-env"


def test_free_models_not_empty():
    assert len(FREE_MODELS) >= 2
    for m in FREE_MODELS:
        assert "id" in m
        assert "name" in m
