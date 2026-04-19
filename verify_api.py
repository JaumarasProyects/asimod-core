import requests
import json

try:
    resp = requests.get("http://localhost:8000/v1/modules")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Modules: {len(data['modules'])}")
    for m in data['modules']:
        print(f" - {m['id']} (UI: {m['has_web_ui']})")
except Exception as e:
    print(f"Error: {e}")
