from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from enum import Enum
import json

class BaseResponse(BaseModel):
    user_query: str = Field(description="The user's original query. MUST match the user's query exactly.")

class NavigationIntent(str, Enum):
    """
    Intent of the user at each step
    NAV_QUERY/ navigation_query - User has a query relating to navigation, but does not wish to be guided yet
    NAV_GUIDE/ navigation_guidance - User wishes to be guided somewhere
    CONVERSATIONAL/ conversational - User converses with the AI Agent, no navigation or additional information is needed
    CLARIFICATION/ clarification - AI Agent requires clarification from the user
    """
    NAV_QUERY = "navigation_query"
    NAV_GUIDE = "navigation_guidance"
    CONVERSATIONAL = "conversational"
    CLARIFICATION = "clarification"

class TargetType(str, Enum):
    """
    The type of the navigation target
    IMPLICIT/ implicit - User does not directly name the room but wishes to be guided there
    EXPLICIT/ explicit - User directly mentions the name/ number of the room they wish to be guided to
    """
    IMPLICIT = "implicit"
    EXPLICIT = "explicit"

