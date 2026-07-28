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

# Evidence types — fallback/default only. The per-tenant source of truth is
# CsvSourceType.evidence_types_config (models/csv_source_type.py), so a new type or
# extension can be added per tenant without a code deploy. This constant is used to seed
# that column's default value and as a backstop for scripts run standalone (no execution
# context to resolve tenant config from), e.g. local/manual script runs.
# "excel" is .xlsx only: requirements.txt pins openpyxl (xlsx reader) but not xlrd, which
# legacy .xls files need — routing a .xls URL to pandas.read_excel() would fail at runtime.
DEFAULT_EVIDENCE_TYPES_CONFIG = [
    {"key": "image", "label": "Image", "extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]},
    {"key": "pdf", "label": "PDF", "extensions": [".pdf"]},
    {"key": "excel", "label": "Excel", "extensions": [".xlsx"]},
]

# Canonical set of accepted evidence-type keys (derived from the default config above).
ALLOWED_EVIDENCE_TYPES = {item["key"] for item in DEFAULT_EVIDENCE_TYPES_CONFIG}

# File extensions per evidence type — used by the pre-processor to classify evidence URLs.
EVIDENCE_TYPE_EXTENSIONS = {item["key"]: item["extensions"] for item in DEFAULT_EVIDENCE_TYPES_CONFIG}

# Relevance tag values — written by the processor, read by report_service and cleanup script.
RELEVANCE_TAG_RELEVANT = "Relevant"
RELEVANCE_TAG_PARTIAL = "Partially Relevant"
RELEVANCE_TAG_IRRELEVANT = "Irrelevant"
RELEVANCE_TAG_NOT_VALIDATED = "notValidated"

# Required header in an uploaded school-filter CSV. The pre-processor script
# (scripts/pre-processor/1-pre-processor.py) reads this exact column name via
# csv.DictReader; the service validates it up front so a filter that would match
# nothing is rejected at upload instead of silently dropping every row.
# Matches the input CSV's own school-ID column name by default (see
# DEFAULT_INPUT_SCHOOL_ID_COLUMN below) rather than the UDISE+ program's branded name,
# since the two columns are compared by value and using the same label in both files
# makes that relationship obvious instead of requiring the uploader to learn a second
# name for the same field. The two constants are independently configurable per tenant
# via CsvSourceType.school_filter_config / column_mappings.geo.school_id — this is just
# their shared default.
SCHOOL_FILTER_REQUIRED_COLUMN = "School ID"

# Fallback/default only — per-tenant source of truth is
# CsvSourceType.column_mappings["geo"]["school_id"] (models/csv_source_type.py). Used to
# seed that config's default and as a backstop for scripts run standalone (no execution
# context to resolve tenant config from).
DEFAULT_INPUT_SCHOOL_ID_COLUMN = "School ID"

# Fallback/default only — per-tenant source of truth is
# CsvSourceType.evidence_columns[0]["column"] (models/csv_source_type.py). Used the same
# way as DEFAULT_INPUT_SCHOOL_ID_COLUMN above.
DEFAULT_EVIDENCE_COLUMN = "Task Evidence"

# Fallback/default only — per-tenant source of truth is CsvSourceType.identity_column
# (models/csv_source_type.py). The column whose value identifies "who/what this evidence
# row belongs to" for the pre-processor's group-aware split, the processor's resume/dedup
# keys, and the per-(identity, task) relevant-evidence cap. "UUID" is correct for
# project_report (one evidence upload per user per project); other CSV shapes where the
# same UUID legitimately recurs across independent submissions (e.g. "observation", where
# one mentor submits many separate school visits) should point this at a column that's
# actually unique per submission instead.
DEFAULT_IDENTITY_COLUMN = "UUID"

# Backward-compat default type_key for config lookups (services/config_service.py) made
# before multiple CsvSourceTypes existed, where an omitted type_key implicitly meant
# "project_report".
DEFAULT_CSV_TYPE_KEY = "project_report"

# Full set of bucketed relevance tags — used for report aggregation.
RELEVANCE_TYPES = {
    RELEVANCE_TAG_RELEVANT,
    RELEVANCE_TAG_PARTIAL,
    RELEVANCE_TAG_IRRELEVANT,
    RELEVANCE_TAG_NOT_VALIDATED,
}

# processing_config JSONB key for the evidence-type filter.
PROCESSING_CONFIG_KEY_EVIDENCE_TYPES = "evidence_types"
