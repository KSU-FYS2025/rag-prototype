from fastapi import HTTPException
import pytest

from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

from ..dependencies import needs_ollama
from ..mcp.api import mcp
from fastapi.testclient import TestClient

@pytest.fixture
async def main_mcp_client():
    async with Client(transport=mcp) as mcp_client:
        yield mcp_client

def test_env(client: TestClient):
    import os
    print("DB_URL:", os.environ.get("DB_URL"))
    print("POI_JSON_PATH:", os.environ.get("POI_JSON_PATH"))

def test_fastapi_server(client):
    response = client.get("/ping")
    assert response.json() == {"message": "pong!"}

def test_ollama():
    failed = False
    try:
        needs_ollama()
    except HTTPException:
        failed = True

    assert not failed

def test_milvus(client: TestClient):
    response = client.get("/poi/all")
    print(response)
    assert response.json() != {}

@pytest.mark.asyncio
async def test_ping(main_mcp_client: Client[FastMCPTransport]):
    res = await main_mcp_client.call_tool("ping")

    assert res.data == "pong!"
