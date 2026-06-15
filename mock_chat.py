import json
import requests

adk_data = {
    "app_name": "full_agent",
    "user_id": "user",
    "session_id": "test_1",
}

run_url = "http://10.96.50.180:8080/run"
session_url =\
    f"http://10.96.50.180:8080/apps/{adk_data['app_name']}/users/{adk_data['user_id']}/sessions/{adk_data['session_id']}"

# Delete session if exists
res = requests.delete(session_url)
print(res.json())

# Create session
res = requests.post(session_url)
print(res.json())

# Load queries from ExcelQueries.json
json_data = ""
with open("ExcelQueries.json", "r") as file:
    json_data = json.load(file)

# Send chat request for all queries in ExcelQueries.json
for query in json_data:
    data = {
        "app_name": adk_data["app_name"],
        "user_id": adk_data["user_id"],
        "session_id": adk_data["session_id"],
        "new_message": {
            "parts": [
                {"text": query}
            ],
            "role": "user"
        }
    }
    res = requests.post(run_url, json=data)
    print(res.json())

