<div align="center">
  <img src="https://raw.githubusercontent.com/vsion-x/vizgenie/main/assets/vizgenielogo.svg" alt="VizGenie Logo" width="300"/>
  
  [![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
  [![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
  [![LangGraph](https://img.shields.io/badge/LangGraph-0.0.50-purple.svg)](https://github.com/langchain-ai/langgraph)
  
  <p>
    <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
      <img src="https://img.shields.io/badge/🎥-Watch_Demo-FF4B4B?style=for-the-badge" alt="Watch Demo">
    </a>
    <a href="https://console.groq.com/">
      <img src="https://img.shields.io/badge/🔑-Get_API_Key-black?style=for-the-badge" alt="Get API Key">
    </a>
  </p>
</div>

# VizGenie: AI-Powered Dashboard Generation

VizGenie is an **intelligent agentic AI system** that transforms natural language queries into production-ready Grafana dashboards. Built with **LangGraph**, it orchestrates multiple AI agents to extract metrics, generate queries (PromQL/SQL), create visualizations, and deploy dashboards automatically.

## 🌟 What's New in v2.0 - Agentic Architecture

<div align="center">
  <table>
    <tr>
      <td align="center" width="25%">
        <div style="font-size: 48px;">🤖</div>
        <h3>LangGraph Agents</h3>
        <p>Multi-agent orchestration with state management</p>
        <img src="https://img.shields.io/badge/NEW-Feature-success">
      </td>
      <td align="center" width="25%">
        <div style="font-size: 48px;">🔄</div>
        <h3>Auto-Retry Logic</h3>
        <p>Intelligent error recovery and query validation</p>
        <img src="https://img.shields.io/badge/NEW-Feature-success">
      </td>
      <td align="center" width="25%">
        <div style="font-size: 48px;">📊</div>
        <h3>Real-time Progress</h3>
        <p>Live workflow tracking with execution logs</p>
        <img src="https://img.shields.io/badge/NEW-Feature-success">
      </td>
      <td align="center" width="25%">
        <div style="font-size: 48px;">🎯</div>
        <h3>Smart Routing</h3>
        <p>Conditional node execution based on results</p>
        <img src="https://img.shields.io/badge/NEW-Feature-success">
      </td>
    </tr>
  </table>
</div>

## ✨ Core Features

<div align="center">
  <table>
    <tr>
      <td align="center">
        <div style="font-size: 48px;">💬</div>
        <h3>Natural Language to Visualization</h3>
        <p>Describe metrics in plain English - AI handles the rest</p>
        <img src="https://img.shields.io/badge/✅-Powered_by_Groq-success">
      </td>
      <td align="center">
        <div style="font-size: 48px;">🧠</div>
        <h3>Vector-Enhanced Search</h3>
        <p>ChromaDB semantic search for metric discovery</p>
        <img src="https://img.shields.io/badge/✅-ChromaDB-success">
      </td>
    </tr>
    <tr>
      <td align="center">
        <div style="font-size: 48px;">🔌</div>
        <h3>Multi-Data Source Support</h3>
        <p>Prometheus & PostgreSQL with unified interface</p>
        <img src="https://img.shields.io/badge/✅-Dual_Support-success">
      </td>
      <td align="center">
        <div style="font-size: 48px;">📈</div>
        <h3>Auto Dashboard Deployment</h3>
        <p>One-click deploy to Grafana with validation</p>
        <img src="https://img.shields.io/badge/✅-Grafana_9.x-success">
      </td>
    </tr>
  </table>
</div>

## 🏗️ Agentic Architecture

VizGenie uses a **deterministic LangGraph workflow** with specialized agents for each step:

```mermaid
graph TD
    A[User Query] --> B[Initialize Agent]
    B --> C[Intent Extraction Agent]
    C --> D[Metrics Extraction Agent]
    D --> E[Vector Search Agent]
    E --> F[Metrics Validation Agent]
    F --> G{Datasource Type?}
    G -->|Prometheus| H[PromQL Generation Agent]
    G -->|PostgreSQL| I[SQL Generation Agent]
    H --> J[Query Validation Agent]
    I --> J
    J -->|Invalid & Retry < 3| H
    J -->|Valid| K[Dashboard Generation Agent]
    K --> L[Deployment Agent]
    L --> M[Grafana Dashboard]
    
    style B fill:#e1f5ff
    style C fill:#e1f5ff
    style D fill:#fff3e0
    style E fill:#fff3e0
    style F fill:#e8f5e9
    style H fill:#f3e5f5
    style I fill:#f3e5f5
    style J fill:#fce4ec
    style K fill:#e0f2f1
    style L fill:#e0f2f1
```

### Agent Workflow Stages

| Stage | Agent | Function | Tools Used |
|-------|-------|----------|------------|
| 🎬 **Initialize** | Initialization Agent | Load session history, setup state | Context Manager |
| 🧠 **Intent Extraction** | Intent Agent | Classify query type, map datasources | Pattern Matching |
| 📊 **Metrics Extraction** | Metrics Agent | Extract metric names & labels via LLM | extract_metrics_tool + Groq LLM |
| 🔍 **Vector Search** | Search Agent | Find similar metrics using embeddings | vector_search_tool + ChromaDB |
| ✅ **Validation** | Validation Agent | Verify metrics exist in datasource | fetch_labels_tool + Prometheus API |
| ⚡ **Query Generation** | Query Agent | Generate PromQL or SQL via LLM | generate_promql_tool / generate_sql_tool |
| 🔎 **Query Validation** | Validator Agent | Syntax validation with auto-retry | validate_query_tool |
| 🎨 **Dashboard Creation** | Dashboard Agent | Generate Grafana JSON via LLM | generate_dashboard_tool |
| 🚀 **Deployment** | Deploy Agent | POST to Grafana API | deploy_dashboard_tool + Grafana API |

## 🔧 Architecture Components

### State Management
```python
VizGenieState (TypedDict):
  - user_queries: List[QueryContext]
  - current_stage: ProcessingStage
  - metrics_contexts: List[MetricsContext]
  - generated_queries: List[GeneratedQuery]
  - dashboard_spec: DashboardSpec
  - errors: List[ErrorContext]
  - execution_log: List[LogEntry]
```

### Tools & Handlers

| Category | Component | Purpose |
|----------|-----------|---------|
| **Tools** | extract_metrics_tool | LLM-based metric extraction |
| | vector_search_tool | Semantic similarity search |
| | fetch_labels_tool | Get actual metric labels |
| | generate_promql_tool | PromQL query generation |
| | generate_sql_tool | SQL query generation |
| | generate_dashboard_tool | Dashboard JSON creation |
| | deploy_dashboard_tool | Grafana deployment |
| **Handlers** | PrometheusHandler | Prometheus API interaction |
| | PostgresHandler | PostgreSQL queries & metadata |
| | VectorDBHandler | ChromaDB operations |
| | GrafanaHandler | Dashboard CRUD operations |

## 📊 How It Works

### Example: "Show CPU utilization"

```
1. User Input
   └─> "Show CPU utilization" + Prometheus datasource

2. Initialize Agent
   └─> Loads session history, creates request context

3. Intent Extraction Agent
   └─> Classifies as: "System metrics visualization"

4. Metrics Extraction Agent (LLM Call #1)
   └─> Extracts: ["node_cpu_seconds_total", "container_cpu_usage_seconds_total"]
   └─> Labels: ["instance", "cpu", "mode"]

5. Vector Search Agent
   └─> ChromaDB finds similar: ["node_cpu_seconds_total", "process_cpu_seconds_total"]

6. Validation Agent
   └─> Prometheus API confirms metrics exist
   └─> Fetches actual labels: {"node_cpu_seconds_total": ["instance", "cpu", "mode"]}

7. PromQL Generation Agent (LLM Call #2)
   └─> Generates: "rate(node_cpu_seconds_total[5m]) * 100"

8. Query Validation Agent
   └─> Validates syntax ✅

9. Dashboard Generation Agent (LLM Call #3)
   └─> Creates Grafana JSON with timeseries panel

10. Deployment Agent
    └─> POSTs to Grafana API
    └─> Returns: http://grafana/d/abc123/cpu-utilization

Result: ✅ Dashboard deployed in ~3-5 seconds
```

## 🎥 Demo

<div align="center">
  <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
    <img src="https://cdn.loom.com/sessions/thumbnails/d4ebd415de14413faf23a928a728ccf9-101b13f5c63868b2-full-play.gif" alt="VizGenie Demo" style="max-width: 90%; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.1);">
  </a>
  <p>
    <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
      <img src="https://img.shields.io/badge/▶-Watch_Full_Demo-FF4B4B?style=for-the-badge" alt="Watch Full Demo">
    </a>
  </p>
</div>

## 🚀 Getting Started

<div align="center">
  <a href="#-prerequisites">
    <img src="https://img.shields.io/badge/1.-Prerequisites-4CAF50?style=for-the-badge&logo=check-circle&logoColor=white" alt="Prerequisites">
  </a>
  <span>→</span>
  <a href="#%EF%B8%8F-installation">
    <img src="https://img.shields.io/badge/2.-Installation-2196F3?style=for-the-badge&logo=download&logoColor=white" alt="Installation">
  </a>
  <span>→</span>
  <a href="#%EF%B8%8F-configuration">
    <img src="https://img.shields.io/badge/3.-Configuration-FF9800?style=for-the-badge&logo=cog&logoColor=white" alt="Configuration">
  </a>
  <span>→</span>
  <a href="#-deployment">
    <img src="https://img.shields.io/badge/4.-Deployment-9C27B0?style=for-the-badge&logo=rocket&logoColor=white" alt="Deployment">
  </a>
</div>

### 📋 Prerequisites

| Component | Required | How to Get |
|-----------|----------|------------|
| 🔑 **Groq API Key** | ✅ Yes | [Get free key here](https://console.groq.com/) |
| 📊 **Grafana Instance** | ✅ Yes | Included in Docker setup |
| 📈 **Prometheus** | ✅ Yes | Included in Docker setup |
| 🐘 **PostgreSQL** | ⚪ Optional | Included in Docker setup |
| 🐳 **Docker & Docker Compose** | ⚪ Optional | [Install Docker](https://docs.docker.com/get-docker/) |

### 💾 Installation

#### Option 1: Clone Repository
```bash
git clone https://github.com/vsion-x/vizgenie.git
cd vizgenie
```

#### Option 2: Download ZIP
Download and extract the latest release from GitHub.

### ⚙️ Configuration

#### 1. Environment Setup

Create a `.env` file in the project root:

```env
# Required: Groq API Key
GROQ_API_KEY=your_groq_api_key_here

# Optional: Multiple keys for failover (comma-separated)
# GROQ_API_KEY=key1,key2,key3
```

> **ℹ️ Note:** This is the only required configuration file. All other settings are managed through the Streamlit UI.

#### 2. Streamlit UI Configuration

When you first launch VizGenie, configure these settings in the UI:

| Service | Configuration | Example Value |
|---------|---------------|---------------|
| 🔌 **Grafana** | • URL<br>• API Key (with `dashboards:write` permission) | `http://localhost:3000`<br>`glsa_xxxxx...` |
| 📈 **Prometheus** | • URL | `http://localhost:9090` |
| 🐘 **PostgreSQL** | • Connection String | `postgresql://postgres:admin@localhost:5433/sales_db` |

### 🚀 Deployment

#### 🐳 Docker Deployment (Recommended)

This method sets up the complete stack:
- VizGenie application
- Grafana
- Prometheus + Node Exporter
- PostgreSQL with sample data
- ChromaDB

```bash
# Navigate to project directory
cd vizgenie

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f vizgenie
```

**Services will be available at:**
- 🎨 VizGenie UI: http://localhost:8501
- 📊 Grafana: http://localhost:3000 (admin/admin)
- 📈 Prometheus: http://localhost:9090
- 🐘 PostgreSQL: localhost:5433

#### 🐍 Local Python Setup

For development or custom setups:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run main.py

# Or with Python module
python3 -m streamlit run main.py
```

**Access at:** http://localhost:8501

### 🔍 Sample Database

VizGenie includes a sample sales database for testing:

**Default PostgreSQL Credentials:**
- Database: `sales_db`
- User: `postgres`
- Password: `admin`
- Port: `5433`
- Connection: `postgresql://postgres:admin@localhost:5433/sales_db`

**Sample Queries to Try:**
- "Show top 10 customers by sales revenue"
- "Display monthly sales trend for last year"
- "Which product line generates most revenue?"
- "Show sales by country on a map"

## 📖 Usage Guide

### Step 1: Configure Connections
1. Open VizGenie at http://localhost:8501
2. Configure Grafana, Prometheus, and PostgreSQL connections
3. Click "Test" buttons to verify connectivity

### Step 2: Refresh Metrics (First Time)
Click "🔄 Refresh All Metrics" to populate the vector database with available Prometheus metrics.

### Step 3: Create Dashboard
1. Enter your query in natural language:
   - "Show CPU utilization for all nodes"
   - "Display memory usage trend for last hour"
   - "Top 5 customers by sales"
   
2. Select datasource (Prometheus or PostgreSQL)

3. Click "✨ Generate Dashboard with Agents"

4. Watch the real-time progress as agents work:
   ```
   ✅ Analyzing query... (120ms) 🎯 Cache HIT
   ✅ Searching metrics... (450ms)
   ✅ Validating metrics... (230ms)
   🔄 Generating PromQL... (in progress)
   ⏳ Creating dashboard...
   ⏳ Deploying...
   ```

5. View your dashboard in Grafana!

## 🏗️ Project Structure

```
vizgenie/
├── main.py                      # Streamlit UI entry point
├── agents/
│   ├── workflow.py              # LangGraph workflow orchestrator
│   ├── vizgenie_agents.py       # Agent node implementations
│   └── __init__.py
├── tools/
│   ├── vizgenie_tools.py        # Tool definitions (LangChain Tools)
│   └── __init__.py
├── state/
│   ├── graph_state.py           # State type definitions
│   └── __init__.py
├── handlers/
│   ├── prometheus_handler.py    # Prometheus API handler
│   ├── postgres_handler.py      # PostgreSQL handler
│   ├── grafana_handler.py       # Grafana API handler
│   ├── vectordb_handler.py      # ChromaDB handler
│   ├── groq_handler.py          # Groq LLM handler
│   └── __init__.py
├── llm/
│   ├── prompt.py                # LLM prompts for each task
│   └── __init__.py
├── metadata/
│   └── metadata.yaml            # PostgreSQL schema metadata
├── chroma_db/                   # ChromaDB storage (auto-created)
├── docker-compose.yml           # Full stack deployment
├── requirements.txt             # Python dependencies
└── README.md
```

## 🔧 Advanced Features

### Real-time Progress Tracking
- Live workflow stage updates
- Execution time per step
- Cache hit/miss indicators
- Error tracking with retry status

### Intelligent Caching
- Metrics extraction results
- Vector search results
- Reduces redundant LLM calls
- 60-70% cost savings on repeated queries

### Auto-Retry Logic
- Up to 3 retries for failed query generation
- Automatic query regeneration with fixes
- Graceful error handling
- Detailed error messages

### Multi-Query Dashboards
- Combine multiple queries in one dashboard
- Mix Prometheus and PostgreSQL data
- Automatic panel layout
- Consistent styling

## 🐛 Troubleshooting

<details>
<summary><strong>Dashboard has duplicate panels</strong></summary>

**Issue:** Getting 2x panels for each query

**Solution:** This was fixed in v2.0. If still occurring:
1. Clear browser cache
2. Restart Streamlit: `docker-compose restart vizgenie`
3. Check logs for LLM hallucination warnings
</details>

<details>
<summary><strong>No metrics found in vector search</strong></summary>

**Solution:**
1. Click "🔄 Refresh All Metrics" in the UI
2. Wait for metrics to be indexed
3. Verify Prometheus is accessible
4. Check ChromaDB logs: `docker-compose logs chroma`
</details>

<details>
<summary><strong>Connection timeouts</strong></summary>

**Solution:**
1. Verify services are running: `docker-compose ps`
2. Check network connectivity
3. Increase timeout in `.env`: `REQUEST_TIMEOUT=60`
4. Check firewall settings
</details>

<details>
<summary><strong>LLM errors or rate limits</strong></summary>

**Solution:**
1. Verify Groq API key is valid
2. Check API quota at https://console.groq.com
3. Add multiple API keys for failover (comma-separated)
4. Wait a few minutes if rate limited
</details>

## 📊 Performance Metrics

Based on typical workloads:

| Metric | Value |
|--------|-------|
| Average Response Time | 3-5 seconds |
| LLM Calls per Request | 3-4 |
| Cache Hit Rate | 60-70% (after warmup) |
| Success Rate | 95%+ |
| Concurrent Users | 10+ |
| Cost per Query | ~$0.0045 |

## 🗺️ Roadmap

- [ ] Support for additional datasources (InfluxDB, Elasticsearch)
- [ ] Custom dashboard templates
- [ ] Alert rule generation
- [ ] Multi-tenancy support
- [ ] API endpoints for programmatic access
- [ ] Dashboard versioning and history
- [ ] Natural language dashboard editing
- [ ] Integration with Slack/Teams for notifications

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with amazing open-source tools:
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [LangChain](https://github.com/langchain-ai/langchain) - LLM framework
- [Groq](https://groq.com/) - Blazing fast LLM inference
- [Streamlit](https://streamlit.io/) - Beautiful web UI
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Grafana](https://grafana.com/) - Visualization platform

<div align="center" style="margin-top: 50px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px;">
  <h3 style="color: white; margin: 0;">⭐ Star us on GitHub!</h3>
  <p style="color: white; margin: 10px 0;">If VizGenie helps you, please give us a star to support development</p>
  <a href="https://github.com/vsion-x/vizgenie">
    <img src="https://img.shields.io/github/stars/vsion-x/vizgenie?style=social" alt="GitHub stars">
  </a>
</div>

<div align="center" style="margin-top: 30px;">
  <p>Made with ❤️ by the VizGenie Team</p>
  <p>
    <a href="https://docs.vizgenie.io">Documentation</a> •
    <a href="https://github.com/vsion-x/vizgenie/blob/main/CONTRIBUTING.md">Contribute</a> •
    <a href="https://github.com/vsion-x/vizgenie/issues">Report Issues</a>
  </p>
</div>