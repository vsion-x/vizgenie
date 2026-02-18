"""
Datasource Registry - session-state backed, no YAML persistence
All URLs come from the UI (Streamlit session_state)
Python 3.12 compatible
"""

import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class DatasourceType(StrEnum):
    PROMETHEUS = "prometheus"
    POSTGRESQL = "postgresql"
    LOKI       = "loki"


@dataclass
class DatasourceConfig:
    uid:             str
    name:            str
    type:            DatasourceType
    url:             str
    enabled:         bool           = True
    auth:            Optional[dict] = None
    config:          dict           = field(default_factory=dict)
    required_fields: list[str]      = field(default_factory=list)

    @property
    def tool_module(self) -> str:
        return f"tools.{self.type}_tools"

    def validate(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if not self.uid:
            errors.append("uid is required")
        if not self.url:
            errors.append("url is required")
        if self.type not in DatasourceType:
            errors.append(f"Invalid type: {self.type}")
        return len(errors) == 0, errors

    def to_dict(self) -> dict:
        return {
            "uid":  self.uid,
            "name": self.name,
            "type": str(self.type),
            "url":  self.url,
        }


class DatasourceRegistry:
    """
    In-memory datasource registry.
    Single source of truth = Streamlit session_state.
    No YAML reads or writes — all URLs come from the UI.
    """

    def __init__(self) -> None:
        self._datasources: dict[str, DatasourceConfig] = {}

    # ── CRUD ───────────────────────────────────────────────────────────

    def register(self, config: DatasourceConfig) -> tuple[bool, list[str]]:
        """Register a datasource. Returns (success, errors)."""
        valid, errors = config.validate()
        if not valid:
            logger.warning(f"Datasource validation failed: {errors}")
            return False, errors
        self._datasources[config.uid] = config
        logger.info(f"Registered datasource: {config.uid} ({config.type})")
        return True, []

    def get(self, uid: str) -> Optional[DatasourceConfig]:
        """Get datasource by UID."""
        return self._datasources.get(uid)