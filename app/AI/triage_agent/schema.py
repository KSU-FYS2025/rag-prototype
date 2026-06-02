from pydantic import BaseModel

from app.AI.schema import TargetType, NavigationIntent
from typing import List

class QueryClassifier(BaseModel):
    order: int
    intent: NavigationIntent
    target_type: TargetType
    semantics: str
    source: str

class TriageAgentOutput(BaseModel):
    targets: List[QueryClassifier]
    extraction_method: str
