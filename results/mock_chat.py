import json
import requests

adk_data = {
    "app_name": "full_agent",
    "user_id": "user",
    "evalset_name": "full_agent_eval_set_large_16",
}

adk_url = "http://10.96.50.180:8080"
app_url = f"{adk_url}/apps/{adk_data['app_name']}"
run_url = f"{adk_url}/run"
eval_set_url = (
    f"{adk_url}/dev/apps/{adk_data['app_name']}/eval_sets/{adk_data['evalset_name']}"
)

print(f"Target ADK URL: {adk_url}")
print(f"Target Run URL: {run_url}")

# Check if ADK is reachable
try:
    ping_res = requests.get(adk_url, timeout=5)
    print(f"ADK Ping Status: {ping_res.status_code}")
except Exception as e:
    print(f"ADK Ping FAILED: {e}")

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

# Load queries from ExcelQueries.json
json_data = ""
with open("ExcelQueries.json", "r") as file:
    json_data = json.load(file)

# Send chat request for all queries in ExcelQueries.json
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

    # Print debugging info
    print(f"[{i}] Query: {query}")

    # Post data, print response
    try:
        res = requests.post(run_url, json=data)
        res.raise_for_status()
        print(f"Query {i}: {query} - SUCCESS")
        print(res.json())
    except Exception as e:
        print(f"Query {i}: {query} - FAILED")
        print(f"Error: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                print(f"Response content: {e.response.json()}")
            except:
                print(f"Response content: {e.response.text}")
        # Stop on first failure to investigate
        # break

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
