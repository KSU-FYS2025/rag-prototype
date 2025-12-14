from copy import deepcopy
from typing import Optional, Any, Literal, Callable, Type, Tuple

import pydantic.v1.main
from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo
from pydantic.main import IncEx
from pydantic.v1.main import ModelMetaclass
from pydantic.v1.schema import schema
from pymilvus import DataType
from pymilvus.model.dense import OnnxEmbeddingFunction

from app.database.db import create_schema, client

# https://stackoverflow.com/a/76560886
def partial_model(model: Type[BaseModel]):
    def make_field_optional(field: FieldInfo, default: Any = None) -> Tuple[Any, FieldInfo]:
        new = deepcopy(field)
        new.default = default
        new.annotation = Optional[field.annotation]  # type: ignore
        return new.annotation, new
    return create_model(
        f'Partial{model.__name__}',
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

    def model_dump(
        self,
        *,
        mode: Literal['json', 'python'] | str = 'python',
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_computed_fields: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal['none', 'warn', 'error'] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> list[float]:
        return [self.x, self.y, self.z]



class POI(BaseModel):
    """
    Please keep up to date with the implementation of this! This is very subject
    to change once I learn more about how to data is structured. As of right now,
    this is based off the information in the shared doc from the first meeting.
    """
    label: str
    tags: list[str]
    position: Pos | list[float]
    description: str
    vector_embedding: Optional[list[float]]

    def generate_embedding(self, embedding_fn: OnnxEmbeddingFunction):
        embedding_str = f"label: {self.label} | "
        f"tags: {",".join(self.tags)} | "
        f"description: {self.description} | "

        embedding = embedding_fn.encode_documents([embedding_str])
        self.vector_embedding = embedding[0]

@partial_model
class POIOptional(POI):
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
