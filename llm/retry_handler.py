"""
# llm/retry_handler.py
LLM Retry Handler - Groq API with key rotation and JSON extraction
Python 3.12 compatible
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

GROQ_API_URL  = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


# ── JSON extractor ─────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    """
    Robustly extract first valid JSON object from LLM output.
    Handles markdown fences, extra text, trailing commas.
    """
    if not raw:
        return {}

    # Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()

    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract FIRST complete {...} block
    brace_count = 0
    start: Optional[int] = None

    for i, ch in enumerate(cleaned):
        if ch == "{":
            if start is None:
                start = i
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0 and start is not None:
                candidate = cleaned[start: i + 1]
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    start       = None
                    brace_count = 0

    logger.warning(f"JSON extraction failed. Raw snippet: {raw[:300]}")
    return {"raw_response": raw}


# ── LLM Retry Handler ──────────────────────────────────────────────────────

class LLMRetryHandler:
    """
    Groq API client with:
    - Multiple API key rotation
    - 3 retries per key
    - Exponential backoff
    - Robust JSON parsing
    """

    def __init__(self, api_keys: list[str], model: str = DEFAULT_MODEL) -> None:
        self.api_keys = [k.strip() for k in api_keys if k.strip()]
        self.model    = model

        if not self.api_keys:
            raise ValueError("At least one Groq API key is required")

        logger.info(f"LLMRetryHandler initialised with {len(self.api_keys)} key(s)")

    # ── Core call ──────────────────────────────────────────────────────

    async def call_llm(
        self,
        prompt:          str,
        temperature:     float = 0.1,
        max_tokens:      int   = 1000,
        response_format: str   = "text",   # "text" | "json"
        system_prompt:   Optional[str] = None,
    ) -> Any:
        """
        Call Groq API with retry + key rotation.

        Returns:
            dict  if response_format="json"
            str   if response_format="text"

        Raises:
            RuntimeError if all retries exhausted
        """
        import aiohttp

        last_error: Optional[Exception] = None
        last_status: Optional[int] = None
        last_response_text: Optional[str] = None

        for key_index, api_key in enumerate(self.api_keys):
            headers = {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            messages: list[dict] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload = {
                "model":       self.model,
                "messages":    messages,
                "temperature": temperature,
                "max_tokens":  max_tokens,
            }

            for attempt in range(1, 4):   # 3 attempts per key
                backoff = min(2 ** (attempt - 1), 30)   # 1s, 2s, 4s … max 30s

                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            GROQ_API_URL,
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=60),
                        ) as response:

                            last_response_text = await response.text()
                            last_status = response.status

                            # ── Rotate key on auth failure ─────────────
                            if last_status == 401:
                                logger.warning(f"Key {key_index+1} unauthorised — rotating")
                                break   # try next key

                            # ── Backoff on rate limit ──────────────────
                            if last_status == 429:
                                logger.warning(
                                    f"Key {key_index+1} rate-limited "
                                    f"(attempt {attempt}) — waiting {backoff}s"
                                )
                                await asyncio.sleep(backoff)
                                continue

                            # ── Retry on server errors ─────────────────
                            if last_status >= 500:
                                logger.warning(
                                    f"Groq server error {last_status} "
                                    f"(attempt {attempt}) — waiting {backoff}s"
                                )
                                await asyncio.sleep(backoff)
                                continue

                            if last_status != 200:
                                body = await response.text()
                                raise RuntimeError(f"Groq HTTP {last_status}: {body[:200]}")

                            # ── Parse response ─────────────────────────
                            data = await response.json()

                            # Extract text from response
                            text_content: str = (
                                data["choices"][0]["message"]["content"]
                            )

                            if response_format == "json":
                                parsed = _extract_json(text_content)
                                if "raw_response" in parsed:
                                    raise ValueError(
                                        f"JSON parse failed. Raw: {text_content[:200]}"
                                    )
                                return parsed
                            else:
                                return text_content

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    last_error = e
                    logger.error(f"Network error (attempt {attempt}): {e}")
                    await asyncio.sleep(backoff)
                    continue

                except Exception as e:
                    last_error = e
                    logger.error(f"LLM call failed: {e}")
                    await asyncio.sleep(backoff)
                    continue

        # Build detailed error message
        error_details = f"LLM call failed after all retries.\n"
        error_details += f"Last error: {last_error}\n"
        error_details += f"Response preview: {last_response_text[:200] if last_response_text else 'None'}\n"
        error_details += f"Keys tried: {len(self.api_keys)}\n"
        error_details += f"Last status: {last_status}\n"

        # ✅ ADD HELPFUL MESSAGE
        if last_status == 429:
            error_details += "\n⚠️ Rate limit exceeded. Wait a few minutes or add more API keys.\n"
        elif last_status == 401:
            error_details += "\n⚠️ Invalid API key. Check your Groq API key in Connections.\n"
        
        logger.error(error_details)
        
        raise RuntimeError(error_details)


# ── Global instance ────────────────────────────────────────────────────────

_llm_handler: Optional[LLMRetryHandler] = None


def initialize_llm_handler(api_keys: list[str]) -> None:
    """Call once from main.py after Groq key is validated"""
    global _llm_handler
    _llm_handler = LLMRetryHandler(api_keys)
    logger.info("LLM handler initialised")


def get_llm_handler() -> LLMRetryHandler:
    """
    Get global handler. 
    Falls back to GROQ_API_KEY env var if not initialised via UI.
    """
    global _llm_handler

    if _llm_handler is None:
        import os
        env_keys = os.getenv("GROQ_API_KEY", "")
        if env_keys:
            _llm_handler = LLMRetryHandler(env_keys.split(","))
            logger.info("LLM handler initialised from env GROQ_API_KEY")
        else:
            # Try session state as last resort
            try:
                import streamlit as st
                key = st.session_state.get("groq_api_key", "")
                if key:
                    _llm_handler = LLMRetryHandler([key])
                    logger.info("LLM handler initialised from session state")
            except Exception:
                pass

    if _llm_handler is None:
        raise RuntimeError(
            "LLM handler not initialised. "
            "Set GROQ_API_KEY env var or configure via UI."
        )

    return _llm_handler