"""
# utils/credentials_store.py
Persistent credentials store — saves to .credentials.json
Focused on Groq API key only. Log source credentials are
persisted separately by LogSourceRegistry (data/log_sources.json).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = Path(".credentials.json")

# Only persist what belongs here; log source creds live in data/log_sources.json
PERSISTENT_KEYS = [
    "groq_api_key",
    "groq_validated",
]


def save_credentials() -> None:
    """Persist current session_state credentials to disk."""
    try:
        import streamlit as st

        data = {
            key: st.session_state[key]
            for key in PERSISTENT_KEYS
            if key in st.session_state
            and st.session_state[key] not in ("", [], None, False)
        }

        CREDENTIALS_FILE.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        logger.debug(f"Credentials saved: {list(data.keys())}")

    except Exception as exc:
        logger.error(f"Failed to save credentials: {exc}")


def load_credentials() -> None:
    """
    Load saved credentials into session_state at startup.
    Skips keys already set in the current session.
    """
    if not CREDENTIALS_FILE.exists():
        return

    try:
        import streamlit as st

        data: dict[str, Any] = json.loads(
            CREDENTIALS_FILE.read_text(encoding="utf-8")
        )

        for key, value in data.items():
            if not st.session_state.get(key):
                st.session_state[key] = value

        # Re-initialise LLM handler if Groq key was restored
        groq_key = st.session_state.get("groq_api_key", "")
        if groq_key:
            try:
                from llm.retry_handler import initialize_llm_handler
                initialize_llm_handler(groq_key.split(","))
            except Exception as exc:
                logger.warning(f"Could not reinitialise LLM handler: {exc}")

        logger.info(f"Credentials loaded: {list(data.keys())}")

    except Exception as exc:
        logger.error(f"Failed to load credentials: {exc}")


def clear_credentials() -> None:
    """Delete saved credentials and reset session state."""
    try:
        if CREDENTIALS_FILE.exists():
            CREDENTIALS_FILE.unlink()
            logger.info("Credentials file deleted")

        import streamlit as st

        for key in PERSISTENT_KEYS:
            if key in st.session_state:
                del st.session_state[key]

    except Exception as exc:
        logger.error(f"Failed to clear credentials: {exc}")