"""
# llm/prompts.py
LLM prompt templates
Focused on RCA and pattern learning only.
Prometheus / SQL / Grafana prompts removed.
"""

# ══════════════════════════════════════════════════════════════════════
#  Pattern Learning
# ══════════════════════════════════════════════════════════════════════

PATTERN_LEARNING_PROMPT = """
You are analyzing application ERROR logs to extract monitoring patterns.

# FULL ERROR LOGS ({full_count} examples):
{full_logs}

# ADDITIONAL ERROR SUMMARIES ({summary_count} more):
{summaries}

# YOUR TASK:
Extract error patterns as JSON. Each pattern needs:
  1. error_type   — name (e.g. "NullPointerError", "ConnectionError")
  2. regex        — Python regex matching this error in raw log text
  3. intent       — what the error indicates (snake_case, e.g. "null_reference")
  4. extract      — dict of named capture-group regexes for structured fields:
       endpoint   → extract API path
       module     → extract module/function name
       error_code → extract error code
       latency_ms → extract latency

# RULES:
- One pattern per distinct error type
- Regex broad enough to catch message variations
- Intent lowercase with underscores
- Extract rules are optional; omit keys you cannot reliably capture
- Respond ONLY with valid JSON — no markdown, no explanation

# OUTPUT FORMAT:
{{
  "patterns": [
    {{
      "error_type": "NullPointerError",
      "regex": "NullPointerError.*'NoneType' object has no attribute",
      "intent": "null_reference",
      "extract": {{
        "endpoint": "path[\"\\\\s:]+([/\\\\w-]+)",
        "module":   "module[\"\\\\s:]+(\\\\w+)"
      }}
    }},
    {{
      "error_type": "ConnectionError",
      "regex": "ConnectionError.*(connection refused|reset|timeout)",
      "intent": "network_failure",
      "extract": {{
        "endpoint": "(https?://[^\\\\s]+)"
      }}
    }}
  ]
}}
"""


# ══════════════════════════════════════════════════════════════════════
#  RCA Analysis
# ══════════════════════════════════════════════════════════════════════

RCA_ANALYSIS_PROMPT = """
You are an expert SRE performing root cause analysis on a production incident.

Incident Context:
- Trigger Type: {trigger_type}
- Severity: {severity}
- Details: {trigger_details}
- Time Window: {time_window}

Evidence Collected:
1. Error Logs (top 10):
{error_logs}

2. Correlated Metrics:
{metrics_data}

3. Pattern Analysis:
{pattern_analysis}

4. Affected Components:
{affected_components}

Your Task:
1. Identify the ROOT CAUSE (not just symptoms)
2. Categorize: code | database | api | cache | config | infrastructure
3. Provide concrete evidence linking cause to symptoms
4. Generate actionable resolution steps with implementation details
5. Estimate resolution time and business impact

Resolution Categories:
- **code**: Application bugs, logic errors, null pointers, array index issues, division by zero
- **database**: Slow queries, connection leaks, deadlocks, schema issues, connection pool exhaustion
- **api**: External service failures, timeouts, rate limits, DNS errors, bad gateway
- **cache**: Cache misses, invalidation issues, memory pressure
- **config**: Wrong settings, missing env vars, resource limits, misconfigured services
- **infrastructure**: Hardware failures, network issues, scaling problems, out of memory

CRITICAL EXAMPLES FOR SPECIFIC ERRORS:

**DivisionByZero:**
- Root Cause: Code is dividing by a variable that can be zero (missing validation)
- Fix Location: Exact function/module where division occurs
- Implementation: Add `if denominator != 0:` check before division

**NullPointerError:**
- Root Cause: Code accessing object property without null check
- Implementation: Add `if object is not None:` before accessing properties

**OutOfMemory:**
- Root Cause: Memory leak OR insufficient heap size OR unbounded data structure
- Implementation: Fix memory leak OR increase heap size OR add size limits

**ConnectionError:**
- Root Cause: External API down OR DNS failure OR network partition OR connection pool exhausted
- Implementation: Add retry logic with exponential backoff, increase pool size, verify DNS

**DatabaseError:**
- Root Cause: Connection pool exhausted OR slow query OR deadlock OR DB overload
- Implementation: Increase pool size, optimize query with index, add transaction timeout

Output Format (JSON):
{{
    "root_cause": {{
        "category": "code|database|api|cache|config|infrastructure",
        "component": "EXACT module/service/function name",
        "description": "SPECIFIC explanation with exact location",
        "confidence_score": 0.0-1.0,
        "contact_team": "Who to notify: Backend Team, DBA Team, DevOps, etc."
    }},
    "evidence": [
        "SPECIFIC evidence item 1",
        "SPECIFIC evidence item 2"
    ],
    "impact_analysis": {{
        "affected_users": "estimate or 'unknown'",
        "affected_requests": "count or percentage",
        "business_impact": "revenue loss, SLA breach, user experience",
        "severity_justification": "Why this severity level"
    }},
    "resolution_suggestions": [
        {{
            "type": "code|database|config|infrastructure",
            "priority": "critical|high|medium|low",
            "suggestion": "One-line summary of fix",
            "implementation": "EXACT numbered steps to implement the fix",
            "estimated_time": "5 minutes|30 minutes|2 hours",
            "risk_level": "low|medium|high",
            "rollback_plan": "How to revert if fix causes issues",
            "contact": "Team / person responsible"
        }}
    ],
    "preventive_measures": [
        "Specific prevention action 1",
        "Specific prevention action 2"
    ],
    "mttd_analysis": {{
        "detection_time": 0,
        "detection_method": "Automated log monitoring",
        "improvement_suggestions": "How to detect faster next time"
    }},
    "mttr_estimate": {{
        "estimated_resolution_time": 1800,
        "assumptions": ["Fix requires code deploy", "No blocked dependencies"]
    }}
}}

Be EXTREMELY SPECIFIC:
- ❌ BAD: "Fix the code"
- ✅ GOOD: "Open services/user_service.py line 42, add: if discount_rate == 0: return original_price"

This is production incident response — be precise and actionable!
"""


# ══════════════════════════════════════════════════════════════════════
#  Keyword-based fallback (no LLM needed)
# ══════════════════════════════════════════════════════════════════════

def get_fallback_classification(user_query: str) -> dict:
    """Rule-based fallback — returns intent string."""
    q = user_query.lower()
    if any(w in q for w in ["root cause", "rca", "what caused", "why did", "incident"]):
        return {"intent": "rca", "reasoning": "Keyword match: RCA terms"}
    return {"intent": "rca", "reasoning": "Default: system is RCA-focused"}