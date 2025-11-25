from typing import Dict, Optional
from pathlib import Path

from pymilvus import MilvusClient, CollectionSchema
from pymilvus import model

client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())

"""
This file outlines basic functions to get the database up and running. These
functions are referenced in the api.py file to support all CRUD operations.
"""


def create_schema(schema: list[Dict]) -> CollectionSchema:
    """
    creates and returns schema using parameters from the schema parameter.
    For reference to those visit https://milvus.io/docs/schema.md
    """
    _schema = client.create_schema()
    for scheme in schema:
        _schema.add_field(**scheme)
    return _schema


def create_collection(settings: Dict, schema: Optional[CollectionSchema] = None):
    if client.has_collection(settings["collection_name"]):
        client.drop_collection(settings["collection_name"])

    client.create_collection(
        schema=schema,
        **settings
    )
