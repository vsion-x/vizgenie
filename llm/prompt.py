# Function to generate PromQL query using OpenAI
import json
import os
from handlers.groq_handler import GroqHandler as groq

groq_handler = groq(os.getenv("GROQ_API_KEY", "").split(","))


def generate_promql_query(user_query_map):
    prompt = f"""
        Context: You are generating Grafana panel configurations for Prometheus metrics with appropriate visualizations.

        Objective: Create accurate PromQL queries and choose the BEST visualization type based on the metric characteristics.

        STRICT REQUIREMENTS:
        - Use ONLY the provided `similar_metrics` and `labels`
        - MUST use the provided `datasource` UID
        - Choose appropriate visualization type based on metric content

        VISUALIZATION SELECTION RULES for Prometheus:
        1. "timeseries" - For metrics with time-based patterns (rates, counters)
        2. "gauge" - For current value metrics (memory usage, temperature)
        3. "stat" - For single numeric values
        4. "piechart" - For categorical distributions (by instance, job, etc.)
        5. "bargauge" - For ranked comparisons

        Input array:  
        {json.dumps(user_query_map, indent=4)}

        OUTPUT FORMAT - MUST RETURN EXACTLY THIS JSON STRUCTURE:
        {{
            "panels": [
                {{
                    "type": "$APPROPRIATE_VIS_TYPE",
                    "title": "Panel based on {user_query_map[0]['original_query']}",
                    "datasource": {{
                        "type": "prometheus",
                        "uid": "{user_query_map[0]['datasource']}"
                    }},
                    "targets": [
                        {{
                            "expr": "$GENERATED_PROMQL_QUERY",
                            "refId": "A",
                            "format": "time_series",
                            "legendFormat": "{{{{label}}}}"
                        }}
                    ],
                    "gridPos": {{
                        "x": 0,
                        "y": 0,
                        "w": 12,
                        "h": 8
                    }},
                    "options": {{
                        "tooltip": {{
                            "mode": "single"
                        }}
                    }}
                }}
            ]
        }}

        VISUALIZATION EXAMPLES:

        1. TIME SERIES (CPU usage):
        {{
            "type": "timeseries",
            "title": "CPU Usage",
            "targets": [{{
                "expr": "rate(node_cpu_seconds_total[5m])",
                "format": "time_series",
                "legendFormat": "{{{{mode}}}}"
            }}]
        }}

        2. GAUGE (Memory usage):
        {{
            "type": "gauge",
            "title": "Memory Usage",
            "targets": [{{
                "expr": "node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100",
                "format": "time_series"
            }}]
        }}

        3. PIE CHART (CPU by mode):
        {{
            "type": "piechart",
            "title": "CPU Time by Mode",
            "targets": [{{
                "expr": "sum by (mode) (rate(node_cpu_seconds_total[5m]))",
                "format": "time_series"
            }}]
        }}

        CRITICAL: Return ONLY valid JSON. No additional text or explanations.
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

    return result



def generate_grafana_dashboard(panels):
    """
    Generate a Grafana 9.x dashboard JSON from panel configurations
    """
    if not panels:
        return {"error": "No panels provided for dashboard generation"}

    prompt = f"""
        Context: You are generating a complete Grafana 9.x dashboard JSON from pre-generated panel configurations.

        Objective: Create a properly structured Grafana dashboard with appropriate visualization options.

        Input Panels:
        {json.dumps(panels, indent=2)}

        STRICT REQUIREMENTS:
        1. MUST use EXACTLY the provided panels without modification
        2. MUST arrange panels in a logical grid layout
        3. MUST maintain all existing panel configurations
        4. ADD appropriate visualization options based on panel type

        VISUALIZATION OPTIONS BY TYPE:

        - "piechart": {{"pieType": "pie", "displayLabels": ["value", "name"]}}
        - "bargauge": {{"orientation": "horizontal", "displayMode": "basic"}}
        - "stat": {{"colorMode": "value", "graphMode": "none"}}
        - "timeseries": {{"legend": {{"showLegend": true}}, "tooltip": {{"mode": "single"}}}}
        - "gauge": {{"orientation": "horizontal", "showThresholdMarkers": true}}

        DASHBOARD STRUCTURE:
        {{
            "title": "AI-Generated Dashboard",
            "uid": "auto-dash-{hash(str(panels))}",
            "time": {{ "from": "now-6h", "to": "now" }},
            "panels": [/* EXACTLY THE PROVIDED PANELS WITH GRID POSITIONS */],
            "schemaVersion": 36
        }}

        GRID LAYOUT RULES:
        - Use 12-column grid system
        - Position panels vertically: panel[n].gridPos.y = panel[n-1].gridPos.y + panel[n-1].gridPos.h
        - Start with x=0, y=0 for first panel

        CRITICAL: Return ONLY valid JSON. No additional text or explanations.
    """

    result = groq_handler.groqrequest(prompt)
    
    if result.startswith("```"):
        result = result.strip("`").strip()
    if result.lower().startswith("json"):
        result = result[4:].strip()

    try:
        dashboard_json = json.loads(result)
        return dashboard_json
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON response: {str(e)}"}

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
        Context: You are generating Grafana panel configurations for SQL-based datasources with appropriate visualizations.

        Objective: Create optimized SQL queries and choose the BEST visualization type based on the query content.

        STRICT REQUIREMENTS:
        - Use ONLY the columns and tables exactly as defined in the schema: {metadata_context}
        - Column and table names are case-sensitive. ALWAYS use double quotes (") around identifiers.
        - MUST use the datasource UUID: {datasource}
        - MUST return complete Grafana panel configuration

        VISUALIZATION SELECTION RULES:
        Choose the MOST APPROPRIATE visualization type based on the query results:

        1. "piechart" - For categorical data with percentages (GROUP BY queries with 2-10 categories)
        2. "bargauge" - For single value comparisons or rankings (LIMIT 5-10 results)
        3. "stat" - For single numeric values (COUNT, SUM, AVG with no grouping)
        4. "timeseries" - For time-based data (must include time column)
        5. "table" - ONLY for raw data display or complex multi-column results

        SQL Guidelines:
        - ANSI-SQL compliant, well-formatted and readable
        - Prefer CTEs for multi-step queries
        - Always use explicit JOINs with proper conditions
        - Never use SELECT * - specify columns explicitly

        User Query: {query}

        OUTPUT FORMAT - MUST RETURN EXACTLY THIS JSON STRUCTURE:
        {{
            "panels": [
                {{
                    "type": "$APPROPRIATE_VIS_TYPE",  // piechart, bargauge, stat, timeseries, or table
                    "title": "Descriptive title based on user query",
                    "datasource": {{
                        "type": "postgres",
                        "uid": "{datasource}"
                    }},
                    "targets": [
                        {{
                            "rawSql": "$GENERATED_SQL_QUERY",
                            "refId": "A",
                            "format": "table",  // Always use "table" for SQL queries
                            "datasource": {{
                                "type": "postgres",
                                "uid": "{datasource}"
                            }}
                        }}
                    ],
                    "gridPos": {{
                        "x": 0,
                        "y": 0,
                        "w": 12,
                        "h": 8
                    }},
                    "options": {{
                        "showHeader": true,
                        "sortBy": [],
                        "pieType": "pie",  // For piechart
                        "orientation": "horizontal"  // For bargauge
                    }}
                }}
            ]
        }}

        VISUALIZATION EXAMPLES:

        1. PIE CHART (categorical distribution):
        {{
            "type": "piechart",
            "title": "Sales by Product Line",
            "targets": [{{
                "rawSql": "SELECT \"PRODUCTLINE\", SUM(\"SALES\") AS \"value\" FROM \"sales_db\" GROUP BY \"PRODUCTLINE\" ORDER BY \"value\" DESC;",
                "refId": "A",
                "format": "table"
            }}],
            "options": {{
                "pieType": "pie",
                "displayLabels": ["name", "value"]
            }}
        }}

        2. BAR GAUGE (ranked comparisons):
        {{
            "type": "bargauge", 
            "title": "Top 5 Customers by Sales",
            "targets": [{{
                "rawSql": "SELECT \"CUSTOMERNAME\", SUM(\"SALES\") AS \"value\" FROM \"sales_db\" GROUP BY \"CUSTOMERNAME\" ORDER BY \"value\" DESC LIMIT 5;",
                "refId": "A",
                "format": "table"
            }}],
            "options": {{
                "orientation": "horizontal",
                "displayMode": "basic"
            }}
        }}

        3. STAT (single value):
        {{
            "type": "stat",
            "title": "Total Sales",
            "targets": [{{
                "rawSql": "SELECT SUM(\"SALES\") AS \"value\" FROM \"sales_db\";",
                "refId": "A",
                "format": "table"
            }}],
            "options": {{
                "colorMode": "value",
                "graphMode": "none"
            }}
        }}

        4. TIME SERIES (time-based data):
        {{
            "type": "timeseries",
            "title": "Sales Over Time",
            "targets": [{{
                "rawSql": "SELECT \"DATE\" as \"time\", SUM(\"SALES\") AS \"value\" FROM \"sales_db\" GROUP BY \"DATE\" ORDER BY \"DATE\";",
                "refId": "A",
                "format": "table"
            }}],
            "options": {{
                "legend": {{
                    "showLegend": true
                }}
            }}
        }}

        CRITICAL: Return ONLY valid JSON. No additional text, explanations, or markdown formatting.
        Always use double quotes for SQL identifiers.
    """
    result = groq_handler.groqrequest(prompt)
    return result