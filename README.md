# VizGenie: Visualize Your Data Your Way

VizGenie is a tool that simplifies the process of visualizing metrics from your data sources within Grafana. By understanding your natural language queries, VizGenie leverages the power of language models to fetch relevant metrics, construct PromQL queries (currently supporting Prometheus, with more data sources planned), generate Grafana dashboard JSON, and automatically apply it to your Grafana instance.

## Key Features

* **Natural Language to Visualization:** Enter your desired visualization in plain English, and VizGenie will attempt to create it.
* **Grafana Integration:** Seamlessly creates and applies dashboards directly to your Grafana instance.
* **Prometheus Support (Current):** Fully supports Prometheus as a data source for metric retrieval.
* **Extensible Architecture (Future):** Designed to support more data sources beyond Prometheus in future updates.
* **Intelligent Query Generation:** Uses language models to understand your intent and generate appropriate PromQL queries.

## Prerequisites

Before you can use VizGenie, ensure you have the following:

* **Groq API Key:** VizGenie utilizes models from Groq. Create an API key on the [Groq platform]([Groq Platform Link - Replace with actual link]).
* **Grafana API Key:** You need a Grafana API key with permissions to create and manage dashboards. To create one:
    1.  Go to **Service Accounts** in your Grafana instance.
    2.  Create a new API key.
    3.  Ensure the key has the necessary permissions (e.g., `dashboards:write`).
* **Docker (Optional but Recommended for Development):** If you intend to use the provided development environment.

## Configuration

Create a `.env` file in the root directory of the project and populate it with your credentials and Grafana/Prometheus URLs:

```GROQ_API_KEY=<YOUR_GROQ_API_KEY> GRAFANA_KEY=<YOUR_GRAFANA_API_KEY> ```
```PROMETHEUS_HOST=http://localhost # Or your Prometheus instance URL ```
```GRAFANA_HOST=http://localhost:3000 # Or your Grafana instance URL```

**Important:** Replace the placeholder values with your actual API keys and host addresses.

## Running VizGenie

You have two primary ways to run VizGenie: using Docker Compose for the development environment or directly using Streamlit.

### Using Docker Compose (Recommended for Development)

1. Ensure you have Docker and Docker Compose installed on your system. 
2. Navigate to the root directory of the VizGenie project in your terminal. 
3. Run the following command to spin up the development environment: 
```bash 
docker-compose up 
```
5. Once the containers are running, you should be able to access the VizGenie UI in your web browser, typically at `http://localhost:8501`.

### Running Directly with Streamlit 
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