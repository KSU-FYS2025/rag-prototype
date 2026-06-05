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

# Set test mode to allow graceful failures on embedding initialization
# This is important for CI/CD where rate limiting might occur
if not os.environ.get("EMBEDDING_RETRY_ATTEMPTS"):
    os.environ["EMBEDDING_RETRY_ATTEMPTS"] = "3"

# Now import the FastAPI app (after environment is set)
from ..main import app
from ..database.db import embedding_fn, get_db_gen
from ..poi.models import get_poi_schema, get_index_params
from ..database.db import create_collection
import json

# Pre-initialize embedding model to cache it for all tests
# This prevents repeated downloads/initialization during test runs
try:
    embedding_fn.initialize(max_retries=2)
except Exception as e:
    print(f"Warning: Failed to pre-initialize embedding model: {e}")


def _ensure_database_initialized():
    """Ensure that the POI collection exists with data loaded."""
    try:
        poi_json_path = os.environ.get("POI_JSON_PATH")
        if not poi_json_path or not os.path.exists(poi_json_path):
            return False
        
        with get_db_gen() as db:
            if not db.has_collection("poi"):
                print("Collection 'poi' not found in test setup. Creating...")
                create_collection(
                    {
                        "collection_name": "poi",
                        "index_params": get_index_params(),
                    },
                    db,
                    get_poi_schema()
                )
                
                # Load POI data
                with open(poi_json_path, "r") as f:
                    json_data = json.load(f)
                
                # Transform into database format
                for poi in json_data.get("pois", []):
                    poi["position"] = [
                        poi["position"]["x"],
                        poi["position"]["y"],
                        poi["position"]["z"]
                    ]
                    poi["rotation"] = [
                        poi["rotation"]["x"],
                        poi["rotation"]["y"],
                        poi["rotation"]["z"]
                    ]
                    poi["localPosition"] = [
                        poi["localPosition"]["x"],
                        poi["localPosition"]["y"],
                        poi["localPosition"]["z"]
                    ]
                    poi["localRotation"] = [
                        poi["localRotation"]["x"],
                        poi["localRotation"]["y"],
                        poi["localRotation"]["z"]
                    ]
                    poi["id"] = poi["identification"]
                    
                    # Generate embedding
                    try:
                        embedding = embedding_fn.encode_documents([
                            f"Name: {poi['name']}\nPOI Name: {poi['poiName']}\nTitle: {poi['title']}\n"
                            f"Description: {poi['description']}\nType: {poi['type']}\nParent: {poi['parentName']}"
                        ])
                        poi["vector"] = embedding[0]
                    except Exception as e:
                        print(f"Warning: Failed to generate embedding for POI {poi.get('id')}: {e}")
                        poi["vector"] = [0.0] * 768
                
                db.insert(
                    collection_name="poi",
                    data=json_data.get("pois", [])
                )
                print(f"Successfully inserted {len(json_data.get('pois', []))} POIs")
        return True
    except Exception as e:
        print(f"Error ensuring database initialization: {e}")
        import traceback
        traceback.print_exc()
        return False


@pytest.fixture(scope="session")
def client():
    """
    Creates a TestClient with the FastAPI app.
    The lifespan context manager runs when entering the TestClient context,
    which initializes the database and loads POI data.
    
    Additional fallback initialization ensures the collection exists for tests.
    """
    test_client = TestClient(app)
    
    # Ensure database is properly initialized after app startup
    if not _ensure_database_initialized():
        pytest.skip("Could not initialize database for tests")
    
    return test_client



