"""
# graphs/rca_graph.py
RCA (Root Cause Analysis) Agent
Triggered by anomaly detection, performs deep analysis and provides actionable resolutions
"""

import logging
from typing import Dict, List, Any
from langgraph.graph import StateGraph, END
from schemas.state import AgentState
from llm.prompts import RCA_ANALYSIS_PROMPT
from llm.retry_handler import get_llm_handler
from datetime import datetime

logger = logging.getLogger(__name__)


async def gather_evidence_node(state: AgentState) -> AgentState:
    """
    Step 1: Gather evidence from multiple sources
    - Error pattern details from monitor
    - Error logs from Loki (if available)
    - Correlated metrics from Prometheus (if available)
    """
    from tools.loki_tools import query_loki_logs, extract_log_metrics
    from tools.prometheus_tools import execute_promql_query
    from tools.pattern_extractor import get_pattern_store
    
    anomaly = state.get('anomaly', {})
    
    # ✅ Get error pattern from context (passed from monitor)
    error_pattern_data = state.get('error_pattern', {})
    
    datasource_uid = state.get('datasource_uid', '')
    datasource_type = state.get('datasource_type', 'loki')
    time_window = '15m'
    
    # Get datasource URL
    available_datasources = state.get('available_datasources', [])
    
    evidence = {
        'error_logs': [],
        'metrics': {},
        'patterns': [],
        'error_pattern': error_pattern_data,  # ✅ Store error pattern
    }
    
    # 1. Try to fetch error logs from Loki (optional - don't fail if unavailable)
    loki_ds = next(
        (ds for ds in available_datasources if ds['type'] == 'loki'),
        None
    )
    
    if loki_ds:
        try:
            error_logs = await query_loki_logs(
                loki_url=loki_ds['url'],
                filter='{level="error"}',
                time_range=time_window,
                limit=50
            )
            
            if error_logs:
                evidence['error_logs'] = error_logs
                log_metrics = await extract_log_metrics(error_logs)
                evidence['log_metrics'] = log_metrics
                logger.info(f"Gathered {len(error_logs)} error logs")
        
        except Exception as e:
            logger.warning(f"Could not fetch error logs: {e}")
    
    # 2. Try to fetch Prometheus metrics (optional)
    prom_ds = next(
        (ds for ds in available_datasources if ds['type'] == 'prometheus'),
        None
    )
    
    if prom_ds:
        try:
            key_metrics = [
                'rate(process_cpu_seconds_total[5m])',
                'process_resident_memory_bytes',
            ]
            
            metrics_data = {}
            for metric_query in key_metrics:
                result = await execute_promql_query(
                    query=metric_query,
                    prometheus_url=prom_ds['url']
                )
                if result:
                    metrics_data[metric_query] = result
            
            if metrics_data:
                evidence['metrics'] = metrics_data
                logger.info(f"Gathered {len(metrics_data)} metric queries")
        
        except Exception as e:
            logger.warning(f"Could not fetch metrics: {e}")
    
    # Store evidence in state
    state['evidence'] = evidence
    state['loki_logs'] = evidence.get('error_logs', [])
    state['correlated_metrics'] = evidence.get('metrics', {})
    
    logger.info("Evidence gathering complete")
    
    return state


async def cross_correlate_node(state: AgentState) -> AgentState:
    """Step 2: Cross-correlate evidence"""
    evidence = state.get('evidence', {})
    
    correlations = {
        'temporal': [],
        'causal': [],
        'affected_components': []
    }
    
    # Extract affected components from error pattern
    error_pattern = evidence.get('error_pattern', {})
    affected_endpoints = error_pattern.get('affected_endpoints', [])
    affected_modules = error_pattern.get('affected_modules', [])
    
    correlations['affected_components'] = list(set(affected_endpoints + affected_modules))
    
    state['correlations'] = correlations
    
    logger.info(f"Cross-correlation found {len(correlations['affected_components'])} affected components")
    
    return state


async def llm_rca_analysis_node(state: AgentState) -> AgentState:
    """
    Step 3: Use LLM to perform root cause analysis with rich error context
    """
    anomaly = state.get('anomaly', {})
    evidence = state.get('evidence', {})
    correlations = state.get('correlations', {})
    
    # ✅ GET ERROR PATTERN DETAILS
    error_pattern = evidence.get('error_pattern', {})
    
    # Extract all error details
    error_type = error_pattern.get('error_type', 'Unknown')
    error_code = error_pattern.get('error_code', 'N/A')
    error_message = error_pattern.get('error_message', 'No message')
    stack_trace = error_pattern.get('stack_trace', 'No stack trace available')
    affected_endpoints = error_pattern.get('affected_endpoints', [])
    affected_modules = error_pattern.get('affected_modules', [])
    sample_logs_data = error_pattern.get('sample_logs', [])
    occurrence_count = error_pattern.get('occurrence_count', 1)
    
    # Build detailed error context for LLM
    error_context = f"""
ERROR TYPE: {error_type}
ERROR CODE: {error_code}
OCCURRENCES: {occurrence_count} times

ERROR MESSAGE:
{error_message}

STACK TRACE:
{stack_trace}

AFFECTED ENDPOINTS:
{', '.join(affected_endpoints[:5]) if affected_endpoints else 'None identified'}

AFFECTED MODULES:
{', '.join(affected_modules[:5]) if affected_modules else 'None identified'}

SAMPLE LOGS (showing first 2):
"""
    
    # Add sample logs
    for idx, log in enumerate(sample_logs_data[:2], 1):
        log_text = log if isinstance(log, str) else str(log)
        error_context += f"\n--- Sample {idx} ---\n{log_text[:500]}\n"
    
    # Build full prompt with rich context
    prompt = RCA_ANALYSIS_PROMPT.format(
        trigger_type=error_type,
        severity=anomaly.get('severity', 'medium'),
        trigger_details=error_context,
        time_window='15 minutes',
        error_logs=error_context,
        metrics_data="System metrics normal (if available)",
        pattern_analysis=f"Error pattern detected {occurrence_count} times",
        affected_components=', '.join(affected_modules[:5]) if affected_modules else 'Unknown'
    )
    
    try:
        llm_handler = get_llm_handler()
        rca_result = await llm_handler.call_llm(
            prompt=prompt,
            temperature=0.1,
            max_tokens=3000,
            response_format="json"
        )
        
        # Store RCA results
        state['root_cause_analysis'] = rca_result.get('root_cause', {}).get('description', '')
        state['resolution_suggestions'] = rca_result.get('resolution_suggestions', [])
        state['mttd'] = rca_result.get('mttd_analysis', {}).get('detection_time', 0)
        state['mttr'] = rca_result.get('mttr_estimate', {}).get('estimated_resolution_time', 0)
        state['rca_result'] = rca_result
        
        logger.info(f"RCA complete: {rca_result.get('root_cause', {}).get('category', 'unknown')}")
    
    except Exception as e:
        logger.error(f"LLM RCA analysis failed: {e}")
        # ✅ FIXED: Call fallback with correct signature
        _fallback_rca_analysis(state)
    
    return state


def _fallback_rca_analysis(state: AgentState):
    """
    Fallback RCA using heuristics when LLM fails
    ✅ FIXED: Single parameter (state only)
    """
    evidence = state.get('evidence', {})
    error_pattern = evidence.get('error_pattern', {})
    
    error_type = error_pattern.get('error_type', 'Unknown')
    error_message = error_pattern.get('error_message', '')
    stack_trace = error_pattern.get('stack_trace', '')
    affected_modules = error_pattern.get('affected_modules', [])
    affected_endpoints = error_pattern.get('affected_endpoints', [])
    
    # Determine category and provide specific guidance
    error_type_lower = error_type.lower()
    
    if 'type' in error_type_lower:
        category = 'code'
        component = affected_modules[0] if affected_modules else '/app/main.py'
        description = f"Type mismatch error in {component}. {error_message[:200]}"
        implementation = f"""STEP-BY-STEP FIX:

1. **Open the file**: {component}
   - Look at the stack trace to find exact line number
   
2. **Locate the error**: 
   - Find where string + integer concatenation happens
   - Or find where incompatible types are used together

3. **Fix the type error**:
   - Convert integer to string: str(number)
   - Or convert string to integer: int(string)
   - Example: result = "string" + str(123)

4. **Add validation**:
   if isinstance(value, str):
       # handle string
   elif isinstance(value, int):
       # convert or handle int

5. **Test and deploy**
   - Add unit test for type validation
   - Deploy fix to production"""

    elif 'null' in error_type_lower or 'none' in error_type_lower:
        category = 'code'
        component = affected_modules[0] if affected_modules else '/app/main.py'
        # Extract line number from stack trace
        line_match = re.search(r'line (\d+)', stack_trace)
        line_num = line_match.group(1) if line_match else 'XXX'
        
        description = f"Null/None reference in {component} at line {line_num}. Attempting to call method on None object."
        implementation = f"""STEP-BY-STEP FIX:

1. **Open file**: {component}
   - Go to line {line_num}

2. **Find the null reference**:
   - Look for: obj.some_method()
   - Object 'obj' is None/null

3. **Add null check BEFORE accessing**:
   if obj is not None:
       result = obj.some_method()
   else:
       logger.warning("Object is None, using default")
       result = default_value

4. **Find WHY object is None**:
   - Check where obj is initialized
   - Check function return values
   - Add logging to trace None source

5. **Prevent future occurrences**:
   - Initialize objects properly
   - Add validation at function start
   - Return empty object instead of None

6. **Test thoroughly before deploy**"""

    elif 'division' in error_type_lower or 'zero' in error_type_lower:
        category = 'code'
        component = affected_modules[0] if affected_modules else '/app/main.py'
        line_match = re.search(r'line (\d+)', stack_trace)
        line_num = line_match.group(1) if line_match else 'XXX'
        
        description = f"Division by zero in {component} at line {line_num}."
        implementation = f"""STEP-BY-STEP FIX:

1. **Open file**: {component}
   - Go to line {line_num}

2. **Find division operation**:
   - Look for: result = x / y
   - Variable 'y' is 0

3. **Add zero check BEFORE division**:
   if denominator == 0:
       logger.error(f"Zero denominator for {{context}}")
       return 0  # or raise exception
   result = numerator / denominator

4. **Find source of zero**:
   - Check where denominator comes from
   - Add input validation
   - Log cases where zero appears

5. **Add unit tests**:
   def test_division_by_zero():
       result = calculate(10, 0)
       assert result == 0  # or raises error

6. **Deploy with monitoring**"""

    elif 'index' in error_type_lower or 'bound' in error_type_lower:
        category = 'code'
        component = affected_modules[0] if affected_modules else 'Unknown module'
        description = f"Array index out of bounds in {component}."
        implementation = f"""STEP-BY-STEP FIX:

1. **Open file containing**: {component}
2. **Find array/list access**: items[index]
3. **Add bounds check**:
   if 0 <= index < len(items):
       value = items[index]
   else:
       logger.error(f"Index {{index}} out of bounds")
       value = default
4. **Or use .get() for dicts**: items.get(key, default)"""

    elif 'connection' in error_type_lower or 'dns' in error_type_lower or 'timeout' in error_type_lower:
        category = 'infrastructure'
        component = 'External service or network'
        description = f"Network/connection failure: {error_message[:200]}"
        implementation = f"""STEP-BY-STEP FIX:

1. **Check service health**:
   - Verify external API is up
   - Check network connectivity
   - Test DNS resolution: nslookup api.example.com

2. **Increase timeout if needed**:
   timeout = 30  # increase from 10 to 30 seconds

3. **Add retry logic**:
   for attempt in range(3):
       try:
           response = call_api()
           break
       except Timeout:
           time.sleep(2 ** attempt)  # exponential backoff

4. **Add circuit breaker**:
   - Fail fast if service is down
   - Don't overwhelm failing service

5. **Contact**: Network Team, External API Provider"""

    else:
        category = 'code'
        component = affected_modules[0] if affected_modules else 'Unknown'
        description = f"{error_type}: {error_message[:200]}"
        implementation = f"""Review stack trace and fix accordingly:

Stack Trace:
{stack_trace}

1. Find exact line causing error
2. Review recent code changes
3. Add proper error handling
4. Test fix thoroughly"""

    # Build resolution suggestion
    state['rca_result'] = {
        'root_cause': {
            'category': category,
            'component': component,
            'description': description,
            'confidence_score': 0.8,
            'contact_team': f'{category.capitalize()} Team'
        },
        'resolution_suggestions': [
            {
                'type': category,
                'priority': 'high',
                'suggestion': f'Fix {error_type} in {component}',
                'implementation': implementation,
                'estimated_time': '15-30 minutes',
                'risk_level': 'low',
                'rollback_plan': 'Revert to previous working commit',
                'contact': f'{category.capitalize()} Team'
            }
        ],
        'evidence': [
            f"Error: {error_message}",
            f"Stack trace shows error in {component}",
            f"Occurred {error_pattern.get('occurrence_count', 1)} times"
        ],
        'impact_analysis': {
            'affected_users': 'Unknown',
            'affected_requests': f"{error_pattern.get('occurrence_count', 1)} occurrences",
            'business_impact': 'Service degradation'
        },
        'preventive_measures': [
            f'Add input validation in {component}',
            f'Add unit tests for {error_type} scenarios',
            'Add monitoring alerts for this error type',
            'Review code for similar patterns'
        ],
        'mttd_analysis': {
            'detection_time': 0,
            'detection_method': 'Automated monitoring'
        },
        'mttr_estimate': {
            'estimated_resolution_time': 1800,  # 30 minutes
            'assumptions': ['Fix requires code change', 'No dependencies']
        }
    }
    
    state['root_cause_analysis'] = description
    state['resolution_suggestions'] = state['rca_result']['resolution_suggestions']
    state['fallback_mode'] = True
    
    logger.info("Fallback RCA complete with detailed guidance")


async def generate_incident_dashboard_node(state: AgentState) -> AgentState:
    """Step 4: Generate incident dashboard"""
    from tools.dashboard_tools import DashboardBuilder
    
    anomaly = state.get("anomaly", {})
    
    builder = DashboardBuilder()
    panels = []
    
    available_datasources = state.get("available_datasources", [])
    
    # Try to add Loki panel
    loki_ds = next((ds for ds in available_datasources if ds["type"] == "loki"), None)
    if loki_ds:
        panels.append(builder.create_panel(
            panel_id=1,
            title="Error Logs Timeline",
            datasource_uid=loki_ds["uid"],
            datasource_type="loki",
            query='rate({level="error"}[1m])',
            query_type="logql",
            x=0, y=0, width=24, height=8,
        ))
    
    # Try to add Prometheus panels
    prom_ds = next((ds for ds in available_datasources if ds["type"] == "prometheus"), None)
    if prom_ds:
        panels.append(builder.create_panel(
            panel_id=2,
            title="CPU Usage",
            datasource_uid=prom_ds["uid"],
            datasource_type="prometheus",
            query='avg(rate(process_cpu_seconds_total[5m]))',
            query_type="promql",
            x=0, y=8, width=12, height=8,
        ))
    
    if panels:
        dashboard = builder.create_dashboard(
            uid=f"incident-{int(datetime.now().timestamp())}",
            title=f"Incident: {anomaly.get('anomaly_type', 'Unknown')}",
            panels=panels,
            tags=["incident", "rca"],
        )
        state["dashboard_json"] = dashboard
        logger.info("Incident dashboard generated")
    else:
        logger.warning("No panels generated for incident dashboard")
    
    return state


async def format_rca_report_node(state: AgentState) -> AgentState:
    """Step 5: Format RCA report"""
    
    anomaly = state.get("anomaly", {})
    rca_result = state.get("rca_result", {})
    
    # Build structured report
    report = {
        'incident_id': f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'timestamp': anomaly.get("timestamp", datetime.now()).isoformat() if isinstance(anomaly.get("timestamp"), datetime) else str(anomaly.get("timestamp", datetime.now())),
        'severity': anomaly.get("severity", "unknown"),
        'anomaly_type': anomaly.get("anomaly_type", "unknown"),
        'trigger_details': anomaly.get("details", {}),
        'root_cause': rca_result.get("root_cause", {}),
        'evidence': rca_result.get("evidence", []),
        'impact_analysis': rca_result.get("impact_analysis", {}),
        'resolution_suggestions': rca_result.get("resolution_suggestions", []),
        'preventive_measures': rca_result.get("preventive_measures", []),
        'mttd': 0,
        'mttr': 1800,
        'dashboard_url': state.get("dashboard_url", ""),
    }
    
    state['rca_report'] = "RCA report generated"
    state['rca_report_structured'] = report
    
    logger.info("RCA report formatted")
    
    return state


def create_rca_graph():
    """Create RCA agent graph"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("gather_evidence", gather_evidence_node)
    workflow.add_node("cross_correlate", cross_correlate_node)
    workflow.add_node("llm_rca_analysis", llm_rca_analysis_node)
    workflow.add_node("generate_incident_dashboard", generate_incident_dashboard_node)
    workflow.add_node("format_rca_report", format_rca_report_node)
    
    from nodes.dashboard_node import dashboard_creation_node
    workflow.add_node("deploy_dashboard", dashboard_creation_node)
    
    workflow.set_entry_point("gather_evidence")
    workflow.add_edge("gather_evidence", "cross_correlate")
    workflow.add_edge("cross_correlate", "llm_rca_analysis")
    workflow.add_edge("llm_rca_analysis", "generate_incident_dashboard")
    workflow.add_edge("generate_incident_dashboard", "deploy_dashboard")
    workflow.add_edge("deploy_dashboard", "format_rca_report")
    workflow.add_edge("format_rca_report", END)
    
    return workflow.compile()


async def invoke_rca_agent(context: Dict) -> Dict:
    """Helper function to invoke RCA agent from background monitor"""
    from schemas.state import AgentState
    
    state: AgentState = {
        'intent': 'rca',
        'anomaly': context.get('anomaly'),
        'available_datasources': context.get('available_datasources', []),
        'datasource_uid': context.get('datasource_uid', ''),
        'datasource_type': context.get('datasource_type', ''),
        'error_pattern': context.get('error_pattern', {}),  # ✅ Pass error pattern
        'log_patterns': [],
        'categorized_data': {},
        'user_query': f"RCA for {context.get('anomaly', {}).get('anomaly_type', 'unknown')} anomaly",
        'llm_retry_count': 0,
        'fallback_mode': False,
        'conversation_history': [],
        'investigation_steps': [],
        'tools_used': [],
        'grafana_url': context.get('grafana_url', ''),
        'grafana_api_key': context.get('grafana_api_key', ''),
    }
    
    graph = create_rca_graph()
    result = await graph.ainvoke(state)
    
    return {
        'rca_report': result.get('rca_report', ''),
        'rca_report_structured': result.get('rca_report_structured', {}),
        'dashboard_url': result.get('dashboard_url', ''),
        'resolution_suggestions': result.get('resolution_suggestions', []),
        'resolved': False
    }