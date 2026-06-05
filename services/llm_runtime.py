"""
Shared Gemini runtime helpers.
Provides consistent token/model resolution for one-off validation and execution processing.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)
from core.constants import OPENROUTER_API_KEY_PREFIX, PROVIDER_GEMINI, PROVIDER_OPENROUTER


API_KEYS_TO_SKIP = {"GEMINI_API_KEYS", "OPENROUTER_API_KEYS"}


def _looks_like_placeholder_secret(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True

    placeholder_markers = (
        "your_",
        "replace_me",
        "placeholder",
        "example",
        "sample",
        "<",
        "changeme",
    )
    if any(marker in normalized for marker in placeholder_markers):
        return True

    return False



def _add_value(unique_values: list[str], seen: set[str], raw_value: Optional[str]) -> None:
    value = (raw_value or "").strip()
    if not value:
        return
    if _looks_like_placeholder_secret(value):
        return
    if value in seen:
        return
    unique_values.append(value)
    seen.add(value)


def _add_csv_values(unique_values: list[str], seen: set[str], raw_values: Optional[str]) -> None:
    for part in str(raw_values or "").split(","):
        _add_value(unique_values, seen, part)


def _collect_tokens_for_prefix(
    prefixes: tuple[str, ...],
    csv_env_key: str,
    env: dict[str, str],
) -> list[str]:
    """
    Collect API tokens for the given key prefixes in priority order:
    1. Pydantic settings — scans ALL matching fields dynamically (no hardcoded _1/_2/_3)
    2. CSV batch key from settings  (e.g. GEMINI_API_KEYS=key1,key2,key3)
    3. Raw env vars matching the prefix (covers Docker/shell without a .env file)
    4. CSV batch key from env

    'prefixes' controls which env var names are picked up.
    Example: ("GEMINI_API_KEY", "GEMINI_TOKEN") picks up GEMINI_API_KEY_1,
    GEMINI_API_KEY_2, GEMINI_TOKEN_1 ... and any future GEMINI_API_KEY_N.
    """
    tokens: list[str] = []
    seen: set[str] = set()

    # settings.model_dump() returns a dict of all fields defined in core/config.py.
    # We scan it dynamically so adding GEMINI_API_KEY_4 to config.py is all that's
    # needed to support a 4th key — no change needed here.
    settings_dict: dict = settings.model_dump()
    for key in sorted(settings_dict.keys()):
        if key in API_KEYS_TO_SKIP:
            continue
        if any(key.startswith(p) for p in prefixes):
            _add_value(tokens, seen, str(settings_dict[key] or ""))
    _add_csv_values(tokens, seen, str(settings_dict.get(csv_env_key) or ""))

    # Same scan against raw os.environ — catches keys set in Docker/shell
    # that aren't in the .env file.
    for key in sorted(env.keys()):
        if key in API_KEYS_TO_SKIP:
            continue
        if any(key.startswith(p) for p in prefixes):
            _add_value(tokens, seen, env.get(key))
    _add_csv_values(tokens, seen, env.get(csv_env_key))

    return tokens


def get_gemini_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """Return Gemini API tokens in priority order (settings first, then env fallback)."""
    source_env = env or os.environ
    tokens: list[str] = []
    seen: set[str] = set()

    # Pydantic settings first — loaded from .env, source of truth for managed keys.
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_1", ""))
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_2", ""))
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_3", ""))

    # Env fallback — covers Docker/shell and any extra numbered slots beyond 3.
    for key in sorted(source_env.keys()):
        if key in API_KEYS_TO_SKIP:
            continue
        if key.startswith("GEMINI_API_KEY") or key.startswith("GEMINI_TOKEN"):
            _add_value(tokens, seen, source_env.get(key))

    _add_csv_values(tokens, seen, source_env.get("GEMINI_API_KEYS"))

    return tokens


def get_openrouter_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """Return all OpenRouter API tokens, scanning OPENROUTER_API_KEY_* dynamically."""
    tokens = _collect_tokens_for_prefix(
        prefixes=(OPENROUTER_API_KEY_PREFIX,),
        csv_env_key="OPENROUTER_API_KEYS",
        env=env or os.environ,
    )
    logger.info("[LLM] OpenRouter: loaded %d key(s)", len(tokens))
    return tokens


def get_gemini_model_name(env: Optional[dict[str, str]] = None) -> str:
    source_env = env or os.environ
    model_name = (source_env.get("GEMINI_MODEL") or "").strip()
    if model_name:
        return model_name

    setting_model = (getattr(settings, "GEMINI_MODEL", "") or "").strip()
    if setting_model:
        return setting_model

    return "gemini-2.5-flash"


def build_gemini_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """
    Build env overrides for subprocesses so execution processing receives
    the same Gemini keys/model from settings when parent env is incomplete.
    """
    source_env = env or os.environ
    overrides: dict[str, str] = {}

    for index, token in enumerate(get_gemini_tokens(source_env)[:3], start=1):
        overrides[f"GEMINI_API_KEY_{index}"] = token

    model_name = get_gemini_model_name(source_env)
    if model_name:
        overrides["GEMINI_MODEL"] = model_name

    return overrides


# ── Provider-agnostic helpers ──────────────────────────────────────────────────

def get_llm_provider_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the active LLM provider name: 'gemini' (default) or 'openrouter'."""
    source_env = env or os.environ
    name = (
        source_env.get("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", "")
        or PROVIDER_GEMINI
    ).strip().lower()
    return name


def get_llm_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """Return API tokens for the active LLM provider (rotation-ready list)."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == PROVIDER_OPENROUTER:
        return get_openrouter_tokens(source_env)
    return get_gemini_tokens(source_env)


def get_llm_model_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the model name for the active LLM provider."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == PROVIDER_OPENROUTER:
        model = (
            source_env.get("OPENROUTER_MODEL")
            or getattr(settings, "OPENROUTER_MODEL", "")
            or ""
        ).strip()
        return model or "google/gemini-2.5-flash-lite"
    return get_gemini_model_name(source_env)


def build_llm_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """
    Build subprocess env overrides for the active LLM provider.
    Extends build_gemini_env_overrides with OpenRouter variables when applicable,
    and always propagates LLM_PROVIDER so the subprocess uses the same provider.
    """
    source_env = env or os.environ
    overrides = build_gemini_env_overrides(source_env)

    provider = get_llm_provider_name(source_env)
    overrides["LLM_PROVIDER"] = provider

    if provider == PROVIDER_OPENROUTER:
        tokens = get_openrouter_tokens(source_env)
        for index, token in enumerate(tokens[:3], start=1):
            overrides[f"OPENROUTER_API_KEY_{index}"] = token
        model = get_llm_model_name(source_env)
        if model:
            overrides["OPENROUTER_MODEL"] = model

    return overrides
