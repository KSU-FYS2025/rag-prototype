from contextlib import contextmanager
from typing import Dict, Optional
import os
from pymilvus import MilvusClient, CollectionSchema

#client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())

def get_db_info() -> tuple[str, str] | None:
    if not "DB_URL" in os.environ or not "DB_TOKEN" in os.environ:
        raise Exception("Database url or token not found in the .env file!")

    return os.environ.get("DB_URL"), os.environ.get("DB_TOKEN")

def create_db_connection() -> MilvusClient:
    _db_url, _db_token = get_db_info()

    return MilvusClient(
        _db_url,
        token=_db_token
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
        if db.has_collection(settings["collection_name"]):
            db.drop_collection(settings["collection_name"])

        db.create_collection(
            schema=schema,
            **settings
        )
