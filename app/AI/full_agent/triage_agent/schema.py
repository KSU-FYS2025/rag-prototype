from pydantic import BaseModel, Field

from app.AI.schema import TargetType, NavigationIntent, BaseResponse
from typing import List


class QueryClassifier(BaseModel):
    order: int = Field(
        ge=0,
        description="The index of this item in the targets list. Start indexing at 0.",
    )
    intent: NavigationIntent
    target_type: TargetType
    filter: str = Field(
        description="A SQL-Like filter that is used to further refine the output of a vector search "
        "inside pymilvus. DO NOT REFERENCE THE TYPE FIELD INSIDE THIS. NEVER PUT TYPE HERE. "
        "This MUST be a string that uses double quotes on the outside."
    )
    semantics: str = Field(
        description="Semantic information about the query that can be used to run a vector search. "
        "Include things like what the Point of Interest is, and any helpful explicit "
        "information.\n",
        # examples="EX1: ROOM 2131\nEX2: bathroom, third floor",
    )
    source: str = Field(default="LLM", description="MUST always be LLM")


class TriageAgentOutput(BaseResponse):
    targets: List[QueryClassifier] = Field(
        description="A list of query classifiers that can be used to run a vector search "
    )
    extraction_method: str = Field(default="LLM", description="MUST always be LLM")
