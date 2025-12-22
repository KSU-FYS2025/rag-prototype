from copy import deepcopy
from typing import Optional, Any, Literal, Callable, Type, Tuple, TypeVar

import pydantic.v1.main
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo
from pydantic.main import IncEx
from pydantic.v1.main import ModelMetaclass
from pydantic.v1.schema import schema
from pymilvus import DataType, MilvusClient
from pymilvus.model.dense import OnnxEmbeddingFunction

from app.database.db import create_schema

# https://stackoverflow.com/a/76560886
def partial_model(model: Type[BaseModel]):
    def make_field_optional(field: FieldInfo, default: Any = None) -> Tuple[Any, FieldInfo]:
        new = deepcopy(field)
        new.default = default
        new.annotation = Optional[field.annotation]  # type: ignore
        return new.annotation, new
    return create_model(
        model.__name__,
        __base__=model,
        __module__=model.__module__,
        **{
            field_name: make_field_optional(field_info)
            for field_name, field_info in model.model_fields.items()
        }
    )


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
    id: Optional[int] = None
    label: str
    tags: list[str]
    pos: list[float]
    description: str
    vector: Optional[list[float]] = None

    def generate_embedding(self, embedding_fn: OnnxEmbeddingFunction):
        embedding_str = f"label: {self.label} | "
        f"tags: {",".join(self.tags)} | "
        f"description: {self.description} | "

        embedding = embedding_fn.encode_documents([embedding_str])
        self.vector = embedding[0].tolist()

@partial_model
class POIOptional(POI):
    pass


posSchema = (MilvusClient.create_struct_field_schema()
             .add_field("x", DataType.FLOAT)
             .add_field("y", DataType.FLOAT)
             .add_field("z", DataType.FLOAT))


def get_poi_schema():
    poiSchema = MilvusClient.create_schema()
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
    index_params = MilvusClient.prepare_index_params()

    index_params.add_index(
        field_name="vector",
        index_name="vector_index",
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    return index_params


def dump_and_trim_none(obj: BaseModel) -> dict:
    print(f"items: {obj.model_dump().items()}")
    new = {key: value for key, value in obj.model_dump().items() if value is not None}
    return new

