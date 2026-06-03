from pydantic import BaseModel, Field
from typing import List

from app.poi.models import POI

class Validation(BaseModel):
    order: int
    selected_ids: List[POI]
    method: str

class SearchOutput(BaseModel):
    validations: List[Validation]

class Vector(BaseModel):
    dx: float = Field(description="x component of distance between two points")
    dy: float = Field(description="y component of distance between two points")
    dz: float = Field(description="z component of distance between two points")

class DistanceAndVector(BaseModel):
    distance: float = Field(description="Scalar distance between two points")
    vector: Vector = Field(description="Vector between two points")

class DistanceBetweenPOIs(BaseModel):
    poi1: int = Field(description="id of first POI")
    poi2: int = Field(description="id of second POI")
    distance: DistanceAndVector

class DistanceOutput(BaseModel):
    POIs: list[list[tuple[POI, float]]] = Field(description="List of POIs returned by the vector search as well as their"
                                                "semantic distance")
    distances: list[DistanceBetweenPOIs] = Field(description="Distances between POIs. Only includes distances that are "
                                                       "relevant to the problem.")

