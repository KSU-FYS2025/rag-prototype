from pydantic import BaseModel, Field
from app.AI.schema import NavigationIntent

class RootOutput(BaseModel):
    intent: NavigationIntent = Field()
    confidence: float = Field(ge=0.0, le=1.0)