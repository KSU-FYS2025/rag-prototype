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

from app.database.db import create_schema, embedding_fn


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

class POI(BaseModel):
    """
    Aligned strictly with Unity POIData from POIExtractor.cs
    """
    id: int
    vector: Optional[list[float]] = None
    name: str = ""
    title: str = ""
    poiName: str = ""
    description: str = ""
    type: str = "Room"
    position: list[float]
    rotation: list[float] = [0.0, 0.0, 0.0]
    localPosition: list[float] = [0.0, 0.0, 0.0]
    localRotation: list[float] = [0.0, 0.0, 0.0]
    parentName: str = ""

    def generate_embedding(self):
        # Embedding based on key textual descriptors
        text = f"Name: {self.name}\nPOI Name: {self.poiName}\nTitle: {self.title}\nDescription: {self.description}\nType: {self.type}\nParent: {self.parentName}"
        self.vector = embedding_fn.encode_documents([text])


@partial_model
class POIOptional(POI):
    pass


def get_poi_schema():
    poiSchema = MilvusClient.create_schema(enable_dynamic_field=True)
    poiSchema.add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary=True,
        auto_id=False,
    )
    poiSchema.add_field(
        field_name="name",
        datatype=DataType.VARCHAR,
        max_length=200,
    )
    poiSchema.add_field(
        field_name="title",
        datatype=DataType.VARCHAR,
        max_length=200,
    )
    poiSchema.add_field(
        field_name="poiName",
        datatype=DataType.VARCHAR,
        max_length=200,
    )
    poiSchema.add_field(
        field_name="description",
        datatype=DataType.VARCHAR,
        max_length=1000,
    )
    poiSchema.add_field(
        field_name="type",
        datatype=DataType.VARCHAR,
        max_length=100,
    )
    poiSchema.add_field(
        field_name="parentName",
        datatype=DataType.VARCHAR,
        max_length=200,
    )
    # Coordinate arrays
    poiSchema.add_field(
        field_name="position",
        datatype=DataType.ARRAY,
        element_type=DataType.FLOAT,
        max_capacity=3
    )
    poiSchema.add_field(
        field_name="rotation",
        datatype=DataType.ARRAY,
        element_type=DataType.FLOAT,
        max_capacity=3
    )
    poiSchema.add_field(
        field_name="localPosition",
        datatype=DataType.ARRAY,
        element_type=DataType.FLOAT,
        max_capacity=3
    )
    poiSchema.add_field(
        field_name="localRotation",
        datatype=DataType.ARRAY,
        element_type=DataType.FLOAT,
        max_capacity=3
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

