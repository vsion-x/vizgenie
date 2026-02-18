"""
# llm/prompts.py
LLM prompt templates for all agents
Generic and reusable across different contexts
"""

# ===== SUPERVISOR PROMPTS =====

SUPERVISOR_CLASSIFICATION_PROMPT = """
You are a query intent classifier for an observability and analytics platform.

Classify the user's query into ONE of these categories:

1. **metrics** - User wants to visualize Prometheus metrics
   Examples: "Show CPU usage", "Memory consumption over time", "Network I/O trends"

2. **sql** - User wants to query PostgreSQL database
   Examples: "Top 10 customers by revenue", "Sales by region", "User activity report"

3. **troubleshoot** - User needs performance investigation using logs + metrics
   Examples: "Why is my API slow?", "Database bottleneck", "High error rate investigation"

4. **learning** - User wants to teach the system new log patterns
   Examples: "Learn new log patterns", "Categorize these logs", "Train on error patterns"

5. **rca** - User explicitly requests root cause analysis
   Examples: "What caused the outage?", "Root cause of errors", "Why did the service crash?"

User Query: {user_query}

Available Datasources: {datasources}

Return ONLY valid JSON:
{{
    "intent": "metrics|sql|troubleshoot|learning|rca",
    "reasoning": "Brief explanation",
    "suggested_datasource": "datasource_uid_or_null"
}}
"""


# ===== METRICS AGENT PROMPTS =====

METRIC_SUGGESTION_PROMPT = """
You are a Prometheus metrics expert.

Analyze this user query and suggest up to 5 relevant Prometheus metric names that would answer their question.

User Query: {user_query}

Guidelines:
- Suggest actual Prometheus metric naming patterns (e.g., node_cpu_seconds_total, http_requests_total)
- Consider standard exporters: node_exporter, kube-state-metrics, application metrics
- Prioritize metrics that directly answer the query
- Do NOT invent metrics - suggest realistic names based on common patterns

Return JSON:
{{
    "suggested_metrics": ["metric1", "metric2", "metric3", "metric4", "metric5"],
    "reasoning": "Why these metrics are relevant"
}}
"""


# ===== SQL AGENT PROMPTS =====

SQL_GENERATION_PROMPT = """
You are a PostgreSQL query expert.

Generate a SQL query based on the user's request and database schema.

Context:
- User Query: {user_query}
- Database Schema: {metadata_context}
- Datasource UID: {datasource_uid}

Important Rules:
1. Use ONLY tables and columns defined in the schema
2. All identifiers MUST be double-quoted: "TABLE_NAME", "COLUMN_NAME"
3. PostgreSQL is case-sensitive with quoted identifiers
4. Use explicit JOINs with ON conditions
5. Never use SELECT *
6. For aggregations, use appropriate GROUP BY
7. Add ORDER BY for meaningful sorting

Examples:
- Simple: `SELECT "CUSTOMERNAME", "SALES" FROM "sales_data" WHERE "COUNTRY" = 'USA';`
- Aggregation: `SELECT "COUNTRY", SUM("SALES") AS "total" FROM "sales_data" GROUP BY "COUNTRY" ORDER BY "total" DESC;`
- Window: `SELECT "YEAR_ID", "MONTH_ID", SUM("SALES") OVER (PARTITION BY "YEAR_ID") FROM "sales_data";`

Return ONLY JSON:
{{
    "mandatory_datasource_uuid": "{datasource_uid}",
    "userquery": "{user_query}",
    "query": "your_sql_here",
    "explanation": "What the query does"
}}
"""
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
- Contact: Backend team + Code owner of affected module

**NullPointerError:**
- Root Cause: Code accessing object property without null check
- Fix Location: Exact line in code where null dereference happens
- Implementation: Add `if object is not None:` before accessing properties
- Contact: Backend team + Feature owner

**OutOfMemory:**
- Root Cause: Memory leak OR insufficient heap size OR unbounded data structure
- Fix Location: Check for list/dict growing without bounds, check heap size config
- Implementation: Fix memory leak OR increase `-Xmx` heap size OR add size limits
- Contact: DevOps team + Backend team

**ConnectionError:**
- Root Cause: External API down OR DNS failure OR network partition OR connection pool exhausted
- Fix Location: Check external service health, check DNS config, check connection pool settings
- Implementation: Add retry logic with exponential backoff, increase pool size, verify DNS
- Contact: External API provider + Network team + DevOps

**DatabaseError:**
- Root Cause: Connection pool exhausted OR slow query OR deadlock OR DB overload
- Fix Location: Check pool size, check slow query logs, check deadlock logs
- Implementation: Increase pool size, optimize query with index, add transaction timeout
- Contact: DBA team + Backend team

Output Format (JSON):
{{
    "root_cause": {{
        "category": "code|database|api|cache|config|infrastructure",
        "component": "EXACT module/service/function name (e.g., 'UserService.calculateDiscount()', 'PostgreSQL connection pool', '/api/users endpoint')",
        "description": "SPECIFIC explanation with exact location: 'Division by zero in UserService.calculateDiscount() line 42 when discount_rate is 0'",
        "confidence_score": 0.0-1.0,
        "contact_team": "Who to notify: Backend Team, DBA Team, DevOps, External API Provider"
    }},
    "evidence": [
        "SPECIFIC evidence like: 'Error occurs at UserService.py:42 in calculateDiscount() function'",
        "Stack trace shows: ZeroDivisionError at line 42: price / discount_rate",
        "Affected endpoint: POST /api/checkout - gets 15 requests/min"
    ],
    "impact_analysis": {{
        "affected_users": "estimate or 'unknown'",
        "affected_requests": "percentage or count: '15 requests/min affected'",
        "business_impact": "revenue loss, SLA breach, user experience",
        "severity_justification": "Why this severity level"
    }},
    "resolution_suggestions": [
        {{
            "type": "code|database|config|infrastructure",
            "priority": "critical|high|medium|low",
            "suggestion": "Add zero-check validation before division",
            "implementation": "EXACT steps:
1. Open file: services/user_service.py
2. Go to line 42 in calculateDiscount() function
3. Add before division: if discount_rate == 0: return original_price
4. Add logging: logger.warning('Zero discount rate received for order {{order_id}}')",
            "estimated_time": "5 minutes|30 minutes|2 hours",
            "risk_level": "low|medium|high",
            "rollback_plan": "Revert commit abc123 if issues arise",
            "contact": "Backend Team Lead (John Doe), Code Owner (Jane Smith)"
        }}
    ],
    "preventive_measures": [
        "SPECIFIC prevention: Add input validation in calculateDiscount() to reject discount_rate <= 0",
        "Add unit test: test_calculateDiscount_zero_rate() to catch this",
        "Add Sentry alert: DivisionByZero in UserService"
    ],
    "mttd_analysis": {{
        "detection_time": "How long to detect (seconds)",
        "detection_method": "What triggered detection",
        "improvement_suggestions": "How to detect faster"
    }},
    "mttr_estimate": {{
        "estimated_resolution_time": "seconds",
        "assumptions": ["Fix requires code deploy", "No dependencies blocked"]
    }}
}}

Be EXTREMELY SPECIFIC:
- ❌ BAD: "Fix the code"
- ✅ GOOD: "Open services/user_service.py line 42, add: if discount_rate == 0: return original_price"

- ❌ BAD: "Contact backend team"
- ✅ GOOD: "Contact: Backend Team Lead (John Doe), Code Owner: UserService (Jane Smith)"

- ❌ BAD: "Database issue"
- ✅ GOOD: "PostgreSQL connection pool exhausted (50/50 connections used), increase max_connections from 50 to 100 in postgresql.conf"

This is production incident response - be precise and actionable!
"""


# ===== FALLBACK PROMPTS =====

def get_fallback_classification(user_query: str) -> dict:
    """
    Rule-based fallback when LLM is unavailable
    """
    query_lower = user_query.lower()
    
    # Keyword mapping
    if any(word in query_lower for word in ['cpu', 'memory', 'metric', 'prometheus', 'gauge', 'counter']):
        return {'intent': 'metrics', 'reasoning': 'Keyword match: metrics-related terms'}
    
    elif any(word in query_lower for word in ['sql', 'database', 'table', 'select', 'query', 'postgres']):
        return {'intent': 'sql', 'reasoning': 'Keyword match: database-related terms'}
    
    elif any(word in query_lower for word in ['slow', 'why', 'bottleneck', 'investigate', 'performance', 'issue']):
        return {'intent': 'troubleshoot', 'reasoning': 'Keyword match: investigation-related terms'}
    
    elif any(word in query_lower for word in ['learn', 'pattern', 'categorize', 'train', 'teach']):
        return {'intent': 'learning', 'reasoning': 'Keyword match: learning-related terms'}
    
    elif any(word in query_lower for word in ['root cause', 'rca', 'what caused', 'why did', 'incident']):
        return {'intent': 'rca', 'reasoning': 'Keyword match: RCA-related terms'}
    
    else:
        # Default to troubleshooting for ambiguous queries
        return {'intent': 'troubleshoot', 'reasoning': 'Default fallback: investigator can handle broad queries'}