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

# Evidence type identifiers — canonical set accepted by the evidence-type filter.
ALLOWED_EVIDENCE_TYPES = {"image", "pdf", "excel"}

# File extensions per evidence type — used by the pre-processor to classify evidence URLs.
EVIDENCE_TYPE_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    "pdf": [".pdf"],
    "excel": [".xlsx", ".xls"],
}

# Relevance tag values — written by the processor, read by report_service and cleanup script.
RELEVANCE_TAG_RELEVANT = "Relevant"
RELEVANCE_TAG_PARTIAL = "Partially Relevant"
RELEVANCE_TAG_IRRELEVANT = "Irrelevant"
RELEVANCE_TAG_NOT_VALIDATED = "notValidated"

# Full set of bucketed relevance tags — used for report aggregation.
RELEVANCE_TYPES = {
    RELEVANCE_TAG_RELEVANT,
    RELEVANCE_TAG_PARTIAL,
    RELEVANCE_TAG_IRRELEVANT,
    RELEVANCE_TAG_NOT_VALIDATED,
}

# processing_config JSONB key for the evidence-type filter.
PROCESSING_CONFIG_KEY_EVIDENCE_TYPES = "evidence_types"
