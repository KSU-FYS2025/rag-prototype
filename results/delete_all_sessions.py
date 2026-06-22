import requests

host = "http://10.96.50.180:8080"

sessions = requests.get(f"{host}/apps/full_agent/users/user/sessions").json()
for session in sessions:
    res = requests.delete(f"{host}/apps/full_agent/users/user/sessions/{session["id"]}")
    print(res.json())
