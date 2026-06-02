from pydantic import BaseModel, Field

from app.AI.schema import TargetType, NavigationIntent
from typing import List

class QueryClassifier(BaseModel):
    order: int = Field(ge=1)
    intent: NavigationIntent
    target_type: TargetType
    filter: str = Field(description="A SQL-Like filter that is used to further refine the output of a vector search "
                                    "inside pymilvus.")
    semantics: str = Field(description="Semantic information about the query that can be used to run a vector search. "
                                       "Include things like what the Point of Interest is, and any helpful explicit "
                                       "information.\n"
                                       "EX1: ROOM 2131\n"
                                       "EX2: bathroom, third floor")
    source: str = Field(description="Should always be LLM")

class TriageAgentOutput(BaseModel):
    targets: List[QueryClassifier] = Field(description="A list of query classifiers that can be used to run a vector search ")
    extraction_method: str = Field(description="Should always be LLM")
