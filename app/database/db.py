from contextlib import contextmanager
from typing import Dict, Optional
import os
from pymilvus import MilvusClient, CollectionSchema, model

embedding_fn = model.DefaultEmbeddingFunction()


#client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())

def get_db_info() -> tuple[str, Optional[str]]:
    if not "DB_URL" in os.environ:
        raise Exception("Database url (DB_URL) not found in the .env file!")

    return os.environ.get("DB_URL"), os.environ.get("DB_TOKEN")


def create_db_connection() -> MilvusClient:
    _db_url, _db_token = get_db_info()
    try:
        client = MilvusClient(
            _db_url,
            token=_db_token
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


def create_collection(settings: Dict, schema: Optional[CollectionSchema] = None):
    with get_db_gen() as db:
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
       fields: list[str] = None
    ) -> list[tuple]:
    query_vectors = embedding_fn.encode_queries([query])

    with get_db_gen() as db:
        res = db.search(
            collection_name="poi",
            data=query_vectors,
            limit=top_n,
            output_fields=fields
        )

    return [(x[0]["entity"], x[0]["distance"]) for x in res]
