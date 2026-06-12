from pydantic import Field

from app.AI.schema import BaseResponse


class ConversationOutput(BaseResponse):
    response: str = Field(description="What your response is.")