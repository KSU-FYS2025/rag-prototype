from typing import Literal

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
                f"[{self.name}] state['{self.state_key}'] is not valid JSON\nRaw value: {raw!r}"
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

type TargetType = Literal["implicit", "general"]
