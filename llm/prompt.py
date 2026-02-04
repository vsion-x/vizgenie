# llm/prompt.py
# prompt for llm

import json
import os
from handlers.groq_handler import GroqHandler as groq

groq_handler = groq(os.getenv("GROQ_API_KEY", "").split(","))


def generate_promql_query(user_query_map):
    prompt = f"""
        Context:You are generating PromQL queries to retrieve system and application metrics from Prometheus.

        Objective:Create accurate, optimized PromQL queries strictly using the provided input. Prioritize custom metrics and apply only the given labels.

        Style:Clear, minimal, and Prometheus-friendly.

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
    
    FIXED: 
    - No duplicate panels
    - Only creates panels for provided queries
    - No hallucinated PostgreSQL panels
    """
    
    # Extract unique datasource types
    datasource_types = list(set([
        qr.get('mandatory_datasource_uuid', '').split('-')[0] 
        for qr in query_responses.get('result', [])
    ]))
    
    prompt = f"""
    Create a Grafana 9.x dashboard JSON with EXACTLY {len(query_responses.get('result', []))} panels.
    
    CRITICAL RULES:
    1. Create EXACTLY ONE panel per query in the input - NO MORE, NO LESS
    2. DO NOT create panels for datasources not in the input
    3. DO NOT duplicate panels
    4. DO NOT add PostgreSQL panels unless explicitly provided in input
    
    Input configuration (CREATE ONE PANEL PER ITEM):
    {json.dumps(query_responses, indent=2)}
    
    Dashboard Structure:
    {{
        "title": "Generated Dashboard",
        "uid": "auto-dash-{hash(json.dumps(query_responses)) % 100000}",
        "schemaVersion": 36,
        "panels": [
            // EXACTLY {len(query_responses.get('result', []))} PANELS HERE
            // One panel per query in input
        ]
    }}
    
    Panel Template for Prometheus:
    {{
        "type": "timeseries",  // or "gauge", "stat" based on query type
        "title": "Panel Title from userquery",
        "gridPos": {{"x": 0, "y": 0, "w": 12, "h": 8}},
        "datasource": {{
            "type": "prometheus",
            "uid": "VALUE_FROM_mandatory_datasource_uuid"
        }},
        "targets": [
            {{
                "expr": "VALUE_FROM_query_field",
                "refId": "A",
                "legendFormat": "{{{{instance}}}}"
            }}
        ],
        "options": {{
            "legend": {{"displayMode": "list"}},
            "tooltip": {{"mode": "single"}}
        }}
    }}
    
    Panel Template for PostgreSQL:
    {{
        "type": "table",  // or "timeseries" if time-based
        "title": "Panel Title from userquery",
        "gridPos": {{"x": 0, "y": 0, "w": 12, "h": 8}},
        "datasource": {{
            "type": "postgres",
            "uid": "VALUE_FROM_mandatory_datasource_uuid"
        }},
        "targets": [
            {{
                "rawSql": "VALUE_FROM_query_field",
                "refId": "A",
                "format": "table"
            }}
        ]
    }}
    
    Panel Type Selection:
    - For rate(), increase(), delta() → "timeseries"
    - For sum(), count(), avg() without time → "stat"
    - For topk(), bottomk() → "bargauge"
    - For SQL SELECT → "table"
    - For SQL with time column → "timeseries"
    
    Grid Layout Rules:
    - First panel: {{"x": 0, "y": 0, "w": 12, "h": 8}}
    - Second panel: {{"x": 12, "y": 0, "w": 12, "h": 8}}
    - Third panel: {{"x": 0, "y": 8, "w": 12, "h": 8}}
    - Pattern: Alternate x between 0 and 12, increment y every 2 panels
    
    FINAL CHECK BEFORE RETURNING:
    - Count panels array length
    - Verify it equals {len(query_responses.get('result', []))}
    - Remove any extra panels
    - Do NOT add placeholder panels
    
    Output ONLY valid JSON. No markdown, no explanations.
    """

    result = groq_handler.groqrequest(prompt)

    # Clean response
    if result.startswith("```"):
        result = result.strip("`").strip()
    if result.lower().startswith("json"):
        result = result[4:].strip()

    try:
        dashboard = json.loads(result)
        
        # POST-PROCESSING: VALIDATE AND FIX
        
        input_queries = query_responses.get('result', [])
        panels = dashboard.get('panels', [])
        
        # Remove duplicate panels (same title and datasource)
        seen = set()
        unique_panels = []
        for panel in panels:
            key = (panel.get('title', ''), 
                   panel.get('datasource', {}).get('uid', ''))
            if key not in seen:
                seen.add(key)
                unique_panels.append(panel)
        
        # Limit to number of input queries
        if len(unique_panels) > len(input_queries):
            print(f"WARNING: LLM generated {len(unique_panels)} panels, expected {len(input_queries)}. Trimming extras.")
            unique_panels = unique_panels[:len(input_queries)]
        
        # Fix grid positions
        for idx, panel in enumerate(unique_panels):
            row = idx // 2
            col = idx % 2
            panel['gridPos'] = {
                "x": col * 12,
                "y": row * 8,
                "w": 12,
                "h": 8
            }
            
            # Ensure datasource format is correct
            if 'datasource' in panel and isinstance(panel['datasource'], str):
                # Fix string datasource to object
                ds_uid = panel['datasource']
                panel['datasource'] = {
                    "type": "prometheus" if "prometheus" in ds_uid.lower() else "postgres",
                    "uid": ds_uid
                }
        
        dashboard['panels'] = unique_panels
        
        # Add metadata
        dashboard['editable'] = True
        dashboard['fiscalYearStartMonth'] = 0
        dashboard['graphTooltip'] = 0
        dashboard['links'] = []
        dashboard['liveNow'] = False
        dashboard['timezone'] = "browser"
        
        print(f"✅ Dashboard generated with {len(unique_panels)} panels")
        return dashboard
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        return {"error": f"Failed to parse JSON: {str(e)}"}
    except Exception as e:
        print(f"❌ Dashboard post-processing failed: {e}")
        return {"error": f"Dashboard processing failed: {str(e)}"}


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
    
    try:
        result = json.loads(result)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON response from LLM"}
    
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
                    "query": "Generated SQL query"
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