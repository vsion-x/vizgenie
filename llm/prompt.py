# Function to generate PromQL query using OpenAI
import json
from client import groq


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

    result = groq.groqrequest(prompt)

    if result.get("error"):
        return {"error": "Failed to generate PromQL query from Groq API"}

    return result


def generate_grafana_dashboard(promql_response):
    """
    Generate a Grafana dashboard JSON from the PromQL responses with proper visualization types.
    """
    prompt = f"""
    Create Grafana 9.x dashboard JSON for the following PromQL query configuration:
    {json.dumps(promql_response, indent=2)}

    Requirements:
    1. Use this base structure:
    {{
        "title": "Generated Dashboard",
        "uid": "auto-dash-{hash(json.dumps(promql_response))}",
        "panels": [
            {{
                "type": "timeseries|piechart|table|gauge|bargauge|stat",
                "title": "Panel Title",
                "datasource": {{ 
                    "type": "prometheus",
                    "uid": "$datasource_uuid" 
                }},
                "targets": [
                    {{
                        "expr": "$query",
                        "refId": "A",
                        "format": "time_series|table",
                        "legendFormat": "{{{{label}}}}"
                    }}
                ],
                "options": {{
                    "mode": "lines|bars|points",
                    "pieType": "pie|donut",
                    "orientation": "auto|horizontal|vertical",
                    "reduceOptions": {{
                        "calcs": ["lastNotNull"],
                        "fields": "",
                        "values": false
                    }}
                }},
                "fieldConfig": {{
                    "defaults": {{
                        "unit": "short",
                        "thresholds": {{
                            "mode": "absolute",
                            "steps": [
                                {{ "color": "green", "value": null }},
                                {{ "color": "red", "value": 80 }}
                            ]
                        }}
                    }},
                    "overrides": []
                }},
                "gridPos": {{ "x": 0, "y": 0, "w": 12, "h": 8 }}
            }}
        ],
        "time": {{ "from": "now-1h", "to": "now" }},
        "schemaVersion": 36,
        "version": 1
    }}

    2. Visualization Selection Rules:
    - Timeseries (line/bars): For metrics with timestamped values
      (e.g., rate(node_cpu_seconds_total[5m]))
      Options: Set "mode" to "bars" for bar charts
      
    - Piechart: For aggregated categorical distributions
      (e.g., sum by (job)(rate(http_requests_total[5m])))
      Format: MUST use "table"
      
    - Gauge: For single numeric values with thresholds
      (e.g., avg(system_memory_used_percent))
      Format: "time_series" with last value
      
    - Bargauge: For comparative horizontal/vertical bars
      (e.g., topk(5, container_memory_usage_bytes))
      
    - Stat: Simple big number display
      (e.g., count(http_requests_total))

    3. Strict Rules:
    - Use EXACT panel types: "timeseries", "piechart", "table", "gauge", "bargauge", "stat"
    - Match formats: "time_series" for metrics, "table" for aggregations
    - Set "legendFormat" using labels from the PromQL result
    - Include gridPos with sequential positioning (x: 0->24, y: increments of 8)
    - For gauges: Include threshold configuration in fieldConfig
    - For piecharts: Set "pieType" to "donut" and format to "table"

    4. Example Configurations:
    - Pie Chart Example:
      {{
        "type": "piechart",
        "options": {{ "pieType": "donut" }},
        "targets": [{{
            "expr": "sum by (env)(rate(http_requests_total[5m]))",
            "format": "table",
            "refId": "A"
        }}]
      }}

    - Bar Gauge Example:
      {{
        "type": "bargauge",
        "options": {{ "orientation": "horizontal" }},
        "targets": [{{
            "expr": "topk(3, container_memory_usage_bytes)",
            "format": "time_series",
            "refId": "A"
        }}]
      }}

    - Time Series Bars:
      {{
        "type": "timeseries",
        "options": {{ "mode": "bars" }},
        "targets": [{{
            "expr": "rate(http_requests_total[5m]",
            "format": "time_series",
            "refId": "A"
        }}]
      }}

    Output ONLY valid JSON. No markdown or extra text.
    """

    result = groq.groqrequest(prompt)

    if result.get("error"):
        return {"error": "Failed to generate Grafana dashboard from Groq API"}
    
    # Post-process JSON to ensure Grafana compatibility
    try:
        # Ensure required fields exist
        result.setdefault("tags", ["generated"])
        result.setdefault("refresh", "30s")
        
        # Normalize panel positions
        for i, panel in enumerate(result.get("panels", [])):
            panel["gridPos"] = {
                "x": (i % 2) * 12,
                "y": (i // 2) * 8,
                "w": 12,
                "h": 8
            }
            
            # Ensure consistent datasource format
            if "datasource" in panel:
                if isinstance(panel["datasource"], str):
                    panel["datasource"] = {
                        "type": "prometheus",
                        "uid": panel["datasource"]
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

    result = groq.groqrequest(prompt)
    
    # Validation
    if not result.get('data'):
        return {"error": "Invalid response format"}
        
    for entry in result['data']:
        if not all(key in entry for key in ['query','datasource','metrics','related_metrics_labels']):
            return {"error": "Missing required fields in LLM response"}
    
    return result