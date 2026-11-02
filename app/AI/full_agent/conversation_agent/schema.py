from pydantic import BaseModel, Field


class ConversationOutput(BaseModel):
    response: str = Field(description="What your response is.")
