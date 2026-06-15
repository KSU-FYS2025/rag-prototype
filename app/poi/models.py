import json
import logging
from copy import deepcopy
from typing import Optional, Any, Literal, Callable, Type, Tuple, TypeVar

from pydantic import BaseModel, create_model, Field, model_validator
from pydantic.fields import FieldInfo
from pymilvus import DataType, MilvusClient

from app.database.db import embedding_fn


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

class POIDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    @staticmethod
    def object_hook(json_data: dict) -> dict:
        if "pois" not in json_data:
            raise Exception(f"No pois data found in json data: {json_data}")
        for i, poi in enumerate(json_data["pois"]):
            # Transform into database format (turns position objects into arrays)
            json_data["pois"][i]["position"] = [
                poi["position"]["x"],
                poi["position"]["y"],
                poi["position"]["z"]
            ]
            json_data["pois"][i]["rotation"] = [
                poi["rotation"]["x"],
                poi["rotation"]["y"],
                poi["rotation"]["z"]
            ]
            json_data["pois"][i]["localPosition"] = [
                poi["localPosition"]["x"],
                poi["localPosition"]["y"],
                poi["localPosition"]["z"]
            ]
            json_data["pois"][i]["localRotation"] = [
                poi["localRotation"]["x"],
                poi["localRotation"]["y"],
                poi["localRotation"]["z"]
            ]
            json_data["pois"][i]["id"] = poi["identification"]

        try:
            vectors = POI.batch_generate_embedding_json(json_data["pois"])

            def mapfunc(vector, poi_item):
                poi_item["vector"] = vector
                return poi_item

            json_data["pois"] = list(map(mapfunc, vectors, json_data["pois"]))

        except Exception as e:
            # If embedding fails due to network issues, log and continue
            # The app can still start, but vector search may not be available
            logging.warning(
                f"Failed to generate embedding for POI: {e}. "
                f"This may be due to network issues. Vector search may be unavailable."
            )
            embedding_init_failed = True
            # Create a dummy embedding if network fails

        return json_data

class POI(BaseModel):
    """
    Aligned strictly with Unity POIData from POIExtractor.cs
    """
    id: int = Field(description="Unique identifier of the POI")
    name: str = Field(description="Name of the POI")
    vector: Optional[list[float]] = Field(default=None, description="Vector embedding representation of the POI")
    title: str = Field(default="", description="Title of the POI. Brief information about what the POI is.")
    poiName: str = Field(description="Name of the POI. Will be the same as title a majority of the time.")
    description: str = Field(description="Brief description of the POI")
    type: str = Field(default="Room", description="Type of the POI. What it represents at a high level")
    position: list[float] = Field(description="Position of the POI")
    rotation: list[float] = Field(default=[0.0, 0.0, 0.0], description="Rotation of the POI")
    localPosition: list[float] = Field(default=[0.0, 0.0, 0.0], description="Local position of the POI")
    localRotation: list[float] = Field(default=[0.0, 0.0, 0.0], description="Local rotation of the POI")
    parentName: str = Field(default="", description="What collection of POIs the POI belongs to.")

    def generate_embedding_str(self):
        # Embedding based on key textual descriptors
        return f"Name: {self.name}\nPOI Name: {self.poiName}\nTitle: {self.title}\nDescription: {self.description}\nType: {self.type}\nParent: {self.parentName}"

    def generate_embedding(self):
        self.vector = embedding_fn.encode_documents([self.generate_embedding_str()])

    @classmethod
    def generate_embedding_str_json(cls, data: dict):
        return f"Name: {data["name"]}\nPOI Name: {data["poiName"]}\nTitle: {data["title"]}\nDescription: {data["description"]}\nType: {data["type"]}\nParent: {data["parentName"]}"

    @classmethod
    def generate_embedding_json(cls, data: dict):
        return embedding_fn.encode_documents([POI.generate_embedding_str_json(data)])

    @classmethod
    def batch_generate_embedding_json(cls, data: list[dict]):
        embedding_data = [POI.generate_embedding_str_json(item) for item in data]
        return list(embedding_fn.encode_documents(embedding_data))

    @model_validator(mode="before")
    @classmethod
    def convert_to_list(cls, data: Any) -> Any:
        # Convert position and rotation from dict to list if necessary
        if isinstance(data, dict):
            for field in ["position", "rotation", "localPosition", "localRotation"]:
                if field in data and not isinstance(data[field], list):
                    data[field] = list(data[field])
        return data

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

