import json
import requests

adk_data = {
    "app_name": "full_agent",
    "user_id": "user",
    "evalset_name": "full_agent_eval_set_large_5",
}

adk_url = "http://10.96.50.180:8080"
app_url = f"{adk_url}/apps/{adk_data['app_name']}"
run_url = f"{adk_url}/run"
eval_set_url = (
    f"{adk_url}/dev/apps/{adk_data['app_name']}/eval_sets/{adk_data['evalset_name']}"
)

# Create evalset (new endpoint)
res = requests.post(
    f"{adk_url}/dev/apps/{adk_data['app_name']}/eval-sets",
    json={
        "evalSet": {
            "eval_set_id": adk_data["evalset_name"],
            "name": adk_data["evalset_name"],
            "description": "Full test of full_agent. Contains 75 test cases",
            "eval_cases": [],
        }
    },
)

print(res.json())

# Load queries from ExcelQueriesOld.json
json_data = ""
with open("ExcelQueriesOld.json", "r") as file:
    json_data = json.load(file)

# Send chat request for all queries in ExcelQueriesOld.json
for i, data in enumerate(json_data):
    query, category = data
    # Generate new session_id for each test case
    session_id = f"Test_{i}"
    session_url = f"{app_url}/users/{adk_data['user_id']}/sessions/{session_id}"
    # Delete session if present
    requests.delete(session_url)

    # Create session
    requests.post(session_url)

    # Create data to post
    data = {
        "app_name": adk_data["app_name"],
        "user_id": adk_data["user_id"],
        "session_id": session_id,
        "new_message": {"parts": [{"text": query}], "role": "user"},
    }

    # Post data, print response
    res = requests.post(run_url, json=data)
    print(res.json())

    # Add session (data we just posted) to evalset
    res = requests.post(
        f"{eval_set_url}/add_session",
        json={
            "evalId": str(query.replace(" ", "_"))[:45],
            "sessionId": session_id,
            "userId": adk_data["user_id"],
        },
    )
    print(res.json())
