import math

from app.AI.full_agent.conversation_agent.schema import ConversationOutput
from app.AI.mock_frontend.schema import ResolveClarifyAction
from app.poi.models import POI
from typing import Generator, Any, Tuple

from google.adk import Workflow, Context
from google.adk.workflow import node
from google.adk import Event
from google.genai import types
from google.adk.events import RequestInput

from app.AI.full_agent.actions_agent.schema import (
    ActionsAgentOutput,
    Command,
    ResolveNearestAction,
    AnswerAction,
    ClarifyAction,
    NavigationAction,
)
from app.AI.full_agent.clarify_agent.agent import clarify_agent
from app.AI.full_agent.agent import full_workflow
from app.database.db import get_db_gen


RESOLUTION_ORDER = [
    "resolve_nearest",
    "answer",
    "clarify",
    "navigation",
]


def proper_index[T](lst: list[T], item: T) -> int | None:
    try:
        return lst.index(item)
    except ValueError:
        return None


def get_distance(this: list[float], other: list[float]) -> float:
    return math.sqrt(
        (this[0] - other[0]) ** 2
        + (this[1] - other[1]) ** 2
        + (this[2] - other[2]) ** 2
    )

@node(name="resolution_helper", rerun_on_resume=True)
async def resolution_helper(ctx: Context):
    actions_in = ctx.state["user:nav_output"]
    actions_parsed = ActionsAgentOutput.model_validate(actions_in)
    actions = actions_parsed.actions

    action_types: list[str] = [action.cmd for action in actions]
    for stage in RESOLUTION_ORDER:
        index = proper_index(action_types, stage)
        # If the current resolution stage does not exist in actions, skip it and go to the next one.
        if index is None:
            continue

        # If the stage is resolve_nearest and any of the actions beforehand are clarify, skip this resolution stage and
        # go to the next one.
        if stage == "resolve_nearest" and any(
            action.cmd == "clarify" for action in actions[:index]
        ):
            continue

        return Event(route="running", output=(index, actions))
    return Event(route="done", output="Finished navigation")

@node(name="resolve_actions", rerun_on_resume=True)
async def resolve_actions(ctx: Context, node_input: Tuple[int, list[Command]]):
    index, actions = node_input
    action = actions[index]

    resolved_action = None
    match action:
        case ResolveNearestAction() as action:
            resolved_action = resolve_nearest(
                action, None if index == 0 else actions[index - 1]
            )

        case AnswerAction() as action:
            resolved_action = resolve_answer(action)

        case ClarifyAction() as action:
            resolved_action = await ctx.run_node(resolve_clarify, action)

        case NavigationAction() as action:
            resolved_action = resolve_navigation(action)

    # If the action resolves into another action, signal for post_res to replace it
    if isinstance(resolved_action, Command.__value__):
        return Event(output=(index, resolved_action))

    # If the action resolves into an event, return it.
    if isinstance(resolved_action, Event):
        return resolved_action


def resolve_nearest(
    action: ResolveNearestAction, previous_action: Command | None = None
) -> NavigationAction:
    start_position: list[float] = [0, 0, 0]
    if previous_action and isinstance(previous_action, NavigationAction):
        prev_id = previous_action.id
        with get_db_gen() as db:
            res = db.search(
                collection_name="poi",
                limit=1,
                filter=f'identification == "{prev_id}"',
            )
        prev_poi = POI(**[hit for x in res for hit in x if hit][0]["entity"])
        start_position = prev_poi.position

    # Now that we have start_position, we have to get the positions for each POI
    poi_ids = action.candidate_ids
    with get_db_gen() as db:
        res = db.query(
            collection_name="poi",
            filter=f"identification in [{','.join(map(str, poi_ids))}]",
        )

    pois = [POI(**hit["entity"]) for x in res for hit in x if hit]
    poi_distances = [(get_distance(poi.position, start_position), poi) for poi in pois]
    distances_sorted = sorted(poi_distances, key=lambda x: x[0])
    return NavigationAction(
        order=action.order,
        target_label=distances_sorted[0][1].name,
        id=distances_sorted[0][1].id,
        # Eventually, consider replacing this with an LLM generated message
        response=f"Guiding you to {distances_sorted[0][1].name}.",
    )


def resolve_answer(action: AnswerAction) -> Event:
    return Event(content=types.Content(parts=[types.Part.from_text(text=action.text)]))

def resolve_navigation(action: NavigationAction) -> Event:
    return Event(
        content=types.Content(parts=[types.Part.from_text(text=action.response)])
    )

def resolve_clarify(action: ClarifyAction) -> Event:
    return Event(
        content=types.Content(parts=[types.Part.from_text(text=f"CLARIFY: {action.prompt}")])
    )

@node(name="post_res", rerun_on_resume=True)
def post_res(ctx: Context, node_input: tuple[int, Command]):
    ...

@node(name="save_to_state", rerun_on_resume=True)
def save_to_state(ctx: Context, node_input: ActionsAgentOutput):
    ctx.state["user:nav_output"] = node_input

@node(name="resolve_conversation", rerun_on_resume=True)
def resolve_conversation(ctx: Context, node_input: ActionsAgentOutput | ConversationOutput):
    if isinstance(node_input, ConversationOutput):
        return Event(route="conversation", output=node_input)
    return Event(route="navigation", output=node_input)

@node(name="skip_nav", rerun_on_resume=True)
def skip_nav(ctx: Context, node_input: ActionsAgentOutput):
    ...

@node(name="setup_res", rerun_on_resume=True)
def setup_res(ctx: Context, node_input: ActionsAgentOutput):
    ...

@node(name="echo", rerun_on_resume=True)
def echo(ctx: Context, node_input: Any):
    return Event(output=node_input)

mock_frontend_workflow = Workflow(
    name="mock_frontend",
    edges=[
        ("START", skip_nav),
        (skip_nav, {
            "skip": (setup_res, resolve_actions),
            "perform": (full_workflow, resolve_conversation),
        }),
        (resolve_actions, post_res),
        (resolve_conversation, {
            "conversation": echo,
            "navigation": (save_to_state, resolution_helper),
        }),
        (resolution_helper, {
            "done": echo,
            "running": resolve_actions,
        }),
        (post_res, {
            "clarify": echo,
            "other": resolution_helper,
        })
    ],
)

agent = mock_frontend_workflow
root_agent = mock_frontend_workflow
