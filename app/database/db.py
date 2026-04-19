from contextlib import contextmanager
from typing import Dict, Optional
import os
from pymilvus import MilvusClient, CollectionSchema, model
import json
import re
import numpy as np
from pymilvus.milvus_client import milvus_client

embedding_fn = model.DefaultEmbeddingFunction()

# --- In-Memory JSON Fallbacks ---
_in_memory_cache = None

def _load_in_memory_db():
    global _in_memory_cache
    if _in_memory_cache is not None:
        return _in_memory_cache
        
    json_path = os.environ.get("POI_JSON_PATH", "/Users/yzhao20/Documents/GitHub/MultisetAITest/MultisetAITest/Assets/NavigationFireDynamicMesh_POIs.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON POI Database not found at {json_path}")
        
    with open(json_path, 'r') as f:
        data = json.load(f)
        
    pois = data.get("pois", [])
    
    # We need to build texts to embed
    texts_to_embed = []
    for item in pois:
        poi_args = {
            "id": item.get("identification", 0),
            "name": item.get("name", ""),
            "title": item.get("title", ""),
            "poiName": item.get("poiName", ""),
            "description": item.get("description", ""),
            "type": item.get("type", "Room"),
            "parentName": item.get("parentName", ""),
            "position": item.get("position", {"x":0.0,"y":0.0,"z":0.0}),
        }
        for field in ["position"]:
            val = poi_args[field]
            if isinstance(val, dict):
                poi_args[field] = [val.get("x", 0.0), val.get("y", 0.0), val.get("z", 0.0)]
                
        text = f"The {poi_args['type']} named '{poi_args['poiName']}' (also known as {poi_args['name']}) is a point of interest titled '{poi_args['title']}'. " \
               f"It is situated within the {poi_args['parentName'] if poi_args['parentName'] else 'main scene'}. " \
               f"Description of this area: {poi_args['description'] if poi_args['description'] else 'No specific details provided.'}"
        texts_to_embed.append(text)
        
    print(f"[In-Memory DB] Embedding {len(pois)} POIs...")
    vectors = embedding_fn.encode_documents(texts_to_embed)
    
    for i, poi in enumerate(pois):
        # normalize fields for milvus-like entity
        poi["id"] = poi.get("identification", 0)
        pos = poi.get("position", {"x":0.0,"y":0.0,"z":0.0})
        poi["position"] = [pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)] if isinstance(pos, dict) else pos
        poi["_vector"] = vectors[i]
        
    _in_memory_cache = pois
    return _in_memory_cache

def simple_filter(poi, filter_expr):
    if not filter_expr:
        return True
    match = re.search(r"(\w+)\s+(LIKE|==)\s+'([^']+)'", filter_expr, re.IGNORECASE)
    if match:
        field, op, val = match.groups()
        poi_val = str(poi.get(field, ""))
        if op.upper() == "LIKE":
            search_str = val.replace("%", "").lower()
            if val.startswith("%") and val.endswith("%"): return search_str in poi_val.lower()
            elif val.endswith("%"): return poi_val.lower().startswith(search_str)
            elif val.startswith("%"): return poi_val.lower().endswith(search_str)
            else: return poi_val.lower() == search_str
        elif op == "==":
            return poi_val.lower() == val.lower()
    return True



#client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())

def get_db_info() -> tuple[str, Optional[str]]:
    if not "DB_URL" in os.environ:
        raise Exception("Database url (DB_URL) not found in the .env file!")

    return os.environ.get("DB_URL"), os.environ.get("DB_TOKEN")


def create_db_connection() -> MilvusClient:
    _db_url, _db_token = get_db_info()
    try:
        if _db_token:
            client = MilvusClient(
                _db_url,
                token=_db_token
            )
        else:
            client = MilvusClient(
                _db_url
            )

    except Exception as e:
        raise Exception(f"{e}\nError while creating database connection! Please ensure that the database server is running\n"
                        f"and didn't randomly suspend the server for no reason :)")
    return client


@contextmanager
def get_db_gen():
    """
    Base function from
    https://www.getorchestra.io/guides/fastapi-and-sql-databases-a-detailed-tutorial
    """
    client = create_db_connection()
    try:
        yield client
    finally:
        client.close()


def create_schema(schema: list[Dict]) -> CollectionSchema:
    """
    creates and returns schema using parameters from the schema parameter.
    For reference to those visit https://milvus.io/docs/schema.md
    """
    with get_db_gen() as db:
        _schema = db.create_schema()
        for scheme in schema:
            _schema.add_field(**scheme)
    return _schema


def create_collection(settings: Dict, db: MilvusClient,  schema: Optional[CollectionSchema] = None):
    name = settings["collection_name"]
    if db.has_collection(name):
        print(f"Dropping existing collection: {name}")
        db.drop_collection(name)

    print(f"Creating collection: {name}")
    db.create_collection(
        schema=schema,
        **settings
    )
    print(f"Collection {name} created.")

def ensure_collection(settings: Dict, schema: Optional[CollectionSchema] = None, db: Optional[MilvusClient] = None):
    if db is not None:
        name = settings["collection_name"]
        if not db.has_collection(name):
            print(f"Collection {name} not found. Creating...")
            db.create_collection(
                schema=schema,
                **settings
            )
            print(f"Collection {name} created.")
        return

    with get_db_gen() as db:
        ensure_collection(settings, schema, db)


def search_poi(
       query: str,
       top_n: int = 5,
       fields: list[str] = None,
       filter_expression: str = ""
    ) -> list[tuple]:
    search_mode = os.environ.get("SEARCH_MODE", "milvus").lower()
    
    if search_mode == "milvus":
        query_vectors = embedding_fn.encode_queries([query])
        with get_db_gen() as db:
            res = db.search(
                collection_name="poi",
                data=query_vectors,
                limit=top_n,
                output_fields=fields,
                filter=filter_expression
            )
        return [(hit["entity"], hit["distance"]) for x in res for hit in x if hit]
        
    elif search_mode == "in_memory":
        pois = _load_in_memory_db()
        query_vectors = embedding_fn.encode_queries([query])
        # Flatten the outer query array down to 1D
        query_vector = np.array(query_vectors[0]) 
        
        results = []
        for poi in pois:
            if not simple_filter(poi, filter_expression):
                continue
                
            poi_vec = np.array(poi["_vector"])
            dist = float(np.dot(query_vector, poi_vec) / (np.linalg.norm(query_vector) * np.linalg.norm(poi_vec)))
            
            entity = {k: v for k, v in poi.items() if (not fields or k in fields)}
            results.append((entity, dist))
            
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]
        
    elif search_mode == "gemini_context":
        pois = _load_in_memory_db()
        results = []
        for poi in pois:
            if not simple_filter(poi, filter_expression):
                continue
            entity = {k: v for k, v in poi.items() if (not fields or k in fields)}
            results.append((entity, 1.0)) # Dummy distance
        return results
        
    else:
        raise ValueError(f"Unknown SEARCH_MODE: {search_mode}")
