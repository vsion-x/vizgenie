"""
# tools/pattern_extractor.py
Pattern Extractor
Sends sampled logs to LLM to extract regex patterns per error type.
Results are saved to config/patterns.json and used by ErrorAnalyzer.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class PatternStore:
    """Manages learned patterns — load from / save to disk."""

    PATTERN_FILE = Path("config/patterns.json")

    def __init__(self) -> None:
        self.patterns: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not self.PATTERN_FILE.exists():
            return
        try:
            data = json.loads(self.PATTERN_FILE.read_text(encoding="utf-8"))
            self.patterns = data.get("patterns", [])
            logger.info(f"Loaded {len(self.patterns)} patterns")
        except Exception as exc:
            logger.error(f"Failed to load patterns: {exc}")

    def _save(self) -> None:
        self.PATTERN_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.PATTERN_FILE.write_text(
                json.dumps({"patterns": self.patterns}, indent=2),
                encoding="utf-8",
            )
            logger.info(f"Saved {len(self.patterns)} patterns to {self.PATTERN_FILE}")
        except Exception as exc:
            logger.error(f"Failed to save patterns: {exc}")

    def get_patterns(self) -> List[Dict]:
        return self.patterns

    # ── LLM-based learning ────────────────────────────────────────────

    async def learn_from_logs(self, sampled: Dict) -> List[Dict]:
        """
        Send sampled log data to LLM and extract regex patterns.

        Args:
            sampled: {
                "full_logs":  [str, …],          # up to 5 complete log lines
                "summaries":  [{"error_type": str, "snippet": str}, …]
            }

        Returns:
            List of pattern dicts, each with:
                error_type, regex, intent, extract (optional)
        """
        from llm.retry_handler import get_llm_handler
        from llm.prompts       import PATTERN_LEARNING_PROMPT

        full_logs  = sampled.get("full_logs",  [])
        summaries  = sampled.get("summaries",  [])

        prompt = PATTERN_LEARNING_PROMPT.format(
            full_count=len(full_logs),
            full_logs="\n".join(
                f"{i + 1}. {log}" for i, log in enumerate(full_logs)
            ),
            summary_count=len(summaries),
            summaries="\n".join(
                f"- {s['error_type']}: {s['snippet']}" for s in summaries[:30]
            ),
        )

        logger.info("Sending logs to LLM for pattern extraction…")

        try:
            llm  = get_llm_handler()
            data = await llm.call_llm(
                prompt=prompt,
                temperature=0.0,
                max_tokens=2000,
                response_format="json",
            )
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")
            return []

        # data should already be a dict (retry_handler parses JSON)
        if isinstance(data, dict) and "patterns" in data:
            patterns = data["patterns"]
        elif isinstance(data, list):
            patterns = data
        else:
            logger.error(f"Unexpected LLM response shape: {type(data)}")
            return []

        if not isinstance(patterns, list):
            logger.error("Patterns field is not a list")
            return []

        self.patterns = patterns
        self._save()

        logger.info(f"✅ Extracted and saved {len(patterns)} patterns")
        return patterns


# ── Global singleton ──────────────────────────────────────────────────

_store: PatternStore | None = None


def get_pattern_store() -> PatternStore:
    global _store
    if _store is None:
        _store = PatternStore()
    return _store