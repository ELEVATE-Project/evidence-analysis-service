"""
LLM provider functions.

Supports:
  - Google Gemini  (google.generativeai)  → LLM_PROVIDER=gemini   (default)
  - OpenRouter     (openai SDK)           → LLM_PROVIDER=openrouter

Call generate_content() from any call site — it branches on provider_name internally.
"""
from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from core.config import settings
from core.constants import PROVIDER_GEMINI, PROVIDER_OPENROUTER

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


# ── OpenRouter helpers ─────────────────────────────────────────────────────────

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
    temperature = float((generation_config or {}).get("temperature", 0.1))
    message_content = _parts_to_openai_content(parts)
    response = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        messages=[{"role": "user", "content": message_content}],
    )
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
    generation_config: dict[str, Any] | None = None,
) -> LLMResponse:
    """
    Generate LLM content for the given parts.

    parts: list of str (prompt) or dict {"mime_type": ..., "data": ...} (image/PDF)
    Provider and model are read from settings — no need to pass them per call.
    """
    provider_name = (getattr(settings, "LLM_PROVIDER", "") or PROVIDER_GEMINI).strip().lower()
    if provider_name == PROVIDER_OPENROUTER:
        model_name = (getattr(settings, "OPENROUTER_MODEL", "") or "google/gemini-2.5-flash-lite").strip()
        return _openrouter_generate(parts, api_key, model_name, generation_config)
    model_name = (getattr(settings, "GEMINI_MODEL", "") or "gemini-2.5-flash").strip()
    return _gemini_generate(parts, api_key, model_name, generation_config)
