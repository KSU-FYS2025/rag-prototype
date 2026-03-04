import sys
from unittest.mock import MagicMock, patch
import json

# Mocking dependencies before importing app.AI.api
mock_ollama = MagicMock()
mock_db = MagicMock()
sys.modules['ollama'] = mock_ollama
sys.modules['app.database.db'] = mock_db
sys.modules['app.dependencies'] = MagicMock()
sys.modules['app.AI.extras'] = MagicMock()

# Setup fastapi mock to NOT break decorators
mock_fastapi = MagicMock()
mock_router = MagicMock()
def pass_through_decorator(func):
    return func
mock_router.get.return_value = pass_through_decorator
mock_fastapi.APIRouter.return_value = mock_router
sys.modules['fastapi'] = mock_fastapi
sys.modules['fastapi.params'] = MagicMock()
sys.modules['starlette.responses'] = MagicMock()

# Now import the triage_agent
from app.AI.api import triage_agent

def test_triage_agent_navigation():
    # Setup mock response from LLM
    mock_response = {
        "message": {
            "content": json.dumps({
                "type": "navigation",
                "targets": [
                    {"category": "explicit", "semantics": "coffee", "description": "Find coffee"}
                ]
            })
        }
    }
    mock_ollama.chat.return_value = mock_response
    
    # search_poi returns [(entity, distance), ...]
    mock_db.search_poi.return_value = [
        ({"id": 1, "poiName": "Starbucks", "position": [1, 0, 1]}, 0.1)
    ]
    
    # Call the agent
    result = triage_agent("Where is the coffee?")
    
    print("Navigation Result Type:", type(result))
    print("Navigation Result Keys:", result.keys() if isinstance(result, dict) else "N/A")
    
    # Check for MagicMocks in the result
    def check_for_mocks(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if "MagicMock" in str(type(v)):
                    print(f"Found MagicMock in key: {k}")
                check_for_mocks(v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if "MagicMock" in str(type(v)):
                    print(f"Found MagicMock in list index: {i}")
                check_for_mocks(v)

    check_for_mocks(result)

    try:
        print("Navigation Result JSON:", json.dumps(result, indent=2))
    except Exception as e:
        print(f"JSON Dump failed: {e}")
        print("Raw result:", result)
        raise e
    
    assert result["type"] == "navigation"
    assert len(result["targets"]) == 1
    assert "poi_results" in result["targets"][0]
    assert result["targets"][0]["poi_results"][0]["poiName"] == "Starbucks"
    print("Navigation Test Passed!")

def test_triage_agent_greeting():
    # Setup mock response from LLM
    mock_response = {
        "message": {
            "content": json.dumps({
                "type": "greeting",
                "response": "Hello! How can I help you today?"
            })
        }
    }
    mock_ollama.chat.return_value = mock_response
    
    # Call the agent
    result = triage_agent("Hi")
    
    print("Greeting Result:", json.dumps(result, indent=2))
    
    assert result["type"] == "greeting"
    assert "Hello" in result["response"]
    print("Greeting Test Passed!")

if __name__ == "__main__":
    try:
        test_triage_agent_navigation()
        test_triage_agent_greeting()
        print("\nAll backend logic tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
