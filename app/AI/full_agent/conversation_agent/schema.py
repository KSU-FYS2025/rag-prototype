from pydantic import Field, BaseModel


class ConversationOutput(BaseModel):
    response: str = Field(description="What your response is.")
