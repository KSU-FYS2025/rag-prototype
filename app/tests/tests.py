from fastapi import HTTPException

from ..main import app
from ..dependencies import needs_ollama
from fastapi.testclient import TestClient


client = TestClient(app)

def test_fastapi_server():
    response = client.get("/ping")
    assert response.json() == {"message": "pong!"}

def test_ollama():
    failed = False
    try:
        needs_ollama()
    except HTTPException:
        failed = True

    assert not failed

def test_milvus():
    response = client.get("/poi/all")
    print(response)
    assert response.json() != {}
