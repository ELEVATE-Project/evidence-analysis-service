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

# Evidence types — the single source of truth for the evidence-type filter.
# Ordered list of {key, label}. Served to the frontend via
# GET /config/list?type=evidence_type and used to validate the
# evidence_types field on execution create/update requests.
EVIDENCE_TYPES = [
    {"key": "image", "label": "Image"},
    {"key": "pdf", "label": "PDF"},
    {"key": "excel", "label": "Excel"},
]

# Canonical set of accepted evidence-type keys (derived from EVIDENCE_TYPES).
ALLOWED_EVIDENCE_TYPES = {item["key"] for item in EVIDENCE_TYPES}

# File extensions per evidence type — used by the pre-processor to classify evidence URLs.
# "excel" is .xlsx only: requirements.txt pins openpyxl (xlsx reader) but not xlrd, which
# legacy .xls files need — routing a .xls URL to pandas.read_excel() would fail at runtime.
EVIDENCE_TYPE_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    "pdf": [".pdf"],
    "excel": [".xlsx"],
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
