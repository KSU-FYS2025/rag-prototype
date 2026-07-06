from pydantic import BaseModel, Field

from app.AI.full_agent.actions_agent.schema import ClarifyAction


class ResolveClarifyAction(BaseModel):
    """
    The schema for resolving a clarification action.
    """

    user_input: str = Field(
        description="The user's input that is used to resolve the clarification action."
    )

    clarification_action: ClarifyAction = Field(
        description="The clarification action that is to be resolved."
    )
