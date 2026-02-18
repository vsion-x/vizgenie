"""
Persistent credentials store — saves to .credentials.json
Loads automatically on every Streamlit rerun
Python 3.12 compatible
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(".credentials.json")

# Keys to persist (never store raw passwords for prod — fine for local dev)
PERSISTENT_KEYS = [
    "groq_api_key",
    "grafana_url",
    "grafana_api_key",
    "prometheus_url",
    "postgres_url",
    "loki_url",
    "groq_validated",
    "grafana_validated",
    "available_datasources",
    "grafana_datasources",
]


def save_credentials() -> None:
    """Save current session_state credentials to disk"""
    try:
        import streamlit as st

        data = {
            key: st.session_state[key]
            for key in PERSISTENT_KEYS
            if key in st.session_state and st.session_state[key] not in ("", [], None, False)
        }

        CREDENTIALS_FILE.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        logger.debug(f"Credentials saved: {list(data.keys())}")

    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")


def load_credentials() -> None:
    """
    Load saved credentials into session_state.
    Called once at app startup — skips keys already set.
    """
    if not CREDENTIALS_FILE.exists():
        return

    try:
        import streamlit as st

        data: dict[str, Any] = json.loads(
            CREDENTIALS_FILE.read_text(encoding="utf-8")
        )

        for key, value in data.items():
            # Only restore if not already set in this session
            if not st.session_state.get(key):
                st.session_state[key] = value

        # Re-initialise LLM handler if groq key was restored
        groq_key = st.session_state.get("groq_api_key", "")
        if groq_key:
            try:
                from llm.retry_handler import initialize_llm_handler
                initialize_llm_handler(groq_key.split(","))
            except Exception as e:
                logger.warning(f"Could not reinitialise LLM handler: {e}")

        logger.info(f"Credentials loaded: {list(data.keys())}")

    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")


def clear_credentials() -> None:
    """Delete saved credentials file and reset session state"""
    try:
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
            logger.info("Credentials file deleted")

        import streamlit as st
        for key in PERSISTENT_KEYS:
            if key in st.session_state:
                del st.session_state[key]

    except Exception as e:
        logger.error(f"Failed to clear credentials: {e}")