"""
Config Service
Provides configuration list APIs.
"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from models.csv_source_type import CsvSourceType
from models.schemas import UserResponse


class ConfigService:
    """Service for config endpoints."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _resolve_scope(current_user: UserResponse) -> tuple[str, str]:
        tenant_code = (current_user.tenant_code or settings.DEFAULT_TENANT_CODE or "").strip()
        organization_code = (current_user.organization_code or settings.DEFAULT_ORGANIZATION_CODE or "").strip()

        if not tenant_code or not organization_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Tenant/organization configuration is missing",
            )

        return tenant_code, organization_code

    @staticmethod
    def _resolve_criterias_mode(question_config: Any) -> str | None:
        if not isinstance(question_config, dict):
            return None

        for key in ("criterias_mode", "mode"):
            candidate = str(question_config.get(key, "")).strip()
            if candidate:
                return candidate

        entry_options = question_config.get("entry_options")
        if isinstance(entry_options, list):
            for entry in entry_options:
                if not isinstance(entry, dict):
                    continue
                for option_key in ("key", "value"):
                    candidate = str(entry.get(option_key, "")).strip()
                    if candidate:
                        return candidate
        return None

    @staticmethod
    def _serialize_csv_source_type(source_type: CsvSourceType) -> dict[str, Any]:
        question_config = source_type.question_config or {}
        default_thresholds = source_type.default_thresholds or {}
        return {
            "id": source_type.id,
            "type_key": source_type.type_key,
            "display_name": source_type.display_name,
            "description": source_type.description,
            "has_geo": bool(source_type.has_geo),
            "has_program": bool(source_type.has_program),
            "has_rubric": bool(source_type.has_rubric),
            "has_narrative": bool(source_type.has_narrative),
            "max_rows_per_upload": source_type.max_rows_per_upload,
            "available_filters": source_type.available_filters or [],
            "question_config": question_config,
            "default_thresholds": default_thresholds,
            "criterias_mode": ConfigService._resolve_criterias_mode(question_config),
            "threshold_config": default_thresholds,
        }

    def list(self, config_type: str, current_user: UserResponse) -> list[dict[str, Any]]:
        """
        List config entries for the requested type.
        Supported contract:
        - type=project -> project CSV source types (type_key=project_report).
        """
        normalized_type = (config_type or "").strip().lower()
        if normalized_type != "project":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported config type. Use type=project.",
            )

        tenant_code, organization_code = self._resolve_scope(current_user)
        source_types = (
            self.db.query(CsvSourceType)
            .filter(
                CsvSourceType.tenant_code == tenant_code,
                CsvSourceType.organization_code == organization_code,
                CsvSourceType.is_active.is_(True),
                CsvSourceType.type_key == "project_report",
            )
            .order_by(CsvSourceType.display_name.asc())
            .all()
        )

        return [self._serialize_csv_source_type(item) for item in source_types]
