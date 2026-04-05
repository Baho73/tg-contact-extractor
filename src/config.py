# FILE: src/config.py
# VERSION: 1.0.0
# START_MODULE_CONTRACT
#   PURPOSE: Load, validate, and persist application configuration (API key, model, batch parameters)
#   SCOPE: Config file I/O, defaults, model list
#   DEPENDS: none
#   LINKS: M-CONFIG
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AppConfig — configuration dataclass
#   FREE_MODELS — predefined list of free OpenRouter models
#   load_config — load config from disk, create default if missing
#   save_config — persist updated config to disk
# END_MODULE_MAP

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# START_BLOCK_FREE_MODELS
FREE_MODELS: list[dict[str, str]] = [
    {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash"},
    {"id": "stepfun/step-3.5-flash:free", "name": "StepFun 3.5 Flash"},
    {"id": "openai/gpt-oss-120b:free", "name": "OpenAI GPT-OSS 120B"},
    {"id": "nvidia/nemotron-3-super-120b-a12b:free", "name": "NVIDIA Nemotron 3 Super 120B"},
    {"id": "qwen/qwen3.6-plus:free", "name": "Qwen 3.6 Plus"},
    {"id": "minimax/minimax-m2.5:free", "name": "MiniMax M2.5"},
]
# END_BLOCK_FREE_MODELS

DEFAULT_MODEL = FREE_MODELS[0]["id"]


# START_BLOCK_APP_CONFIG
@dataclass
class AppConfig:
    openrouter_api_key: str = ""
    model: str = DEFAULT_MODEL
    batch_size: int = 50
    max_tokens_per_batch: int = 3000
    language: str = "ru"
    max_retries: int = 3
    base_timeout: float = 30.0
# END_BLOCK_APP_CONFIG


# START_CONTRACT: _app_dir
#   PURPOSE: Resolve exe vs dev root directory
#   INPUTS: none
#   OUTPUTS: Path
# END_CONTRACT: _app_dir
def _app_dir() -> Path:
    """Directory where the exe (or the project root in dev mode) lives."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle — exe directory
        return Path(sys.executable).resolve().parent
    # Dev mode — project root (parent of src/)
    return Path(__file__).resolve().parent.parent


# START_CONTRACT: _default_config_path
#   PURPOSE: Get default config.json path
#   INPUTS: none
#   OUTPUTS: Path
# END_CONTRACT: _default_config_path
def _default_config_path() -> Path:
    return _app_dir() / "config.json"


# START_CONTRACT: _default_env_path
#   PURPOSE: Get default .env path
#   INPUTS: none
#   OUTPUTS: Path
# END_CONTRACT: _default_env_path
def _default_env_path() -> Path:
    return _app_dir() / ".env"


# START_CONTRACT: _load_dotenv
#   PURPOSE: Parse .env file into dict without external deps
#   INPUTS: { env_path: Path | None }
#   OUTPUTS: dict[str, str]
# END_CONTRACT: _load_dotenv
def _load_dotenv(env_path: Path | None = None) -> dict[str, str]:
    """Parse .env file into a dict. No external dependencies."""
    path = env_path or _default_env_path()
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip("'\"")
    return result


# START_CONTRACT: load_config
#   PURPOSE: Load config from disk; create default file if missing
#   INPUTS: { config_path: Path | None — path to config.json }
#   OUTPUTS: { AppConfig — validated configuration }
#   SIDE_EFFECTS: Creates config.json with defaults if not found
#   LINKS: M-CONFIG
# END_CONTRACT: load_config
def load_config(config_path: Path | None = None, env_path: Path | None = ...) -> AppConfig:
    """Load config. env_path=... uses default .env; env_path=None disables .env loading."""
    path = config_path or _default_config_path()

    # START_BLOCK_LOAD_OR_CREATE
    if not path.exists():
        logger.info("[Config][load_config][LOAD_OR_CREATE] Config not found, creating default at %s", path)
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    # END_BLOCK_LOAD_OR_CREATE

    # START_BLOCK_PARSE_CONFIG
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("[Config][load_config][PARSE_CONFIG] Failed to read config: %s", exc)
        raise ValueError(f"CONFIG_INVALID: {exc}") from exc

    cfg = AppConfig(
        openrouter_api_key=raw.get("openrouter_api_key", ""),
        model=raw.get("model", DEFAULT_MODEL),
        batch_size=raw.get("batch_size", 50),
        max_tokens_per_batch=raw.get("max_tokens_per_batch", 3000),
        language=raw.get("language", "ru"),
    )
    # END_BLOCK_PARSE_CONFIG

    # START_BLOCK_ENV_OVERRIDE
    # .env and OS environment override config.json for API key
    resolved_env = _default_env_path() if env_path is ... else env_path
    env_vars = _load_dotenv(resolved_env) if resolved_env else {}
    env_key = env_vars.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        cfg.openrouter_api_key = env_key
        logger.info("[Config][load_config][ENV_OVERRIDE] API key loaded from .env / environment")
    # END_BLOCK_ENV_OVERRIDE

    logger.info("[Config][load_config] Loaded config, model=%s", cfg.model)
    return cfg


# START_CONTRACT: save_config
#   PURPOSE: Persist configuration to disk
#   INPUTS: { config: AppConfig, config_path: Path | None }
#   OUTPUTS: None
#   SIDE_EFFECTS: Writes config.json to disk
#   LINKS: M-CONFIG
# END_CONTRACT: save_config
def save_config(config: AppConfig, config_path: Path | None = None) -> None:
    path = config_path or _default_config_path()
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("[Config][save_config] Saved config to %s", path)


# START_CHANGE_SUMMARY
#   LAST_CHANGE: [v1.1.0 — Added .env support: API key loaded from .env > env var > config.json]
# END_CHANGE_SUMMARY
