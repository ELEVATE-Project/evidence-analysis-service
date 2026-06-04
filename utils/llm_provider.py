"""
Provider-agnostic LLM abstraction layer.

Supports:
  - Google Gemini  (google.generativeai)   → LLM_PROVIDER=google   (default)
  - OpenRouter     (openai SDK)            → LLM_PROVIDER=openrouter

Business logic must only import from this module; no direct vendor SDK usage
is permitted outside here.
"""
from __future__ import annotations

import base64
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_SUPPORTED_PROVIDERS = frozenset({"google", "openrouter"})


# ── Normalised response types ──────────────────────────────────────────────────

class LLMUsage:
    """Normalised token-usage object, compatible with Gemini's usage_metadata API."""

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
    """
    Normalised response object.
    Exposes .text and .usage_metadata to match existing Gemini response access
    patterns so call sites need no changes.
    """

    __slots__ = ("text", "usage_metadata")

    def __init__(self, text: str, usage_metadata: LLMUsage) -> None:
        self.text = text
        self.usage_metadata = usage_metadata


# ── Abstract interfaces ────────────────────────────────────────────────────────

class LLMModel(ABC):
    """Single-model handle returned by a provider."""

    @abstractmethod
    def generate_content(self, parts: list) -> LLMResponse:
        """
        Generate content from a list of parts.
        Each part is either:
          - a plain str (prompt text)
          - a dict {"mime_type": str, "data": bytes | str}  (image / PDF)
        """


class BaseLLMProvider(ABC):
    """Factory + configuration interface for a single LLM vendor."""

    @abstractmethod
    def configure(self, api_key: str) -> None:
        """Authenticate with the given API key."""

    @abstractmethod
    def create_model(
        self,
        model_name: str,
        generation_config: dict[str, Any] | None = None,
    ) -> LLMModel:
        """Create a model handle for the given model name."""


# ── Google Gemini provider ─────────────────────────────────────────────────────

class _GeminiModel(LLMModel):
    def __init__(self, genai_model: Any) -> None:
        self._model = genai_model

    def generate_content(self, parts: list) -> LLMResponse:
        raw = self._model.generate_content(parts)
        text = getattr(raw, "text", "") or ""
        meta = getattr(raw, "usage_metadata", None)
        usage = LLMUsage(
            prompt_token_count=getattr(meta, "prompt_token_count", 0) or 0,
            candidates_token_count=getattr(meta, "candidates_token_count", 0) or 0,
            total_token_count=getattr(meta, "total_token_count", 0) or 0,
        )
        return LLMResponse(text=text, usage_metadata=usage)


class GeminiProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._genai: Any = None

    def configure(self, api_key: str) -> None:
        import google.generativeai as genai  # noqa: PLC0415
        self._genai = genai
        genai.configure(api_key=api_key)

    def create_model(
        self,
        model_name: str,
        generation_config: dict[str, Any] | None = None,
    ) -> LLMModel:
        if self._genai is None:
            import google.generativeai as genai  # noqa: PLC0415
            self._genai = genai
        if generation_config:
            gemini_model = self._genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
            )
        else:
            gemini_model = self._genai.GenerativeModel(model_name=model_name)
        return _GeminiModel(gemini_model)


# ── OpenRouter provider (via openai SDK) ───────────────────────────────────────

def _pdf_bytes_to_image_parts(pdf_bytes: bytes) -> list[dict]:
    """Convert PDF bytes to image_url message parts using PyMuPDF (up to 3 pages)."""
    try:
        import fitz  # PyMuPDF  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "[LLM] PyMuPDF is not installed; PDF cannot be sent via OpenRouter. "
            "Install it with: pip install pymupdf"
        )
        return [{"type": "text", "text": "[PDF content unavailable: PyMuPDF not installed]"}]
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = min(len(doc), 3)
        parts: list[dict] = []
        for i in range(pages):
            pix = doc[i].get_pixmap(dpi=150)
            b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            parts.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            )
        return parts
    except Exception as exc:
        logger.warning("[LLM] PDF-to-image conversion failed: %s", exc)
        return [{"type": "text", "text": "[PDF content could not be processed]"}]


def _parts_to_openai_content(parts: list) -> list | str:
    """
    Translate Gemini-style content parts to the OpenAI chat completions
    message content format.
    """
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]

    content: list[dict] = []
    for part in parts:
        if isinstance(part, str):
            content.append({"type": "text", "text": part})
        elif isinstance(part, dict):
            mime: str = part.get("mime_type", "")
            raw: bytes | str = part.get("data", b"")

            if isinstance(raw, str):
                b64_data = raw
                raw_bytes = base64.b64decode(raw)
            else:
                b64_data = base64.b64encode(raw).decode("utf-8")
                raw_bytes = raw

            if mime.startswith("image/"):
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_data}"}}
                )
            elif mime == "application/pdf":
                content.extend(_pdf_bytes_to_image_parts(raw_bytes))
            else:
                logger.warning("[LLM] OpenRouter: unsupported mime type '%s' — skipping part", mime)
    return content


class _OpenRouterModel(LLMModel):
    def __init__(self, client: Any, model_name: str, temperature: float = 0.1) -> None:
        self._client = client
        self._model_name = model_name
        self._temperature = temperature

    def generate_content(self, parts: list) -> LLMResponse:
        message_content = _parts_to_openai_content(parts)
        response = self._client.chat.completions.create(
            model=self._model_name,
            temperature=self._temperature,
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


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._client: Any = None

    def configure(self, api_key: str) -> None:
        try:
            import openai  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is required for the OpenRouter provider. "
                "Install it with: pip install 'openai>=1.0.0'"
            ) from exc
        self._client = openai.OpenAI(base_url=_OPENROUTER_BASE_URL, api_key=api_key)

    def create_model(
        self,
        model_name: str,
        generation_config: dict[str, Any] | None = None,
    ) -> LLMModel:
        if self._client is None:
            raise RuntimeError(
                "[LLM] OpenRouterProvider is not configured. "
                "Call configure(api_key) before create_model()."
            )
        temperature = float((generation_config or {}).get("temperature", 0.1))
        return _OpenRouterModel(self._client, model_name=model_name, temperature=temperature)


# ── Factory ────────────────────────────────────────────────────────────────────

def get_provider(env: dict[str, str] | None = None) -> BaseLLMProvider:
    """
    Return a provider instance for the active LLM_PROVIDER configuration.

    Reads LLM_PROVIDER from *env* (or os.environ if omitted).
    Supported values: 'google' (default), 'openrouter'.
    Raises ValueError for unrecognised values.
    """
    source = env if env is not None else os.environ
    provider_name = (source.get("LLM_PROVIDER") or "google").strip().lower()
    if provider_name == "google":
        return GeminiProvider()
    if provider_name == "openrouter":
        return OpenRouterProvider()
    raise ValueError(
        f"[LLM] Unsupported LLM_PROVIDER value: '{provider_name}'. "
        f"Supported values: {', '.join(sorted(_SUPPORTED_PROVIDERS))}"
    )
