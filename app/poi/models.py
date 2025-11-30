from typing import Optional, Any

from pydantic import BaseModel
from pydantic.v1.schema import schema
from pymilvus import DataType
from pymilvus.model.dense import OnnxEmbeddingFunction

from app.database.db import create_schema, client


class Pos(BaseModel):
    x: float
    y: float
    z: float

def generate_embedding(obj, embedding_fn: OnnxEmbeddingFunction):
    embedding_str = f"label: {obj.label} | "
    f"tags: {",".join(obj.tags)} | "
    f"description: {obj.description} | "

    embedding = embedding_fn.encode_documents([embedding_str])
    obj.vector_embedding = embedding[0]

class POI(BaseModel):
    """
    Please keep up to date with the implementation of this! This is very subject
    to change once I learn more about how to data is structured. As of right now,
    this is based off the information in the shared doc from the first meeting.
    """
    label: str
    tags: list[str]
    position: Pos
    description: str
    vector_embedding: Optional[list[float]]

    def generate_embedding(self, embedding_fn: OnnxEmbeddingFunction):
        generate_embedding(self, embedding_fn)

class POIOptional(BaseModel):
    label: Optional[str]
    tags: Optional[list[str]]
    position: Optional[Pos]
    description: Optional[str]
    vector_embedding: Optional[list[float]]

    def generate_embedding(self, embedding_fn: OnnxEmbeddingFunction):
        generate_embedding(self, embedding_fn)

posSchema = (client.create_struct_field_schema()
             .add_field("x", DataType.FLOAT)
             .add_field("y", DataType.FLOAT)
             .add_field("z", DataType.FLOAT))

poiSchema = (client.create_schema()
            .add_field(
                field_name="id",
                datatype=DataType.INT32,
                is_primary=True,
                auto_id=True,
            )
            .add_field(
                field_name="label",
                datatype=DataType.ARRAY,
                element_type=DataType.VARCHAR,
                max_capacity=10,
                max_length=25,
            )
            .add_field(
                field_name="pos",
                datatype=DataType.STRUCT,
                struct_schema=posSchema,
            )
            .add_field(
                field_name="description",
                datatype=DataType.VARCHAR,
                max_length=300,
            )
            .add_field(
                field_name="vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=768,
))

index_params = client.prepare_index_params()

index_params.add_index(
    field_name="vector",
    index_type="vector_index",
    index_name="AUTOINDEX",
    metric_type="COSINE",
)
