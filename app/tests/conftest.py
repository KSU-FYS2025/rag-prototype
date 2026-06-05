"""
Pytest configuration for RAG Prototype tests.

This file sets up the test environment with proper environment variables
and ensures the database is initialized for all tests.
"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure environment variables are set BEFORE importing FastAPI app
project_root = Path(__file__).parent.parent.parent

# Set default environment variables if not already set
if not os.environ.get("POI_JSON_PATH"):
    poi_json_path = project_root / "NavigationFireDynamicMesh_POIs.json"
    if poi_json_path.exists():
        os.environ["POI_JSON_PATH"] = str(poi_json_path)
    else:
        # Fallback to a path that might exist in alternative locations
        os.environ["POI_JSON_PATH"] = str(poi_json_path)

if not os.environ.get("DB_URL"):
    os.environ["DB_URL"] = "database.db"

if not os.environ.get("AI_MODEL"):
    os.environ["AI_MODEL"] = "deepseek-r1:8b"

# Now import the FastAPI app (after environment is set)
from ..main import app


@pytest.fixture(scope="session")
def client():
    """
    Creates a TestClient with the FastAPI app.
    The lifespan context manager runs when entering the TestClient context,
    which initializes the database and loads POI data.
    """
    with TestClient(app) as fastapi_client:
        yield fastapi_client


