"""
LLM provider functions.

Single canonical home for both providers' token/model resolution AND content
generation:
  - Google Gemini  (google.generativeai)  → LLM_PROVIDER=gemini   (default)
  - OpenRouter     (openai SDK)           → LLM_PROVIDER=openrouter

Call sites should resolve tokens/model via get_llm_tokens()/get_llm_model_name()
and generate via generate_content() — both providers flow through the same
shared helpers and the same dispatcher, so there is one place to look.
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
from typing import Any, Iterable, Optional

from core.config import settings
from core.constants import (
    GEMINI_API_KEY_PREFIX,
    OPENROUTER_API_KEY_PREFIX,
    PROVIDER_GEMINI,
    PROVIDER_OPENROUTER,
)

logger = logging.getLogger(__name__)


# ── Response types ─────────────────────────────────────────────────────────────

class LLMUsage:
    __slots__ = ("prompt_token_count", "candidates_token_count", "total_token_count")

    def __init__(
        self,
        prompt_token_count: int = 0,
        candidates_token_count: int = 0,
        total_token_count: int = 0,
    ) -> None:
        self.prompt_token_count = prompt_token_count
        self.candidates_token_count = candidates_token_count
        self.total_token_count = total_token_count


class LLMResponse:
    __slots__ = ("text", "usage_metadata")

    def __init__(self, text: str, usage_metadata: LLMUsage) -> None:
        self.text = text
        self.usage_metadata = usage_metadata


# ── Shared token/model resolution helpers (used by both providers) ────────────

_PLACEHOLDER_MARKERS = (
    "your_", "your-api-key", "replace_me", "placeholder", "example", "sample", "<", "changeme", "dummy",
)


def _looks_like_placeholder(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def _numeric_suffix_sort_key(key: str) -> tuple[str, int]:
    """Sort <PREFIX>_<N> by numeric N so _2 precedes _10 (not lexicographic _10 < _2)."""
    prefix, _, suffix = key.rpartition("_")
    return (prefix, int(suffix)) if suffix.isdigit() else (key, -1)


def _add_token(tokens: list[str], seen: set[str], raw_value: Optional[str]) -> None:
    value = (raw_value or "").strip()
    if not value or _looks_like_placeholder(value) or value in seen:
        return
    tokens.append(value)
    seen.add(value)


def _add_csv_values(tokens: list[str], seen: set[str], raw_values: Optional[str]) -> None:
    for part in str(raw_values or "").split(","):
        _add_token(tokens, seen, part)


def _resolve_model_name(env: dict[str, str], env_key: str, settings_attr: str, default: str) -> str:
    model_name = (env.get(env_key) or "").strip()
    if model_name:
        return model_name
    setting_model = (getattr(settings, settings_attr, "") or "").strip()
    return setting_model or default


# ── Gemini token/model resolution ──────────────────────────────────────────────

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


def _iter_gemini_env_keys(prefixes: Iterable[str], env: dict[str, str]) -> list[str]:
    matches: list[str] = []
    for key in sorted(env.keys()):
        if key == "GEMINI_API_KEYS":
            continue
        if any(key.startswith(prefix) for prefix in prefixes):
            matches.append(key)
    return matches


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
        _add_token(tokens, seen, source_env.get(key))

    # Reference-app compatible comma-separated key list support.
    _add_csv_values(tokens, seen, source_env.get("GEMINI_API_KEYS"))

    for key in _iter_gemini_env_keys(("GEMINI_TOKEN", "GEMINI_API_KEY"), source_env):
        _add_token(tokens, seen, source_env.get(key))

    # Settings fallback for environments where values are loaded only via pydantic settings.
    _add_token(tokens, seen, getattr(settings, "GEMINI_API_KEY_1", ""))
    _add_token(tokens, seen, getattr(settings, "GEMINI_API_KEY_2", ""))
    _add_token(tokens, seen, getattr(settings, "GEMINI_API_KEY_3", ""))

    return tokens


def get_gemini_model_name(env: Optional[dict[str, str]] = None) -> str:
    source_env = env or os.environ
    return _resolve_model_name(source_env, "GEMINI_MODEL", "GEMINI_MODEL", "gemini-2.5-flash")


def _build_provider_env_overrides(
    source_env: dict[str, str],
    get_tokens_fn,
    key_prefix: str,
    get_model_name_fn,
    model_env_key: str,
    token_cap: Optional[int] = None,
) -> dict[str, str]:
    overrides: dict[str, str] = {}
    tokens = get_tokens_fn(source_env)
    capped = tokens[:token_cap] if token_cap is not None else tokens
    for index, token in enumerate(capped, start=1):
        overrides[f"{key_prefix}_{index}"] = token
    model_name = get_model_name_fn(source_env)
    if model_name:
        overrides[model_env_key] = model_name
    return overrides


def build_gemini_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Caps at 3 to match the processor script's fixed GEMINI_API_KEY_1/2/3 key names."""
    return _build_provider_env_overrides(
        env or os.environ,
        get_gemini_tokens, GEMINI_API_KEY_PREFIX,
        get_gemini_model_name, "GEMINI_MODEL",
        token_cap=3,
    )


# ── OpenRouter token/model resolution ──────────────────────────────────────────

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
    return _resolve_model_name(
        source_env, "OPENROUTER_MODEL", "OPENROUTER_MODEL", "google/gemini-2.5-flash-lite"
    )


def build_openrouter_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    return _build_provider_env_overrides(
        env or os.environ,
        get_openrouter_tokens, OPENROUTER_API_KEY_PREFIX,
        get_openrouter_model_name, "OPENROUTER_MODEL",
    )


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
    """Return API tokens for the active provider."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == PROVIDER_OPENROUTER:
        return get_openrouter_tokens(source_env)
    elif provider == PROVIDER_GEMINI:
        return get_gemini_tokens(source_env)
    raise ValueError(f"Unsupported LLM provider: {provider!r}")


def get_llm_model_name(env: Optional[dict[str, str]] = None) -> str:
    """Return the model name for the active provider."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == PROVIDER_OPENROUTER:
        return get_openrouter_model_name(source_env)
    elif provider == PROVIDER_GEMINI:
        return get_gemini_model_name(source_env)
    raise ValueError(f"Unsupported LLM provider: {provider!r}")


def build_llm_env_overrides(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Build subprocess env overrides for the active provider."""
    source_env = env or os.environ
    provider = get_llm_provider_name(source_env)
    if provider == PROVIDER_OPENROUTER:
        overrides = build_openrouter_env_overrides(source_env)
    elif provider == PROVIDER_GEMINI:
        overrides = build_gemini_env_overrides(source_env)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider!r}")
    overrides["LLM_PROVIDER"] = provider
    return overrides


# ── OpenRouter content-translation helpers ────────────────────────────────────

def _pdf_bytes_to_image_parts(pdf_bytes: bytes) -> list[dict]:
    """Convert PDF bytes to image_url parts using PyMuPDF (up to 3 pages)."""
    try:
        import fitz  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "[LLM] PyMuPDF is not installed; PDF cannot be sent via OpenRouter. "
            "Install it with: pip install pymupdf"
        )
        return [{"type": "text", "text": "[PDF content unavailable: PyMuPDF not installed]"}]
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        parts: list[dict] = []
        for i in range(min(len(doc), 3)):
            pix = doc[i].get_pixmap(dpi=150)
            b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        return parts
    except Exception as exc:
        logger.warning("[LLM] PDF-to-image conversion failed: %s", exc)
        return [{"type": "text", "text": "[PDF content could not be processed]"}]


def _parts_to_openai_content(parts: list) -> list | str:
    """Translate Gemini-style content parts to the OpenAI message content format."""
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]

    content: list[dict] = []
    for part_index, part in enumerate(parts):
        if isinstance(part, str):
            content.append({"type": "text", "text": part})
        elif isinstance(part, dict):
            if "url" in part:
                content.append({"type": "image_url", "image_url": {"url": part["url"]}})
                continue
            mime: str = part.get("mime_type", "")
            raw: bytes | str = part.get("data", b"")
            if isinstance(raw, str):
                try:
                    raw_bytes = base64.b64decode(raw, validate=True)
                except (binascii.Error, ValueError):
                    logger.warning(
                        "[LLM] OpenRouter: part[%d] has malformed base64 data (mime '%s') — skipping part",
                        part_index, mime,
                    )
                    continue
                b64_data = raw
            else:
                b64_data = base64.b64encode(raw).decode("utf-8")
                raw_bytes = raw
            if mime.startswith("image/"):
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_data}"}})
            elif mime == "application/pdf":
                content.extend(_pdf_bytes_to_image_parts(raw_bytes))
            else:
                logger.warning("[LLM] OpenRouter: unsupported mime type '%s' — skipping part", mime)
    return content


# ── Provider implementations ───────────────────────────────────────────────────

def _gemini_generate(
    parts: list,
    api_key: str,
    model_name: str,
    generation_config: dict[str, Any] | None,
) -> LLMResponse:
    import google.generativeai as genai  # noqa: PLC0415
    genai.configure(api_key=api_key)
    gemini_model = (
        genai.GenerativeModel(model_name=model_name, generation_config=generation_config)
        if generation_config
        else genai.GenerativeModel(model_name=model_name)
    )
    raw = gemini_model.generate_content(parts)
    text = getattr(raw, "text", "") or ""
    meta = getattr(raw, "usage_metadata", None)
    return LLMResponse(
        text=text,
        usage_metadata=LLMUsage(
            prompt_token_count=getattr(meta, "prompt_token_count", 0) or 0,
            candidates_token_count=getattr(meta, "candidates_token_count", 0) or 0,
            total_token_count=getattr(meta, "total_token_count", 0) or 0,
        ),
    )


def _openrouter_generate(
    parts: list,
    api_key: str,
    model_name: str,
    generation_config: dict[str, Any] | None,
) -> LLMResponse:
    try:
        import openai  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "The 'openai' package is required for OpenRouter. "
            "Install it with: pip install 'openai>=1.0.0'"
        ) from exc
    client = openai.OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=api_key)
    config = generation_config or {}
    temperature = float(config.get("temperature", 0.1))
    message_content = _parts_to_openai_content(parts)
    create_kwargs: dict[str, Any] = {
        "model": model_name,
        "temperature": temperature,
        "messages": [{"role": "user", "content": message_content}],
    }
    if config.get("response_format") == "json_object":
        create_kwargs["response_format"] = {"type": "json_object"}
    logger.debug(
        "openrouter_request  model=%s  json_format_enforced=%s  temperature=%.2f",
        model_name, "response_format" in create_kwargs, temperature,
    )
    response = client.chat.completions.create(**create_kwargs)
    text = (response.choices[0].message.content or "") if response.choices else ""
    usage = getattr(response, "usage", None)
    return LLMResponse(
        text=text,
        usage_metadata=LLMUsage(
            prompt_token_count=getattr(usage, "prompt_tokens", 0) or 0,
            candidates_token_count=getattr(usage, "completion_tokens", 0) or 0,
            total_token_count=getattr(usage, "total_tokens", 0) or 0,
        ),
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_content(
    parts: list,
    *,
    api_key: str,
    model_name: str | None = None,
    generation_config: dict[str, Any] | None = None,
) -> LLMResponse:
    """
    Generate LLM content for the given parts.

    parts: list of str (prompt) or dict {"mime_type": ..., "data": ...} (image/PDF)
    Provider is read from settings. Pass model_name to use an already-resolved
    model (e.g. from get_llm_model_name()); otherwise it is resolved from settings.
    """
    provider_name = (getattr(settings, "LLM_PROVIDER", "") or PROVIDER_GEMINI).strip().lower()
    if provider_name == PROVIDER_OPENROUTER:
        resolved_model_name = model_name or (
            getattr(settings, "OPENROUTER_MODEL", "") or "google/gemini-2.5-flash-lite"
        ).strip()
        return _openrouter_generate(parts, api_key, resolved_model_name, generation_config)
    elif provider_name == PROVIDER_GEMINI:
        resolved_model_name = model_name or (getattr(settings, "GEMINI_MODEL", "") or "gemini-2.5-flash").strip()
        return _gemini_generate(parts, api_key, resolved_model_name, generation_config)
    raise ValueError(f"Unsupported LLM provider: {provider_name!r}")
