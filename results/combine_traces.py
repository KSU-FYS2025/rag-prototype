import json

import requests

session_ids = [f"Test_{i}" for i in range(75)]
full_json = {}
for session_id in session_ids:
    url = f"http://10.96.50.180:8080/dev/apps/full_agent/debug/trace/session/{session_id}"
    response = requests.get(url).json()
    print(response)
    full_json[session_id] = response

with open("full_traces.json", "w") as f:
    json.dump(full_json, f, indent=2)
