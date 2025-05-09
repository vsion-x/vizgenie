# Function to generate PromQL query using OpenAI
import json
import os
from handlers.groq_handler import GroqHandler as groq

groq_handler = groq(os.getenv("GROQ_API_KEY", "").split(","))


def generate_promql_query(user_query_map):

    
    prompt = f"""
        Context:You are generating PromQL queries to retrieve system and application metrics from Prometheus.

        Objective:Create accurate, optimized PromQL queries strictly using the provided input. Prioritize custom metrics and apply only the given labels.

        Style:lear, minimal, and Prometheus-friendly.

        Tone:Professional and concise.

        Audience:Engineers and analysts experienced with Prometheus.

        Response:Return a valid JSON object only — no extra text or explanation.

        Input array:  
        {json.dumps(user_query_map, indent=4)}

        Guidelines:

        1. For each item:
        - Use the `mandatory_datasource_uuid` (required).
        - Use only the `mandatory_similar_metrics`. **Do not use any other metrics.**
        - Use only the `mandatry_corresponding_metrics_labels`. **Do not add or infer labels.**

        2. Follow PromQL best practices:
        - Use text-based identifiers (e.g., `instance`, `job`) and include an `id` label when aggregating.
        - Group only by provided labels.
        - Ensure performance and correctness.

        3. Format output as:
        {{
            "result": [
                {{
                    "mandatory_datasource_uuid": "value",
                    "userquery": "value",
                    "query": "Generated PromQL query"
                }}
            ]
        }}

        Example queries:

        - List all containers:  
        `"count(container_memory_usage_bytes) by (container_name)"`

        - Highest CPU container:  
        `"topk(1, sum by (container_name) (rate(container_cpu_usage_seconds_total[5m])))"`

        - Redis clients:  
        `"redis_connected_clients"`

        - Node CPU:  
        `"node_cpu_seconds_total"`
    """

    result = groq_handler.groqrequest(prompt)

    if result.startswith("```"):
        result = result.strip("`").strip()
    if result.lower().startswith("json"):
        result = result[4:].strip()
    # Attempt to parse the JSON response
    try:
        result = json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON response from LLM"}

    if result.get("error"):
        return {"error": "Failed to generate PromQL query from Groq API"}

    return result


def generate_grafana_dashboard(query_responses):
    """
    Generate a Grafana 9.x dashboard JSON supporting both Prometheus and PostgreSQL datasources
    """
    prompt = f"""
    Create Grafana 9.x dashboard JSON that supports both Prometheus and PostgreSQL datasources.
    Use this structure for mixed datasource dashboards:

    Input configuration:
    {json.dumps(query_responses, indent=2)}

    Base template:
    {{
        "title": "Generated Dashboard",
        "uid": "auto-dash-{hash(json.dumps(query_responses))}",
        "panels": [
            {{
                "type": "$VIS_TYPE",
                "title": "Panel Title",
                "datasource": {{
                    "type": "$DATASOURCE_TYPE",
                    "uid": "$DATASOURCE_UID"
                }},
                "targets": [
                    {{
                        "expr": "$QUERY",          // PromQL
                        "rawSql": "$QUERY",        // PostgreSQL
                        "refId": "A",
                        "format": "$RESULT_FORMAT",
                        "legendFormat": "{{{{label}}}}"  // For time series
                    }}
                ],
                "options": {{/* Visualization-specific options */}},
                "gridPos": {{ "x": 0, "y": 0, "w": 12, "h": 8 }}
            }}
        ],
        "schemaVersion": 36
    }}

    Visualization Rules:

    1. Prometheus Panels:
    - Timeseries: Metrics with timestamped values
    - Piechart: Aggregated categorical distributions
    - Gauge/Bargauge: Single values/comparisons
    - Stat: Simple numeric displays
    - Format: "time_series" for metrics, "table" for aggregations

    2. PostgreSQL Panels:
    - Table: Raw SQL results
    - Timeseries: Time-based queries (must have time column)
    - Stat: Single value results
    - Piechart: Category distributions
    - Format: "table" for most queries, "time_series" if time column exists

    3. Panel Type Mapping:
    | Query Type        | Suggested Panel   | Format       |
    |-------------------|-------------------|--------------|
    | Prometheus Range  | timeseries        | time_series  |
    | Prometheus Aggr.  | piechart/stat     | table        |
    | SQL SELECT        | table             | table        |
    | SQL Aggregation   | stat/piechart     | table        |
    | SQL Time Series   | timeseries        | time_series  |

    4. Special Handling:
    - For PostgreSQL timeseries:
      * Query MUST return a time column named 'time'
      * Include "convertToDateType": true in fieldConfig
    - Mix datasources in same dashboard
    - Maintain consistent grid layout

    5. Examples:
    - Prometheus CPU Usage:
      {{
        "type": "timeseries",
        "datasource": {{"type":"prometheus","uid":"DS_UID"}},
        "targets": [{{
            "expr": "rate(node_cpu_seconds_total[5m])",
            "format": "time_series"
        }}]
      }}

    - PostgreSQL Sales Report:
      {{
        "type": "table",
        "datasource": {{"type":"postgres","uid":"DS_UID"}},
        "targets": [{{
            "rawSql": "SELECT product, SUM(sales) FROM orders GROUP BY product",
            "format": "table"
        }}]
      }}

    - Mixed Dashboard Layout:
      "panels": [
        {{/* Prometheus panel */ "gridPos": {{"x":0,"y":0,"w":12,"h":8}} }},
        {{/* Postgres panel */   "gridPos": {{"x":0,"y":8,"w":12,"h":8}} }}
      ]

    Output ONLY valid JSON. No markdown or explanations.
    """

    result = groq_handler.groqrequest(prompt)

    if result.startswith("```"):
        result = result.strip("`").strip()
    if result.lower().startswith("json"):
        result = result[4:].strip()


    try:
        result = json.loads(result)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON: {str(e)}"}
    
    print("========>>> result", result)

    try:
        for panel in result.get("panels", []):
            # Ensure consistent datasource format
            if "datasource" in panel:
                if isinstance(panel["datasource"], str):
                    panel["datasource"] = {
                        "type": "prometheus" if "prometheus" in panel["datasource"].lower() else "postgres",
                        "uid": panel["datasource"]
                    }
            
            # Add PostgreSQL time conversion
            if panel["datasource"]["type"] == "postgres" and panel["type"] == "timeseries":
                panel.setdefault("fieldConfig", {})
                panel["fieldConfig"]["defaults"] = {
                    "unit": "dateTimeAsIso",
                    "custom": {
                        "convertToDateType": True
                    }
                }

        return result
    except Exception as e:
        return {"error": f"Dashboard post-processing failed: {str(e)}"}


def get_query_metrics_labels(queries):
    prompt = f"""
    You are an expert in Prometheus metrics and observability queries.
    Your task is to analyze user queries and suggest relevant Prometheus metrics and labels.
        
    **Context:** You're analyzing observability queries to identify relevant Prometheus metrics and their labels. 
    The user wants to create Grafana dashboards from natural language questions.
    
    **Objective:** For each query, return:
    - Up to 5 potential metrics names
    - Up to 3 relevant labels for filtering/grouping
    - Never invent metrics - only suggest real Prometheus metrics
    
    **Style:** 
    - Structured and technical
    - Prometheus-centric terminology
    - Clear metric-label relationships
    
    **Tone:** 
    - Precise and analytical
    - Avoid assumptions or explanations
    
    **Audience:** 
    - DevOps engineers
    - SREs with Prometheus experience
    
    **Response Format:** Strict JSON
    {{
        "data": [
            {{
                "query": "original_user_query",
                "datasource": "selected_datasource_name",
                "metrics": ["metric1", "metric2", ...],  // max 5
                "related_metrics_labels": ["label1", "label2", "label3"]  // max 3
            }}
        ]
    }}

    **Input Queries:**
    {json.dumps([
        {"query": q[0], "datasource": q[1]} 
        for q in queries if q[0] and q[1]
    ], indent=2)}

    **Rules:**
    1. Metrics must exist in standard Prometheus ecosystem
    2. Labels should be actually present on the suggested metrics
    3. Prioritize metrics matching query intent over quantity
    4. Handle abbreviated/spoken-language queries professionally
    5. Never include example metrics - only real suggestions
    """

    result = groq_handler.groqrequest(prompt)

    if result.startswith("```"):
        result = result.strip("`").strip()
        if result.lower().startswith("json"):
            result = result[4:].strip()
    # Attempt to parse the JSON response
    try:
        result = json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON response from LLM"}
    
    # Validation
    if not result.get('data'):
        return {"error": "Invalid response format"}
        
    for entry in result['data']:
        if not all(key in entry for key in ['query','datasource','metrics','related_metrics_labels']):
            return {"error": "Missing required fields in LLM response"}
    
    return result

    
def generate_sql_query(query, datasource, metadata_context):
    prompt = f"""
        Context:
        You are an expert SQL generator for analytical systems. Your goal is to create valid, optimized SQL queries based strictly on the provided schema and metadata.

        Key Instructions:
        - Use ONLY the columns and tables exactly as defined in the schema: {metadata_context}
        - Column names and table names are case-sensitive. Always use double quotes (") around them.
        - Mandatory datasource UUID: {datasource}

        SQL Style:
        - ANSI-SQL compliant
        - Well-formatted and readable
        - Prefer CTEs for multi-step queries
        - Always use explicit JOINs
        - Never use SELECT *
        - Use database-specific functions only if mentioned

        Output Format:
        Return only valid JSON with the structure:
        {{
            "result": [
                {{
                    "mandatory_datasource_uuid": "value",
                    "userquery": "value",
                    "query": "Generated PromQL query"
                }}
            ]
        }}

        Important:
        - Quote all identifiers ("TABLE_NAME", "COLUMN_NAME") to respect case-sensitivity.
        - If a table or column does not exist, return:
        {{ "error": "Invalid table or column in schema" }}
        - If a JOIN lacks a condition, return:
        {{ "error": "Missing join condition" }}

        User Query Input:
        {query}

        Examples:

        - Simple Selection:
        [SELECT "CUSTOMERNAME", "COUNTRY", "SALES" FROM "sales_data";]

        - Aggregation:
        [SELECT "COUNTRY", SUM("SALES") AS "total_sales" FROM "sales_data" GROUP BY "COUNTRY" ORDER BY "total_sales" DESC;]

        - Window Function:
        [SELECT "YEAR_ID", "MONTH_ID", SUM("SALES") AS "monthly_sales" FROM "sales_data" GROUP BY "YEAR_ID", "MONTH_ID" ORDER BY "YEAR_ID" DESC, "MONTH_ID" ASC;]

    """
    result = groq_handler.groqrequest(prompt)

    return result
