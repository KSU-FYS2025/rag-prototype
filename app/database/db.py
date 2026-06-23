from contextlib import contextmanager
from typing import Dict, Optional, List, Any
import os
from pymilvus import MilvusClient, CollectionSchema
from sentence_transformers import SentenceTransformer
import json
import re
import logging
import time

from torch import Tensor

logger = logging.getLogger(__name__)


# Configure HuggingFace and transformers model caching
def _configure_model_caching():
    """Configure environment variables for model caching before any model loading."""
    # Set HuggingFace hub cache directory
    if not os.environ.get("HF_HOME"):
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
        os.environ["HF_HOME"] = cache_dir
        logger.info(f"Set HF_HOME to {cache_dir}")

    # Set transformers cache directory
    if not os.environ.get("TRANSFORMERS_CACHE"):
        cache_dir = os.path.join(
            os.path.expanduser("~"), ".cache", "huggingface", "transformers"
        )
        os.environ["TRANSFORMERS_CACHE"] = cache_dir
        logger.info(f"Set TRANSFORMERS_CACHE to {cache_dir}")

    # Prevent offline mode issues
    os.environ.setdefault("HF_DATASETS_OFFLINE", "0")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")


_configure_model_caching()


class EmbeddingFn:
    def __init__(self):
        self._embedding_fn = None
        self._initialization_lock = False

    def initialize(self, max_retries: int = 3, backoff_factor: float = 2.0):
        """Initialize embedding function once at startup with retry logic."""
        if self._embedding_fn is not None:
            logger.info("Embedding function already initialized.")
            return self._embedding_fn

        if self._initialization_lock:
            logger.warning("Embedding function initialization already in progress.")
            return None

        self._initialization_lock = True

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Initializing embedding function (attempt {attempt + 1}/{max_retries})..."
                )

                # Loading the embedding model explicitly using a modern wrapper
                logger.info("Loading Sentencetransformer for embeddings...")
                self._embedding_fn = SentenceTransformer(
                    "all-mpnet-base-v2"
                )  # A standard, reliable all-purpose model
                return self._embedding_fn
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    # Rate limit error - calculate backoff
                    wait_time = backoff_factor**attempt
                    logger.warning(
                        f"HuggingFace rate limit hit (HTTP 429). "
                        f"Retrying in {wait_time:.1f}s... (Attempt {attempt + 1}/{max_retries})"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Failed to initialize embedding function after {max_retries} attempts due to rate limiting. "
                            "Tests will continue but vector search may not work."
                        )
                else:
                    logger.error(
                        f"Error initializing embedding function (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor**attempt
                        logger.info(f"Retrying in {wait_time:.1f}s...")
                        time.sleep(wait_time)

        logger.error(
            "Failed to initialize embedding function after all retry attempts."
        )
        self._initialization_lock = False
        return None

    def is_initialized(self):
        return self._embedding_fn is not None

    def encode_queries(self, queries: List[str]):
        if self._embedding_fn is None:
            raise RuntimeError(
                "Embedding function not initialized. "
                "Call initialize() at startup or check server logs for initialization errors."
            )
        # Use the underlying sentence transformer method
        return self._embedding_fn.encode_query(queries, convert_to_tensor=True)

    def encode_documents(self, documents: List[str]):
        if self._embedding_fn is None:
            raise RuntimeError(
                "Embedding function not initialized. "
                "Call initialize() at startup or check server logs for initialization errors."
            )
        # Use the underlying sentence transformer method
        return self._embedding_fn.encode_document(documents, convert_to_tensor=True)


embedding_fn = EmbeddingFn()
# Initialize the embedding function globally upon module load to ensure all functions (like search_poi) can use it.
if embedding_fn._embedding_fn is None:
    embedding_fn.initialize()

# --- In-Memory JSON Fallbacks ---
_in_memory_cache = None


def _load_in_memory_db():
    global _in_memory_cache
    if _in_memory_cache is not None:
        return _in_memory_cache

    json_path = os.environ.get(
        "POI_JSON_PATH",
        "/Users/yzhao20/Documents/GitHub/MultisetAITest/MultisetAITest/Assets/NavigationFireDynamicMesh_POIs.json",
    )
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON POI Database not found at {json_path}")

    with open(json_path, "r") as f:
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
            "position": item.get("position", {"x": 0.0, "y": 0.0, "z": 0.0}),
        }
        for field in ["position"]:
            val = poi_args[field]
            if isinstance(val, dict):
                poi_args[field] = [
                    val.get("x", 0.0),
                    val.get("y", 0.0),
                    val.get("z", 0.0),
                ]

        text = (
            f"The {poi_args['type']} named '{poi_args['poiName']}' (also known as {poi_args['name']}) is a point of interest titled '{poi_args['title']}'. "
            f"It is situated within the {poi_args['parentName'] if poi_args['parentName'] else 'main scene'}. "
            f"Description of this area: {poi_args['description'] if poi_args['description'] else 'No specific details provided.'}"
        )
        texts_to_embed.append(text)

    print(f"[In-Memory DB] Embedding {len(pois)} POIs...")
    vectors = embedding_fn.encode_documents(texts_to_embed)

    for i, poi in enumerate(pois):
        # normalize fields for milvus-like entity
        poi["id"] = poi.get("identification", 0)
        pos = poi.get("position", {"x": 0.0, "y": 0.0, "z": 0.0})
        poi["position"] = (
            [pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)]
            if isinstance(pos, dict)
            else pos
        )
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
            if val.startswith("%") and val.endswith("%"):
                return search_str in poi_val.lower()
            elif val.endswith("%"):
                return poi_val.lower().startswith(search_str)
            elif val.startswith("%"):
                return poi_val.lower().endswith(search_str)
            else:
                return poi_val.lower() == search_str
        elif op == "==":
            return poi_val.lower() == val.lower()
    return True


# client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())


def get_db_info() -> tuple[str, Optional[str]]:
    db_url = os.environ.get("DB_URL")
    if not db_url:
        raise Exception("Database url (DB_URL) not found in the .env file!")

    return db_url, os.environ.get("DB_TOKEN")


# def create_db_connection() -> MilvusClient:
#     _db_url, _db_token = get_db_info()
#     try:
#         if _db_token:
#             client = MilvusClient(
#                 _db_url,
#                 token=_db_token
#             )
#         else:
#             client = MilvusClient(
#                 _db_url
#             )
#
#     except Exception as e:
#         raise Exception(f"{e}\nError while creating database connection! Please ensure that the database server is running\n"
#                         f"and didn't randomly suspend the server for no reason :)")
#     return client


def create_db_connection() -> MilvusClient:
    """Initializes and returns a database connection client using the local file path."""
    _db_url, _db_token = get_db_info()
    try:
        # Use try/except to catch immediate initialization failure related to file paths or permissions.
        if _db_token:
            client = MilvusClient(_db_url, token=_db_token)
        else:
            client = MilvusClient(_db_url)

        # Minimal check: Attempt a basic command that requires connectivity (like listing collections).
        # We still attempt this, as it's the best way to confirm local readiness.
        list_collections_result = client.list_collections()
        print(
            "Connection test successful: Successfully connected and listed collections."
        )
        return client

    except Exception as e:
        # Catching any exception ensures we report configuration or file system errors correctly.
        raise Exception(
            f"Failed to initialize MilvusClient connection with {_db_url}. "
            f"Check if the local database directory exists, permissions are correct, and pymilvus is configured for local files. Error: {e}"
        )


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


def get_db_dep():
    with get_db_gen() as db:
        yield db


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


def create_collection(
    settings: Dict, db: MilvusClient, schema: Optional[CollectionSchema] = None
):
    name = settings["collection_name"]
    if db.has_collection(name):
        print(f"Dropping existing collection: {name}")
        db.drop_collection(name)

    print(f"Creating collection: {name}")
    db.create_collection(schema=schema, **settings)
    print(f"Collection {name} created.")


def ensure_collection(
    settings: Dict,
    schema: Optional[CollectionSchema] = None,
    db: Optional[MilvusClient] = None,
):
    if db is not None:
        name = settings["collection_name"]
        if not db.has_collection(name):
            print(f"Collection {name} not found. Creating...")
            db.create_collection(schema=schema, **settings)
            print(f"Collection {name} created.")
        return

    with get_db_gen() as db:
        ensure_collection(settings, schema, db)


def _to_native(obj: Any) -> Any:
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
        return [_to_native(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    return obj


def search_poi(
    query: str,
    top_n: int = 5,
    fields: Optional[list[str]] = None,
    filter_expression: str = "",
) -> list[tuple[dict, float]]:
    query_vectors = embedding_fn.encode_queries([query])
    if isinstance(query_vectors, Tensor):
        query_vectors = query_vectors.tolist()
    with get_db_gen() as db:
        db.load_collection("poi")
        res = db.search(
            collection_name="poi",
            data=query_vectors,
            limit=top_n,
            output_fields=fields,
            filter=filter_expression,
        )

    return [
        (
            {
                **hit["entity"],
                "position": list(hit["entity"]["position"]),
                "rotation": list(hit["entity"]["rotation"]),
                "localPosition": list(hit["entity"]["localPosition"]),
                "localRotation": list(hit["entity"]["localRotation"]),
            },
            float(hit["distance"]),
        )
        for x in res
        for hit in x
        if hit
    ]


# def search_poi(
#        query: str,
#        top_n: int = 5,
#        fields: list[str] = None,
#        filter_expression: str = ""
#     ) -> list[tuple]:
#     search_mode = os.environ.get("SEARCH_MODE", "milvus").lower()
#
#     if search_mode == "milvus":
#         query_vectors = embedding_fn.encode_queries([query])
#         with get_db_gen() as db:
#             res = db.search(
#                 collection_name="poi",
#                 data=query_vectors,
#                 limit=top_n,
#                 output_fields=fields,
#                 filter=filter_expression
#             )
#         return [(hit["entity"], hit["distance"]) for x in res for hit in x if hit]
#
#     elif search_mode == "in_memory":
#         pois = _load_in_memory_db()
#         query_vectors = embedding_fn.encode_queries([query])
#         # Flatten the outer query array down to 1D
#         query_vector = np.array(query_vectors[0])
#
#         results = []
#         for poi in pois:
#             if not simple_filter(poi, filter_expression):
#                 continue
#
#             poi_vec = np.array(poi["_vector"])
#             dist = float(np.dot(query_vector, poi_vec) / (np.linalg.norm(query_vector) * np.linalg.norm(poi_vec)))
#
#             entity = {k: v for k, v in poi.items() if (not fields or k in fields)}
#             results.append((entity, dist))
#
#         results.sort(key=lambda x: x[1], reverse=True)
#         return results[:top_n]
#
#     elif search_mode == "gemini_context":
#         pois = _load_in_memory_db()
#         results = []
#         for poi in pois:
#             if not simple_filter(poi, filter_expression):
#                 continue
#             entity = {k: v for k, v in poi.items() if (not fields or k in fields)}
#             results.append((entity, 1.0)) # Dummy distance
#         return results
#
#     else:
#         raise ValueError(f"Unknown SEARCH_MODE: {search_mode}")
