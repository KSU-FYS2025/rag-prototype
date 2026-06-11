from pydantic import BaseModel, Field
from typing import List

from app.AI.schema import BaseResponse
from app.poi.models import POI

class Validation(BaseModel):
    order: int = Field(description="The order of the POIs returned by the input. This MUST match your input.")
    selected_pois: List[POI] = Field(description="List of POIs chosen by the LLM.")
    method: str = Field(default="LLM",description="MUST always be LLM")

class SearchOutput(BaseResponse):
    validations: List[Validation]

# class Vector(BaseModel):
#     dx: float = Field(description="x component of distance between two points")
#     dy: float = Field(description="y component of distance between two points")
#     dz: float = Field(description="z component of distance between two points")

# class DistanceAndVector(BaseModel):
#     distance: float = Field(description="Scalar distance between two points")
#     vector: Vector = Field(description="Vector between two points")

# class DistanceBetweenPOIs(BaseModel):
#     poi1: int = Field(description="id of first POI")
#     poi2: int = Field(description="id of second POI")
#     distance: DistanceAndVector

class POIAndSemanticDistance(BaseModel):
    poi: POI = Field(description="The POI object that this object is associated with")
    semantic_distance: float = Field(description="The semantic distance between this POI and the semantic for this "
                                                 "query.")

class ParallelOutput(BaseResponse):
    POIs: list[list[POIAndSemanticDistance]] = Field(description="List of POIs returned by the vector search as well as "
                                                                 "their semantic distance from the semantic for this "
                                                                 "query.")

