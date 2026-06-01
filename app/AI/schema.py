from pydantic import BaseModel, Field, ValidationError
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from enum import Enum
import json

class ValidationAgent(BaseAgent):
    state_key: str
    schema: type[BaseModel]

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(self, ctx: InvocationContext):
        raw = ctx.session.state.get(self.state_key)

        if raw is None:
            raise ValueError(f"State key [{self.state_key}] is either missing or None! Check upstream models!")

        if isinstance(raw, str):
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            try:
                parsed_dict = json.loads(cleaned)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"[{self.name}] state['{self.state_key}'] is not valid JSON: {e}\nRaw value: {raw!r}"
                )
        elif isinstance(raw, dict):
            parsed_dict = raw
        else:
            raise ValueError(
                f"[{self.name}] state['{self.state_key}'] is not valid JSON: {e}\nRaw value: {raw!r}"
            )

        try:
            validated = self.schema.model_validate(parsed_dict)
        except ValidationError as e:
            raise ValueError(
                f"[{self.name}] Pydantic validation failed for '{self.state_key}':\n{e}"
            )
        # This may be unsafe, consider changing this
        ctx.session.state[self.state_key] = validated.model_dump_json()

        yield Event(
            author=self.name,
            content=None,
            actions=EventActions()
        )


class NavigationIntent(str, Enum):
    NAV_QUERY = "navigation_query"
    NAV_GUIDE = "navigation_guidance"
    CONVERSATIONAL = "conversational"

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

