"""
Shared Gemini runtime helpers.
Provides consistent token/model resolution for one-off validation and execution processing.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

from core.config import settings


_ORDERED_GEMINI_ENV_KEYS = [
    "GEMINI_TOKEN",
    "GEMINI_TOKEN_1",
    "GEMINI_TOKEN_2",
    "GEMINI_TOKEN_3",
    "GEMINI_API_KEY",
    "GEMINI_API_KEY_1",
    "GEMINI_API_KEY_2",
    "GEMINI_API_KEY_3",
]


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


def _iter_env_keys(prefixes: Iterable[str], env: dict[str, str]) -> list[str]:
    matches: list[str] = []
    for key in sorted(env.keys()):
        if key == "GEMINI_API_KEYS":
            continue
        if any(key.startswith(prefix) for prefix in prefixes):
            matches.append(key)
    return matches


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


def get_gemini_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """
    Resolve Gemini tokens in deterministic order with fallback semantics.
    Supported sources:
    - GEMINI_TOKEN* / GEMINI_API_KEY* env variables
    - settings.GEMINI_API_KEY_1..3 fallback values
    """
    source_env = env or os.environ
    tokens: list[str] = []
    seen: set[str] = set()

    for key in _ORDERED_GEMINI_ENV_KEYS:
        _add_value(tokens, seen, source_env.get(key))

    # Reference-app compatible comma-separated key list support.
    _add_csv_values(tokens, seen, source_env.get("GEMINI_API_KEYS"))

    for key in _iter_env_keys(("GEMINI_TOKEN", "GEMINI_API_KEY"), source_env):
        _add_value(tokens, seen, source_env.get(key))

    # Settings fallback for environments where values are loaded only via pydantic settings.
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_1", ""))
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_2", ""))
    _add_value(tokens, seen, getattr(settings, "GEMINI_API_KEY_3", ""))

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

    keys_from_env = get_gemini_tokens(source_env)
    for index, token in enumerate(keys_from_env[:3], start=1):
        overrides[f"GEMINI_API_KEY_{index}"] = token

    for key in ("GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3"):
        if key in overrides:
            continue
        value = (source_env.get(key) or "").strip()
        if not value:
            value = (getattr(settings, key, "") or "").strip()
        if value and not _looks_like_placeholder_secret(value):
            overrides[key] = value

    model_name = get_gemini_model_name(source_env)
    if model_name:
        overrides["GEMINI_MODEL"] = model_name

    return overrides


# ── Provider-agnostic helpers ──────────────────────────────────────────────────

def get_llm_provider_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the active LLM provider name: 'google' (default) or 'openrouter'."""
    source_env = env or os.environ
    name = (
        source_env.get("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", "")
        or "google"
    ).strip().lower()
    return name


def get_llm_tokens(env: Optional[dict[str, str]] = None) -> list[str]:
    """
    Return API tokens for the active LLM provider.
    - google:     returns the Gemini key list (rotation-ready).
    - openrouter: returns [OPENROUTER_API_KEY] (single key).
    """
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == "openrouter":
        key = (
            source_env.get("OPENROUTER_API_KEY")
            or getattr(settings, "OPENROUTER_API_KEY", "")
            or ""
        ).strip()
        if key and not _looks_like_placeholder_secret(key):
            return [key]
        return []
    return get_gemini_tokens(source_env)


def get_llm_model_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the model name for the active LLM provider."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == "openrouter":
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

    if provider == "openrouter":
        key = (
            source_env.get("OPENROUTER_API_KEY")
            or getattr(settings, "OPENROUTER_API_KEY", "")
            or ""
        ).strip()
        if key and not _looks_like_placeholder_secret(key):
            overrides["OPENROUTER_API_KEY"] = key
        model = get_llm_model_name(source_env)
        if model:
            overrides["OPENROUTER_MODEL"] = model

    return overrides
