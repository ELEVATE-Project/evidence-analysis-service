"""
Application-wide string constants.
Define shared values here so they are never duplicated across files.
"""

# LLM provider identifiers — must match the LLM_PROVIDER env var values.
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENROUTER = "openrouter"

# API key env var prefixes — used for dynamic key discovery (KEY_1, KEY_2, ... KEY_N).
GEMINI_API_KEY_PREFIX = "GEMINI_API_KEY"
OPENROUTER_API_KEY_PREFIX = "OPENROUTER_API_KEY"

# OpenRouter API endpoints.
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Relevance Tag value for evidence rows skipped by the relevant-evidence cap
# (no AI call made). Used by the processor, report aggregation, and the
# notValidated cleanup script — change here, not at each call site.
RELEVANCE_TAG_NOT_VALIDATED = "notValidated"
