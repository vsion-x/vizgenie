# 🎩 VizGenie

> **Transform natural language into Grafana dashboards with AI-powered observability**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1.19-green.svg)](https://github.com/langchain-ai/langgraph)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🗣️ **Natural Language Queries** | Describe metrics in plain English |
| 📊 **Auto Dashboard Generation** | Grafana dashboards deployed in seconds |
| 🔍 **AI-Powered RCA** | Autonomous root cause analysis in < 15s |
| 🧠 **Log Pattern Learning** | Self-learns regex patterns from your logs |
| 📜 **Log Segregation** | Background categorisation with Loki |
| ⏱️ **MTTD / MTTR Tracking** | Built-in SRE observability metrics |
| 🔌 **Multi-Datasource** | Prometheus + PostgreSQL + Loki |

---

## 🏗️ Architecture
```
┌────────────────────────────────────────────────────────┐
│                    Streamlit UI                        │
│   Connections · Query Interface · Job Control · RCA   │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│              LangGraph Agent System                    │
│  Supervisor → Metrics | SQL | Investigator | Learning │
│                      RCA Agent                        │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│              Async Background Jobs                     │
│       Unified Monitor (Log Segregation + RCA)         │
└───────────────────────┬────────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────────┐
│                   Tools Layer                          │
│  Prometheus · PostgreSQL · Loki · VectorDB · Grafana  │
└────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Docker (Recommended)
```bash
# 1. Clone
git clone https://github.com/your-org/vizgenie.git
cd vizgenie

# 2. Configure
cp .env.example .env
# Edit .env → add your GROQ_API_KEY

# 3. Start full stack
docker compose up -d

# 4. Open
open http://localhost:8501
```

### Local Python
```bash
# 1. Python 3.12 required
python --version   # Python 3.12.x

# 2. Install deps
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Edit .env → add your GROQ_API_KEY

# 4. Run
streamlit run main.py
```

---

## ⚙️ Configuration

### Mandatory Services

| Service | Purpose | Get Key |
|---|---|---|
| **Groq** | LLM backbone | [console.groq.com](https://console.groq.com) |
| **Grafana** | Dashboard platform | Self-hosted or [grafana.com](https://grafana.com) |

### Optional Services

| Service | Purpose | Default Port |
|---|---|---|
| Prometheus | Metrics | 9090 |
| Loki | Logs | 3100 |
| PostgreSQL | Relational data | 5433 |

### Environment Variables
```bash
GROQ_API_KEY=gsk_...           # Required
LOG_LEVEL=INFO                 # Optional
POSTGRES_USER=postgres         # Optional
POSTGRES_PASSWORD=admin        # Optional
POSTGRES_DB=sales_db           # Optional
GRAFANA_USER=admin             # Optional
GRAFANA_PASSWORD=admin         # Optional
```

---

## 📖 Usage

### 1. Connect Services
Navigate to **Connections** → test Groq + Grafana (mandatory) →
optionally connect Prometheus, Loki, PostgreSQL.

### 2. Create a Dashboard
Navigate to **Dashboard** → type a natural language query:
- *"Show CPU usage over the last hour"*
- *"Top 10 customers by sales revenue"*
- *"Why is my FastAPI service slow?"*

### 3. Monitor Automatically
Navigate to **Job Control** → **Start Monitor** →
select a Loki datasource → configure thresholds → click **Start**.

The monitor will:
- Categorise logs every 30 seconds using learned patterns
- Detect anomalies every 15 seconds
- Trigger RCA automatically when thresholds are breached
- Display reports in the **RCA Reports** tab

### 4. Learn New Patterns
Click **Learn Patterns** on the Dashboard page to trigger the
learning agent — it fetches 1 000 log samples, extracts regex
patterns via LLM, validates them, and saves to
`config/log_patterns.yaml`.

---

## 📁 Project Structure
```
vizgenie/
├── main.py                         # Streamlit entry point
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── schemas/
│   └── state.py                    # LangGraph AgentState
│
├── graphs/                         # LangGraph agent graphs
│   ├── supervisor_graph.py
│   ├── metrics_graph.py
│   ├── sql_graph.py
│   ├── investigator_graph.py
│   ├── learning_graph.py
│   └── rca_graph.py
│
├── nodes/                          # Graph node functions
│   ├── metric_nodes.py
│   ├── sql_nodes.py
│   └── dashboard_node.py
│
├── tools/                          # Datasource tools
│   ├── base_tool.py
│   ├── vectordb_tools.py
│   ├── prometheus_tools.py
│   ├── postgres_tools.py
│   ├── loki_tools.py
│   ├── learning_tools.py
│   ├── dashboard_tools.py
│   └── __init__.py
│
├── bg_jobs/
│   └── unified_monitor.py          # Async log segregation + RCA
│
├── llm/
│   ├── prompts.py
│   ├── retry_handler.py
│   └── groq_client.py
│
├── ui/
│   ├── job_control.py
│   └── query_interface.py
│
├── utils/
│   ├── logger.py
│   ├── validators.py
│   └── streamlit_notifier.py
│
├── config/
│   ├── datasources.yaml
│   ├── log_patterns.yaml
│   └── thresholds.yaml
│
├── metadata/
│   └── metadata.yaml
│
└── docker/
    ├── grafana/provisioning/
    ├── prometheus/prometheus.yml
    ├── loki/loki-config.yaml
    ├── promtail/promtail-config.yaml
    └── postgres/init.sql
```

---

## 📜 License

MIT — © VizGenie Team