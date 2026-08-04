from google.adk.agents.base_agent import BeforeAgentCallback, AfterAgentCallback
from google.adk.agents.llm_agent import AfterModelCallback
from google.adk.agents.llm_agent import BeforeModelCallback
from typing import Optional
from google.adk.agents.llm_agent import InstructionProvider, ToolUnion
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.planners import BuiltInPlanner
from google.genai import types
from google.adk import Agent
from pydantic import BaseModel, Field, ConfigDict

from typing import overload, TypedDict, NotRequired, Unpack
from functools import lru_cache


@lru_cache(maxsize=None)
def load_instructions(agent_name: str) -> str:
    with open(f"app/AI/full_agent/instructions/{agent_name}.md") as f:
        base = f.read()
    with open("app/AI/full_agent/instructions/post_prompt.md") as f:
        post = f.read()
    return base + "\n" + post


def shared_instruction_provider(context: ReadonlyContext) -> str:
    agent_name = context.agent_name
    return load_instructions(agent_name)


planner_defaults = BuiltInPlanner(
    thinking_config=types.ThinkingConfig(
        include_thoughts=False,
    )
)


class AgentConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = Field(
        default="gemini-2.5-flash", description="The model to use for the agent"
    )
    name: str = Field(description="The name of the agent")
    description: str = Field(description="The description of the agent")
    instruction: str | InstructionProvider = Field(
        default=shared_instruction_provider, description="The instruction of the agent"
    )
    planner: BuiltInPlanner = Field(
        default=planner_defaults, description="The planner for the agent"
    )
    input_schema: type[BaseModel] | None = Field(
        default=None, description="The input schema for the agent"
    )
    output_schema: types.SchemaUnion | None = Field(
        default=None, description="The output schema for the agent"
    )
    tools: list[ToolUnion] = Field(
        default_factory=list, description="The tools available to the agent"
    )
    before_model_callback: Optional[BeforeModelCallback] = None
    after_model_callback: Optional[AfterModelCallback] = None
    before_agent_callback: Optional[BeforeAgentCallback] = None
    after_agent_callback: Optional[AfterAgentCallback] = None


class AgentConfigDict(TypedDict):
    model: NotRequired[str]
    name: str
    description: str
    instruction: NotRequired[str | InstructionProvider]
    planner: NotRequired[BuiltInPlanner]
    input_schema: NotRequired[type[BaseModel] | None]
    output_schema: NotRequired[types.SchemaUnion | None]
    tools: NotRequired[list[ToolUnion]]
    before_model_callback: NotRequired[Optional[BeforeModelCallback]]
    after_model_callback: NotRequired[Optional[AfterModelCallback]]
    before_agent_callback: NotRequired[Optional[BeforeAgentCallback]]
    after_agent_callback: NotRequired[Optional[AfterAgentCallback]]


class AgentBuilder:
    """
    Drop-in replacement for adk.Agent with codebase defaults

    Note: This is just a wrapper. When "instantiating" the class it will not
    return an instance of AgentBuilder, but rather adk.Agent.
    """

    @classmethod
    def _builder(cls, config: AgentConfig) -> Agent:
        return Agent(
            model=config.model,
            name=config.name,
            description=config.description,
            instruction=config.instruction,
            planner=config.planner,
            input_schema=config.input_schema,
            output_schema=config.output_schema,
            tools=config.tools,
            before_model_callback=config.before_model_callback,
            after_model_callback=config.after_model_callback,
            before_agent_callback=config.before_agent_callback,
            after_agent_callback=config.after_agent_callback,
        )

    def __new__(
        cls, config: AgentConfig | None = None, **kwargs: Unpack[AgentConfigDict]
    ) -> Agent:
        if not config:
            config = AgentConfig(**kwargs)
        return cls._builder(config)
