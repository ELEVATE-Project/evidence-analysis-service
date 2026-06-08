"""
Provider-agnostic LLM runtime dispatch.

Routes token/model/env-override resolution to the existing Gemini runtime
(services.gemini_runtime, left untouched) or to the OpenRouter equivalents
defined here, based on the LLM_PROVIDER setting. The Gemini code path always
flows through the original gemini_runtime functions — this module only adds
OpenRouter support and a thin selector on top.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from core.config import settings
from core.constants import OPENROUTER_API_KEY_PREFIX, PROVIDER_GEMINI, PROVIDER_OPENROUTER
from services.gemini_runtime import (
    build_gemini_env_overrides,
    get_gemini_model_name,
    get_gemini_tokens,
)

logger = logging.getLogger(__name__)

_OPENROUTER_PLACEHOLDER_MARKERS = (
    "your_", "replace_me", "placeholder", "example", "sample", "<", "changeme",
)


def _looks_like_placeholder(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in _OPENROUTER_PLACEHOLDER_MARKERS)


def _numeric_suffix_sort_key(key: str) -> tuple[str, int]:
    """Sort OPENROUTER_API_KEY_<N> by numeric N so _2 precedes _10 (not lexicographic _10 < _2)."""
    prefix, _, suffix = key.rpartition("_")
    return (prefix, int(suffix)) if suffix.isdigit() else (key, -1)


def _add_token(tokens: list[str], seen: set[str], raw_value: Optional[str]) -> None:
    value = (raw_value or "").strip()
    if not value or _looks_like_placeholder(value) or value in seen:
        return
    tokens.append(value)
    seen.add(value)


def get_openrouter_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """
    Resolve OpenRouter tokens for rotation: OPENROUTER_API_KEY_1, _2, _3, ... _N.

    Scans pydantic settings AND raw env dynamically for any OPENROUTER_API_KEY_*
    field — no hardcoded cap, so adding OPENROUTER_API_KEY_4 to .env is enough.
    """
    source_env = env or os.environ
    tokens: list[str] = []
    seen: set[str] = set()

    settings_dict: dict = settings.model_dump()
    matched_setting_keys = sorted(
        (k for k in settings_dict.keys() if k.startswith(OPENROUTER_API_KEY_PREFIX + "_")),
        key=_numeric_suffix_sort_key,
    )
    for key in matched_setting_keys:
        _add_token(tokens, seen, str(settings_dict[key] or ""))

    matched_env_keys = sorted(
        (k for k in source_env.keys() if k.startswith(OPENROUTER_API_KEY_PREFIX + "_")),
        key=_numeric_suffix_sort_key,
    )
    for key in matched_env_keys:
        _add_token(tokens, seen, source_env.get(key))

    if tokens:
        logger.info("[LLM] OpenRouter: loaded %d key(s)", len(tokens))
    return tokens


def get_openrouter_model_name(env: Optional[dict[str, str]] = None) -> str:
    source_env = env or os.environ
    model_name = (source_env.get("OPENROUTER_MODEL") or "").strip()
    if model_name:
        return model_name
    setting_model = (getattr(settings, "OPENROUTER_MODEL", "") or "").strip()
    return setting_model or "google/gemini-2.5-flash-lite"


def build_openrouter_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    source_env = env or os.environ
    overrides: dict[str, str] = {}
    for index, token in enumerate(get_openrouter_tokens(source_env), start=1):
        overrides[f"OPENROUTER_API_KEY_{index}"] = token
    model_name = get_openrouter_model_name(source_env)
    if model_name:
        overrides["OPENROUTER_MODEL"] = model_name
    return overrides


# ── Provider dispatch ──────────────────────────────────────────────────────────

def get_llm_provider_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the active LLM provider: 'gemini' (default) or 'openrouter'."""
    source_env = env or os.environ
    return (
        source_env.get("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", "")
        or PROVIDER_GEMINI
    ).strip().lower()


def get_llm_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """Return API tokens for the active provider. Gemini path is get_gemini_tokens(), untouched."""
    source_env = env or os.environ
    if get_llm_provider_name(source_env) == PROVIDER_OPENROUTER:
        return get_openrouter_tokens(source_env)
    return get_gemini_tokens(source_env)


def get_llm_model_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the model name for the active provider. Gemini path is get_gemini_model_name(), untouched."""
    source_env = env or os.environ
    if get_llm_provider_name(source_env) == PROVIDER_OPENROUTER:
        return get_openrouter_model_name(source_env)
    return get_gemini_model_name(source_env)


def build_llm_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """
    Build subprocess env overrides for the active provider.
    Always starts from build_gemini_env_overrides (untouched) so Gemini subprocess
    behavior is unchanged; layers OpenRouter overrides + LLM_PROVIDER on top when active.
    """
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)

    overrides = build_gemini_env_overrides(source_env)
    if provider == PROVIDER_OPENROUTER:
        overrides.update(build_openrouter_env_overrides(source_env))
    overrides["LLM_PROVIDER"] = provider
    return overrides
