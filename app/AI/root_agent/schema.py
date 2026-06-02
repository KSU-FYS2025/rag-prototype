from pydantic import BaseModel, Field

from app.AI.schema import NavigationIntent


class RootOutput(BaseModel):
    intent: NavigationIntent = Field(description="What the user's query is classified as.\n"
                                                 "NAV_GUIDE or navigation_guidance is when the user asks, either"
                                                 "implicitly or explicitly to be guided to some place(s).\n"
                                                 "NAV_QUERY or navigation_query is when the user asks about a place(s)"
                                                 "but does not explicitly wish to be guided to that place."
                                                 "CONVERSATIONAL or conversational is when the user's query is"
                                                 "just conversational and does not require additional information.")
    confidence: float = Field(ge=0.0, le=1.0,
                              description="How confident the AI model is in it's choice of navigation intent")