from typing import List

from pydantic import BaseModel, Field

from app.AI.schema import BaseResponse, NavigationIntent, TargetType


class QueryClassifier(BaseModel):
    order: int = Field(
        ge=0,
        description="The index of this item in the targets list. Start indexing at 0.",
    )
    intent: NavigationIntent
    target_type: TargetType
    filter: str = Field(
        description="Milvus filter expression using name, type or parentName, or an empty string."
    )
    semantics: str = Field(
        description="A short noun phrase naming the place for the vector search, e.g. 'Room 3431' or 'restroom'."
    )
    source: str = Field(default="LLM", description="MUST always be LLM")


class TriageAgentOutput(BaseModel):
    targets: List[QueryClassifier] = Field(
        description="A list of query classifiers that can be used to run a vector search "
    )
    extraction_method: str = Field(default="LLM", description="MUST always be LLM")
