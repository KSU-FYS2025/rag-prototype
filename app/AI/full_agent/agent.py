from typing import Any

from google.adk.workflow import node, JoinNode
from google.adk import Context, Workflow, Event

import logging
import asyncio

from pydantic import BaseModel

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.search_agent.agent import (
    validate_pois,
    search_poi_node,
    synthesis_agent,
)
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput
from app.AI.full_agent.conversation_agent.agent import conversation_agent
from app.AI.full_agent.actions_agent.agent import actions_agent
from app.AI.full_agent.root_agent.agent import root_agent as intent_agent
from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.agent import triage_agent
from app.AI.schema import NavigationIntent
from google.genai import types


@node(name="navigation_router", rerun_on_resume=True)
def navigation_router(node_input: RootOutput):
    if node_input.intent == NavigationIntent.CONVERSATIONAL:
        return Event(route="conversational")
    else:
        return Event(route="navigation")


def make_base_workflow(i: int) -> Workflow:
    return Workflow(
        name=f"BaseWorkflow_{i}",
        edges=[
            (
                "START",
                search_poi_node,
                validate_pois,
                synthesis_agent,
                actions_agent,
            ),
        ],
    )


@node(name="router", rerun_on_resume=True)
async def parallel_router(ctx: Context, node_input: TriageAgentOutput):
    node_input = TriageAgentOutput.model_validate(node_input.model_dump(mode="json"))

    logging.info(f"parallel_router called with {node_input}")
    workflows = [make_base_workflow(item.order) for item in node_input.targets]

    tasks = [ctx.run_node(wf, item) for wf, item in zip(workflows, node_input.targets)]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Extract the output from each event
    extracted_results = []
    for i, r in enumerate(results):
        if hasattr(r, "output"):
            extracted_results.append(r.output)
        else:
            extracted_results.append(r)

    logging.info(f"Extracted results from tasks: {extracted_results}")

    failures = [r for r in extracted_results if isinstance(r, Exception)]
    if failures:
        raise RuntimeError(f"One or more sub-workflows failed: {failures}")

    # Filter out None values and ensure they are valid Commands
    valid_actions = []
    for i, r in enumerate(extracted_results):
        if r is None:
            logging.warning(
                f"Sub-workflow {i} returned None. This usually means actions_agent failed to produce a Command."
            )
            continue

        # actions_agent doesn't know which target it handled, so take the order
        # from the target itself rather than trusting the LLM's value.
        target_order = node_input.targets[i].order
        if isinstance(r, dict):
            r = {**r, "order": target_order}
        elif isinstance(r, BaseModel):
            r = r.model_copy(update={"order": target_order})

        valid_actions.append(r)

    if not valid_actions and node_input.targets:
        error_msg = f"All {len(node_input.targets)} sub-workflows failed to return an action. Query: {ctx.state['user_query']}"
        logging.error(error_msg)
        # We might want to raise an error here to prevent empty actions if that's not allowed
        # But let's see what ActionsAgentOutput says. It allows List[Command].

    if len(valid_actions) < len(extracted_results):
        logging.warning(
            f"Filtered out {len(extracted_results) - len(valid_actions)} invalid/None actions: {extracted_results}"
        )

    try:
        results_obj = ActionsAgentOutput(
            actions=valid_actions,
        )
    except Exception as e:
        logging.error(
            f"Failed to create ActionsAgentOutput. Query: {ctx.state['user_query']}, Actions: {valid_actions}"
        )
        # If we have no valid actions due to filtering but expected some,
        # or if valid_actions still has something Pydantic does not like.
        raise e

    # Content makes the combined action list visible to adk eval, which only
    # records events that have content.
    return Event(
        output=results_obj,
        content=types.Content(
            role="model", parts=[types.Part(text=results_obj.model_dump_json())]
        ),
        partial=True,
    )


@node(name="capture_query", rerun_on_resume=True)
async def capture_query(ctx: Context, node_input: Any):
    if isinstance(node_input, types.Content):
        text = "".join(p.text or "" for p in node_input.parts or [])
    elif isinstance(node_input, dict):
        text = str(node_input.get("request", ""))
    else:
        text = str(node_input or "")

    text = text.strip()
    ctx.state["user_query"] = text
    return Event(output=text)


navigation_workflow = Workflow(
    name="navigation_workflow",
    edges=[("START", triage_agent), (triage_agent, parallel_router)],
)

full_workflow = Workflow(
    name="full_workflow",
    edges=[
        ("START", capture_query, intent_agent, navigation_router),
        (
            navigation_router,
            {"conversational": conversation_agent, "navigation": navigation_workflow},
        ),
    ],
    input_schema=str,
)

root_agent = full_workflow
agent = full_workflow
