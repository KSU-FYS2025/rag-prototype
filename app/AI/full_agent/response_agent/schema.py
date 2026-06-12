from typing import List, Literal, Annotated, Union

from pydantic import BaseModel, Field, Discriminator, Tag
from enum import Enum

class Action(BaseModel):
    order: int = Field(ge=0, description="The order of the Action")

class NavigationAction(Action):
    cmd: Literal["navigation"] = "navigation"
    id: int = Field(description="The id of the POI the user will be guided to")
    target_label: str = Field(description="The semantic information of the query the user will be guided to")

class ResolveNearestAction(Action):
    cmd: Literal["resolve_nearest"] = "resolve_nearest"
    candidate_ids: List[int] = Field(description="The ids the Unity client will decide between.")
    target_label: str = Field(description="The semantic information of the query the user will be guided to")

class AnswerAction(Action):
    cmd: Literal["answer"] = "answer"
    text: str = Field(description="The text of the Answer")
    source_ids: List[int] = Field(description="The poi ids the user was questioning about")

class ClarificationSuggestion(BaseModel):
    id: int = Field(description="The id of the POI you are suggesting")
    name: str = Field(description="The name of the POI you are suggesting")

class ClarifyAction(Action):
    cmd: Literal["clarify"] = "clarify"
    unresolved_target: str = Field(description="The semantic information of the poi the user queried")
    reason: str = Field(description="The reason the agent was not able to resolve this query.")
    suggestions: List[ClarificationSuggestion] = Field(description="Suggestions for POIs that exist")
    prompt: str = Field(description="The prompt that will be shown to the user. Must include all the suggestions in "
                                    "suggestions.")

Command = Annotated[
    Union[
        Annotated[NavigationAction, Tag("navigation")],
        Annotated[ResolveNearestAction, Tag("resolve_nearest")],
        Annotated[AnswerAction, Tag("answer")],
        Annotated[ClarifyAction, Tag("clarify")]
    ],
    Discriminator("cmd")
]

class ResponseAgentOutput(BaseModel):
    response: str = Field(description="The final response from the Unity runner that will be spoken to the user.")
    actions: List[Command] = Field(description="The list of actions the Unity runner will take. This should be in the "
                                               "order the Unity runner takes them.")
