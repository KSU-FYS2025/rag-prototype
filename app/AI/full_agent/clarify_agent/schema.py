from pydantic import BaseModel, Field

from app.AI.full_agent.actions_agent.schema import ClarifyAction, Command


class ClarifyInput(BaseModel):
    user_input: str = Field(
        description="The user's input. Use this to resolve the clarification problem."
    )
    clarification_action: ClarifyAction = Field(
        description="The clarification action you are to resolve."
    )


class ClarifyOutput(BaseModel):
    action: Command = Field(
        description="The command you are suggesting should replace the clarification action based"
        "on the user's input."
    )
