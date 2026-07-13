from typing import List, Literal

from pydantic import BaseModel, Field

from app.AI.schema import BaseResponse


class Action(BaseModel):
    order: int = Field(ge=0, description="The order of the Action")


class NavigationAction(Action):
    """
    This action should be taken if there is exactly one poi inside the selected_pois tag.
    """

    cmd: Literal["navigation"] = "navigation"
    id: int = Field(description="The id of the POI the user will be guided to")
    target_label: str = Field(
        description="The semantic information of the query the user will be guided to"
    )
    response: str = Field(
        description="The response of the action. Will be spoken to the user."
    )


class ResolveNearestAction(Action):
    """
    This action should be taken if there is multiple pois inside the selected_pois tag and the result of the navigation
    is not impacted by user preferences
    EX: Things like gender, where/ what classes they are taking are, etc.
    """

    cmd: Literal["resolve_nearest"] = "resolve_nearest"
    candidate_ids: List[int] = Field(
        description="The ids the Unity client will decide between."
    )
    target_label: str = Field(
        description="The semantic information of the query the user will be guided to"
    )


class AnswerAction(Action):
    """
    This action should be taken if the user asked a question and did not request guidance somewhere. Answer their
    question using the information provided to you in the selected_pois tag. When answering about where something is,
    don't just tell the user about the coordinates of where it is. Give information about where it is relative to
    something else. You may use the following information below to guide your response:
    In the atrium building:
        * The first number of any room number is the floor it's located on
        * The second number of any room number is which hallway it's located on.
    """

    cmd: Literal["answer"] = "answer"
    text: str = Field(description="The text of the Answer")
    source_ids: List[int] = Field(
        description="The poi ids the user was questioning about"
    )


class ClarificationSuggestion(BaseModel):
    id: int = Field(description="The id of the POI you are suggesting")
    name: str = Field(description="The name of the POI you are suggesting")


class ClarifyAction(Action):
    """
    This action should be taken if there is either no POIs inside the selected_pois tag or there are multiple and the
    outcome could be impacted by user preferences. In this case, the agent should ask the user for clarification.
    Remember: user preferences can include gender. For example, if a user asks to be guided to the restroom/ bathroom
    but do not specify if it's the men's or women's restroom, you must use this action to ask them which one.
    """

    cmd: Literal["clarify"] = "clarify"
    unresolved_target: str = Field(
        description="The semantic information of the poi the user queried"
    )
    reason: str = Field(
        description="The reason the agent was not able to resolve this query."
    )
    suggestions: List[ClarificationSuggestion] = Field(
        description="Suggestions for POIs that exist"
    )
    prompt: str = Field(
        description="The prompt that will be shown to the user. Must include the reason inside the "
        "reason field formed as a question to ask to the user."
    )


Command = NavigationAction | ResolveNearestAction | AnswerAction | ClarifyAction


class ActionsAgentOutput(BaseResponse):
    actions: List[Command] = Field(
        description="The list of actions the Unity runner will take. This should be in the "
        "order the Unity runner takes them."
    )
