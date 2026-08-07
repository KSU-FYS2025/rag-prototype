from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput
from app.AI.full_agent.skills.skills import load


def take_out_fence(text: str) -> str:
    block_start = text.find("```json")
    if block_start < 0:
        return text

    block_start += len("```json")
    block_end = text.find("```", block_start)
    new_str = text[block_start:block_end]

    return new_str


def strip_json_fences(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> LlmResponse | None:
    if llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text:
                part.text = take_out_fence(part.text)

    return llm_response


triage_agent = AgentBuilder(
    name="triage_agent",
    description="An agent that separates and classifies queries within a full user query",
    input_schema=RootOutput,
    output_schema=TriageAgentOutput,
    after_model_callback=strip_json_fences,
    tools=[
        load(
            (
                "milvus-json-operators",
                "milvus-array-operators",
                "milvus-struct-array-operators",
                "milvus-geometry-operators",
                "milvus-random-sampling",
                "milvus-filter-templating",
            )
        )
    ],
)
