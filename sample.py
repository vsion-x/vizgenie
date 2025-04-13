import requests

dashboard_json = {
    "title": "Job with the Highest CPU Usage",
    "uid": "cpu-usage-dashboard",
    "panels": [
        {
            "title": "Top Job by CPU Usage",
            "type": "timeseries",
            "datasource": {
                "type": "prometheus",
                "uid": "P1809F7CD0C75ACF3"
            },
            "targets": [
                {
                    "expr": "topk(1, sum by (job) (rate(process_cpu_seconds_total[5m])))",
                    "refId": "A"
                }
            ],
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
        }
    ],
    "time": {"from": "now-5m", "to": "now"},
    "refresh": "10s",
    "schemaVersion": 41,
    "version": 1
}

url = "http://localhost:3000/api/dashboards/db"
headers = {
    "Content-Type": "application/json",
    "Authorization": ""
}

payload = {
    "dashboard": dashboard_json,
    "overwrite": True
}

try:
    response = requests.post(url, headers=headers, json=payload)
    print(response.text, response.status_code)

    if response.status_code == 200:
        print("✅ Dashboard imported successfully.")
    else:
        print("❌ Error importing dashboard.")
except Exception as e:
    print(f"Error: {e}")
