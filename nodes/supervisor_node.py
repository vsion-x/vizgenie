"""
# nodes/supervisor_node.py
Supervisor node - LLM-based intent classification
Classifies user query into: metrics | sql | troubleshoot | learning | rca
Python 3.12 compatible
"""

import logging
from typing import Literal
from schemas.state import AgentState
from llm.retry_handler import get_llm_handler
from llm.prompts import SUPERVISOR_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# Valid intents
Intent = Literal["metrics", "sql", "troubleshoot", "learning", "rca"]

# ── Fallback keyword classifier ────────────────────────────────────────

_KEYWORD_MAP: list[tuple[list[str], Intent]] = [
    (["cpu", "memory", "ram", "disk", "network", "latency", "throughput",
      "request", "rate", "metric", "prometheus", "gauge", "counter",
      "p95", "p99", "bandwidth", "uptime", "saturation"],           "metrics"),

    (["sql", "table", "database", "query", "select", "sales", "revenue",
      "customer", "order", "postgres", "rows", "column", "join",
      "aggregate", "sum", "count", "group by"],                      "sql"),

    (["rca", "root cause", "incident", "anomaly", "alert",
      "pagerduty", "down", "outage", "spike", "degraded"],           "rca"),

    (["learn", "pattern", "categorize", "train", "extract",
      "unknown log", "new pattern"],                                  "learning"),

    (["slow", "why", "debug", "investigate", "troubleshoot",
      "error", "exception", "failing", "broken", "issue", "problem",
      "timeout", "500", "crash", "trace"],                           "troubleshoot"),
]


def _keyword_fallback(query: str) -> Intent:
    """Rule-based intent classification fallback"""
    q = query.lower()
    scores: dict[Intent, int] = {
        "metrics": 0, "sql": 0, "troubleshoot": 0, "learning": 0, "rca": 0
    }

    for keywords, intent in _KEYWORD_MAP:
        for kw in keywords:
            if kw in q:
                scores[intent] += 1

    best: Intent = max(scores, key=lambda k: scores[k])

    # Default to metrics if no strong signal
    if scores[best] == 0:
        best = "metrics"

    logger.info(f"Keyword fallback classification: {best} (scores={scores})")
    return best


def _pick_datasource(intent: Intent, available_datasources: list[dict]) -> dict:
    """Auto-select best datasource for intent"""
    type_preference: dict[Intent, list[str]] = {
        "metrics":      ["prometheus"],
        "sql":          ["postgresql"],
        "troubleshoot": ["loki", "prometheus"],
        "learning":     ["loki"],
        "rca":          ["loki", "prometheus"],
    }

    preferred_types = type_preference.get(intent, ["prometheus"])

    for preferred in preferred_types:
        ds = next(
            (d for d in available_datasources if d.get("type") == preferred),
            None,
        )
        if ds:
            return ds

    # Return first available
    return available_datasources[0] if available_datasources else {}


# ── Main supervisor node ───────────────────────────────────────────────

async def supervisor_node(state: AgentState) -> AgentState:
    """
    LangGraph node: Classify intent and select datasource.
    Falls back to keyword matching if LLM fails.
    """
    user_query          = state["user_query"]
    available_datasources = state.get("available_datasources", [])

    logger.info(f"Supervisor classifying: '{user_query[:80]}'")

    # ── Step 1: Try LLM classification ────────────────────────────────
    try:
        llm_handler = get_llm_handler()

        ds_names = [
            f"{ds['name']} ({ds['type']})"
            for ds in available_datasources
        ]

        prompt = SUPERVISOR_CLASSIFICATION_PROMPT.format(
            user_query=user_query,
            available_datasources=", ".join(ds_names) or "none configured",
        )

        result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=300,
            response_format="json",
        )

        raw_intent = result.get("intent", "").lower().strip()

        # Validate intent value
        valid_intents: set[Intent] = {"metrics", "sql", "troubleshoot", "learning", "rca"}
        intent: Intent = raw_intent if raw_intent in valid_intents else _keyword_fallback(user_query)

        suggested_ds_name = result.get("suggested_datasource", "")

        logger.info(f"LLM classified intent='{intent}', suggested_ds='{suggested_ds_name}'")

    except Exception as e:
        logger.warning(f"LLM classification failed ({e}), using keyword fallback")
        intent = _keyword_fallback(user_query)
        state["fallback_mode"] = True

    # ── Step 2: Select datasource ──────────────────────────────────────
    # Honour the datasource already selected in the UI if present
    selected = state.get("selected_datasource") or {}

    if not selected:
        selected = _pick_datasource(intent, available_datasources)

    # ── Step 3: Update state ───────────────────────────────────────────
    state["intent"]             = intent
    state["selected_datasource"] = selected

    logger.info(
        f"Supervisor done — intent={intent}, "
        f"datasource={selected.get('uid', 'none')}"
    )

    return state