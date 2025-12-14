from typing import Optional, Any

import pydantic.v1.main
from pydantic import BaseModel
from pydantic.v1.main import ModelMetaclass
from pydantic.v1.schema import schema
from pymilvus import DataType
from pymilvus.model.dense import OnnxEmbeddingFunction

from app.database.db import create_schema, client


# From https://stackoverflow.com/a/75011200
# If this approach doesn't work, I will replace it using this https://stackoverflow.com/a/76560886
class AllOptional(pydantic.v1.main.ModelMetaclass):
    def __new__(mcls, name, bases, namespaces, **kwargs):
        cls = super().__new__(mcls, name, bases, namespaces, **kwargs)
        for field in cls.__fields__.values():
            field.required = False
        return cls


class Pos(BaseModel):
    x: float
    y: float
    z: float

    def generate_vector(self) -> list[float]:
        return [self.x, self.y, self.z]


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
        embedding_str = f"label: {self.label} | "
        f"tags: {",".join(self.tags)} | "
        f"description: {self.description} | "

        embedding = embedding_fn.encode_documents([embedding_str])
        self.vector_embedding = embedding[0]


class POIOptional(POI, metaclass=AllOptional):
    pass


posSchema = (client.create_struct_field_schema()
             .add_field("x", DataType.FLOAT)
             .add_field("y", DataType.FLOAT)
             .add_field("z", DataType.FLOAT))


def get_poi_schema():
    poiSchema = client.create_schema()
    poiSchema.add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary=True,
        auto_id=True,
    )
    poiSchema.add_field(
        field_name="label",
        datatype=DataType.ARRAY,
        element_type=DataType.VARCHAR,
        max_capacity=10,
        max_length=25,
    )
    # poiSchema.add_field(
    #     field_name="pos",
    #     datatype=DataType.STRUCT,
    #     struct_schema=posSchema,
    # )
    # I do not like this, but I have to do it this way because milvus only supports
    poiSchema.add_field(
        field_name="pos",
        datatype=DataType.ARRAY,
        element_type=DataType.FLOAT,
        max_capacity=3
    )
    poiSchema.add_field(
        field_name="description",
        datatype=DataType.VARCHAR,
        max_length=300,
    )
    poiSchema.add_field(
        field_name="vector",
        datatype=DataType.FLOAT_VECTOR,
        dim=768,
    )
    return poiSchema


def get_index_params():
    index_params = client.prepare_index_params()

    index_params.add_index(
        field_name="vector",
        index_name="vector_index",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    return index_params
