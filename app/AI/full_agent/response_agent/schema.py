from typing import List

from pydantic import BaseModel, Field
from enum import Enum

class FinalResponse(BaseModel):
    response: str
    actions: List[Action]

class Command(str, Enum):
    """
    The command that the Unity runner will take.
    NAVIGATION/ navigation - Unit runner will guide the user to an id specified outside of this enum.
    """
    # TODO: Implement route to nearest using Unity's calculated distances
    NAVIGATION = "navigation"

class Action(BaseModel):
    order: int = Field(ge=0, description="The order of the Action")
    cmd: Command
    id: int = Field(description="The id of the POI the user will be guided to")
