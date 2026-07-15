from pydantic import BaseModel, Field
from typing import List

from app.AI.schema import BaseResponse
from app.poi.models import POI


class Validation(BaseModel):
    order: int = Field(
        description="The order of which sub-query this belonged to. This MUST match your input."
    )
    selected_pois: List[POI] = Field(description="List of POIs chosen by the LLM.")
    method: str = Field(default="LLM", description="MUST always be LLM")


class POIAndSemanticDistance(BaseModel):
    poi: POI = Field(description="The POI object that this object is associated with")
    semantic_distance: float = Field(
        description="The semantic distance between this POI and the semantic for this "
        "query."
    )


class ParallelOutput(BaseResponse):
    POIs: list[POIAndSemanticDistance] = Field(
        description="List of POIs returned by the vector search as well as "
        "their semantic distance from the semantic for this "
        "query."
    )
