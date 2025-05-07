<div align="center">
  <img src="https://raw.githubusercontent.com/vsion-x/vizgenie/main/assets/vizgenielogo.svg" alt="VizGenie Logo" width="300"/>
  
  [![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
  [![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
  
  <p>
    <a href="https://www.loom.com/share/d4ebd415de14413faf23a928a728ccf9">
      <img src="https://img.shields.io/badge/🎥-Watch_Demo-FF4B4B?style=for-the-badge" alt="Watch Demo">
    </a>
    <a href="https://console.groq.com/">
      <img src="https://img.shields.io/badge/🔑-Get_API_Key-black?style=for-the-badge" alt="Get API Key">
    </a>
  </p>
</div>

# VizGenie: Visualize Your Data Your Way

VizGenie is an intelligent tool that transforms natural language queries into Grafana visualizations. It leverages language models to generate queries (PromQL and SQL), build dashboards, and deploy them automatically to your Grafana instance.

## ✨ Key Features

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://img.icons8.com/color/48/000000/conversation.png" width="48" height="48"/>
        <h3>Natural Language to Visualization</h3>
        <p>Describe metrics in plain English</p>
        <img src="https://img.shields.io/badge/✅-Feature_Enabled-success">
      </td>
      <td align="center">
        <img src="https://img.icons8.com/color/48/000000/grafana.png" width="48" height="48"/>
        <h3>Grafana Integration</h3>
        <p>Auto-create and deploy dashboards</p>
        <img src="https://img.shields.io/badge/✅-Feature_Enabled-success">
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="https://img.icons8.com/color/48/000000/database.png" width="48" height="48"/>
        <h3>Multi-Data Source</h3>
        <p>Works with Prometheus and PostgreSQL</p>
        <img src="https://img.shields.io/badge/✅-Feature_Enabled-success">
      </td>
      <td align="center">
        <img src="https://img.icons8.com/color/48/000000/artificial-intelligence.png" width="48" height="48"/>
        <h3>AI-Powered Insights</h3>
        <p>Context-aware metric recommendations</p>
        <img src="https://img.shields.io/badge/✅-Feature_Enabled-success">
      </td>
    </tr>
  </table>
</div>

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
  <a href="#-configuration">
    <img src="https://img.shields.io/badge/2.-Configuration-2196F3?style=for-the-badge&logo=cog&logoColor=white" alt="Configuration">
  </a>
  <span>→</span>
  <a href="#-deployment">
    <img src="https://img.shields.io/badge/3.-Deployment-9C27B0?style=for-the-badge&logo=rocket&logoColor=white" alt="Deployment">
  </a>
</div>

### 📋 Prerequisites

<div style="background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 10px 0;">
  <table>
    <tr>
      <td><img src="https://img.icons8.com/color/24/000000/api-key.png"/></td>
      <td><strong>Groq API Key</strong></td>
      <td><a href="https://console.groq.com/">Get it here</a></td>
    </tr>
    <tr>
      <td><img src="https://img.icons8.com/color/24/000000/grafana.png"/></td>
      <td><strong>Grafana API Key</strong></td>
      <td>Create with <code>dashboards:write</code> permissions</td>
    </tr>
    <tr>
      <td><img src="https://img.icons8.com/color/24/000000/docker.png"/></td>
      <td><strong>Docker</strong> (Optional)</td>
      <td>Recommended for containerized deployment</td>
    </tr>
    <tr>
      <td><img src="https://img.icons8.com/color/24/000000/postgreesql.png"/></td>
      <td><strong>PostgreSQL</strong></td>
      <td>Running instance or use provided Docker setup</td>
    </tr>
  </table>
</div>

### ⚙️ Configuration

<div style="background: #f8f9ff; padding: 20px; border-radius: 8px; border-left: 4px solid #2196F3; margin: 15px 0;">
  <h3>1. Environment Setup</h3>
  <p>Create a <code>.env</code> file in the root directory with your GROQ API key:</p>
  
  ```env
  GROQ_API_KEY=your_groq_api_key_here
  ```
  
  <div style="background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0;">
    <strong>ℹ️ Note:</strong> This is the only configuration needed in the <code>.env</code> file. All other configurations are managed through the Streamlit UI.
  </div>
</div>

<div style="background: #f8f9ff; padding: 20px; border-radius: 8px; border-left: 4px solid #4CAF50; margin: 15px 0;">
  <h3>2. Streamlit UI Configuration</h3>
  <p>Configure the following settings directly in the Streamlit UI when prompted:</p>
  
  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 15px 0;">
    <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
      <h4>🔌 Grafana</h4>
      <ul style="margin: 10px 0 0 0; padding-left: 20px;">
        <li>URL: <code>http://localhost:3000</code></li>
        <li>API Key with <code>dashboards:write</code> permissions</li>
      </ul>
    </div>
    
    <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
      <h4>📊 Prometheus</h4>
      <ul style="margin: 10px 0 0 0; padding-left: 20px;">
        <li>URL: <code>http://localhost:9090</code></li>
      </ul>
    </div>
    
    <div style="background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
      <h4>🐘 PostgreSQL</h4>
      <ul style="margin: 10px 0 0 0; padding-left: 20px;">
        <li>Connection String: <code>postgresql://postgres:admin@localhost:5433/sales_db</code></li>
      </ul>
    </div>
  </div>
</div>

**Sample Connection Strings:**
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- PostgreSQL: `postgresql://postgres:admin@localhost:5433/sales_db`

### Sample Database

A sample database is included in the repository:
- Database schema and metadata can be found in the `metadata/` directory
- Sample data is provided in CSV format in the root directory
- Default PostgreSQL credentials:
  - Database: `sales_db`
  - User: `postgres`
  - Password: `admin`
  - Port: `5433`

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
