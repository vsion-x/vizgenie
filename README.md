<div align="center">
  <img src="https://raw.githubusercontent.com/vsion-x/vizgenie/main/assets/vizgenielogo.svg" alt="VizGenie Logo" width="300"/>
  
  [![Demo Video](https://img.shields.io/badge/Watch-Demo_Video-blue)](https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9?sid=da9cec9a-849e-4954-89b0-3a77f2b7e6d2)
</div>

# VizGenie: Visualize Your Data Your Way

VizGenie is an intelligent tool that transforms natural language queries into Grafana visualizations. It leverages language models to generate PromQL queries, build dashboards, and deploy them automatically to your Grafana instance.

## ✨ Key Features

* **Natural Language to Visualization** - Describe metrics in plain English
* **Grafana Integration** - Auto-create and deploy dashboards
* **Prometheus Support** - Native PromQL query generation
* **Extensible Architecture** - Future support for multiple data sources
* **AI-Powered Insights** - Context-aware metric recommendations

## 🎬 Demo

<div>
    <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
      <p>Automated-Grafana-Dashboard-llm - Watch Video</p>
    </a>
    <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
      <img style="max-width:300px;" src="https://cdn.loom.com/sessions/thumbnails/d4ebd415de14413faf23a928a728ccf9-101b13f5c63868b2-full-play.gif">
    </a>
</div>

## 🚀 Getting Started

### 📋 Prerequisites

- **Groq API Key**: Get from [Groq Console](https://console.groq.com/)
- **Grafana API Key**: Create with `dashboards:write` permissions
- **Docker** (Optional): Recommended for containerized deployment

### ⚙️ Configuration

1. Create `.env` file with:
```env
GROQ_API_KEY=<YOUR_GROQ_API_KEY>
GRAFANA_KEY=<YOUR_GRAFANA_API_KEY>
PROMETHEUS_HOST=http://localhost  # Your Prometheus URL
GRAFANA_HOST=http://localhost:3000  # Your Grafana URL
```

**Important:** Replace the placeholder values with your actual API keys and host addresses.

### 🐳 Docker Deployment (Recommended)

1. Ensure you have Docker and Docker Compose installed on your system. 
2. Navigate to the root directory of the VizGenie project in your terminal. 
3. Run the following command to spin up the development environment: 
```bash 
docker-compose up 
```
5. Once the containers are running, you should be able to access the VizGenie UI in your web browser, typically at `http://localhost:8501`.

### 🐍 Local Python Setup
1. Ensure you have Python 3 and Streamlit installed. If not, you can install them using pip: 
```bash 
pip install -r requirements.txt 
```
2. Navigate to the root directory of the VizGenie project in your terminal. 
3. Run the Streamlit application using the following command:

```bash 
streamlit run main.py 
``` 
or 
```bash 
python3 -m streamlit run main.py 
```

4. Streamlit will automatically open a new tab in your web browser with the VizGenie UI.

This project is licensed under the **MIT License**. See the `LICENSE` file for more information.
