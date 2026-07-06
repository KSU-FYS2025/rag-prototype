from google.adk.planners import BuiltInPlanner
from google.genai import types

planner_defaults = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(
        include_thoughts=False,
    )
)
