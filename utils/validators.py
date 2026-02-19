"""
# utils/validators.py
Input validation utilities
Python 3.12 compatible
"""

import re
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def validate_url(
    url: str,
    allowed_schemes: tuple[str, ...] = ("http", "https"),
) -> tuple[bool, Optional[str]]:
    """
    Validate URL format.

    Args:
        url:             URL string to validate
        allowed_schemes: Permitted URI schemes

    Returns:
        (is_valid, error_message)
    """
    if not url or not url.strip():
        return False, "URL cannot be empty"

    try:
        parsed = urlparse(url)

        if parsed.scheme not in allowed_schemes:
            return False, f"URL must use one of {allowed_schemes}. Got: '{parsed.scheme}'"

        if not parsed.netloc:
            return False, "URL must include a host"

        return True, None

    except Exception as exc:
        return False, f"Invalid URL: {exc}"


def validate_connection_string(conn_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate PostgreSQL connection string.

    Expected format:
        postgresql://user:password@host:port/database

    Returns:
        (is_valid, error_message)
    """
    if not conn_str or not conn_str.strip():
        return False, "Connection string cannot be empty"

    pattern = r"^postgresql://[^:]+:[^@]+@[^:/]+:\d+/.+$"
    if not re.match(pattern, conn_str):
        return (
            False,
            "Invalid format. Expected: postgresql://user:password@host:port/database",
        )

    return True, None


def validate_api_key(
    api_key: str,
    min_length: int = 20,
) -> tuple[bool, Optional[str]]:
    """
    Validate generic API key.

    Args:
        api_key:    Key string to validate
        min_length: Minimum acceptable length

    Returns:
        (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty"

    if len(api_key.strip()) < min_length:
        return False, f"API key too short (minimum {min_length} characters)"

    return True, None


def validate_groq_key(api_key: str) -> tuple[bool, Optional[str]]:
    """
    Validate Groq API key format (gsk_…).

    Returns:
        (is_valid, error_message)
    """
    valid, err = validate_api_key(api_key, min_length=20)
    if not valid:
        return False, err

    if not api_key.strip().startswith("gsk_"):
        return False, "Groq API key must start with 'gsk_'"

    return True, None


def validate_grafana_key(api_key: str) -> tuple[bool, Optional[str]]:
    """
    Validate Grafana service-account token format (glsa_…).

    Returns:
        (is_valid, error_message)
    """
    valid, err = validate_api_key(api_key, min_length=20)
    if not valid:
        return False, err

    if not api_key.strip().startswith("glsa_"):
        return False, "Grafana API key must start with 'glsa_'"

    return True, None


def validate_threshold_config(thresholds: dict) -> tuple[bool, list[str]]:
    """
    Validate monitoring threshold configuration.

    Args:
        thresholds: dict of severity → threshold values

    Returns:
        (is_valid, error_messages)
    """
    errors: list[str] = []
    valid_severities = {"critical", "high", "medium", "low"}

    for severity, values in thresholds.items():
        if severity not in valid_severities:
            errors.append(f"Unknown severity '{severity}'")
            continue

        if not isinstance(values, dict):
            errors.append(f"Thresholds for '{severity}' must be a dict")
            continue

        if "error_rate" in values:
            rate = values["error_rate"]
            if not (0.0 <= rate <= 1.0):
                errors.append(f"error_rate for '{severity}' must be in [0.0, 1.0]")

        if "latency_p95" in values:
            latency = values["latency_p95"]
            if latency <= 0:
                errors.append(f"latency_p95 for '{severity}' must be > 0")

    return (len(errors) == 0, errors)