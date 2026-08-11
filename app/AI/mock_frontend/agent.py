import math

from app.AI.full_agent.clarify_agent.schema import ClarifyInput
from app.AI.full_agent.conversation_agent.schema import ConversationOutput
from app.poi.models import POI
from typing import Tuple

from google.adk import Workflow, Context
from google.adk.workflow import node
from google.adk import Event
from google.genai import types

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


def get_last_user_input(ctx: Context) -> str | None:
    last_user_event = next(
        (event for event in reversed(ctx.session.events) if event.author == "user"),
        None,
    )
    if last_user_event and last_user_event.content and last_user_event.content.parts:
        return last_user_event.content.parts[0].text
    return None


def resolve_nearest_helper(
    actions: ActionsAgentOutput, action_to_resolve: ResolveNearestAction
):
    index = proper_index(actions.actions, action_to_resolve)
    assert index is not None

    previous_actions: list[str] = [action.cmd for action in actions.actions[:index]]
    for pos, action in enumerate(reversed(previous_actions)):
        if action == "navigation":
            correct_index = index - 1 - pos
            return actions.actions[correct_index]
    return None


def resolution_helper(actions: ActionsAgentOutput):
    action_types: list[str] = [action.cmd for action in actions.actions]
    for stage in RESOLUTION_ORDER:
        index = proper_index(action_types, stage)
        # If the current resolution stage does not exist in actions, skip it and go to the next one.
        if index is None:
            continue

        # If the stage is resolve_nearest and any of the actions beforehand are clarify, skip this resolution stage and
        # go to the next one.
        if stage == "resolve_nearest" and any(
            action.cmd == "clarify" for action in actions.actions[:index]
        ):
            continue

        return index, actions
    return Event(
        content=types.Content(parts=[types.Part.from_text(text="Finished navigation")])
    )


@node(name="resolve_actions", rerun_on_resume=True)
async def resolve_actions(ctx: Context, node_input: ActionsAgentOutput):
    helper_output = resolution_helper(node_input)
    if isinstance(helper_output, Event):
        yield helper_output
        return

    index, actions = helper_output
    action = actions.actions[index]

    match action:
        case ResolveNearestAction() as action:
            last_index = resolve_nearest_helper(actions, action)
            resolved_action = resolve_nearest(action, last_index)

            yield Event(route="commit", output=(actions, action, resolved_action))

        case AnswerAction() as action:
            yield answer_respond(action)
            yield Event(route="commit", output=(actions, action, None))

        case ClarifyAction() as action:
            yield clarify_respond(action)
            yield Event(route="clarify", output=(actions, action))

        case NavigationAction() as action:
            yield navigation_respond(action)
            yield Event(route="commit", output=(actions, action, None))
    return


def resolve_nearest(
    action: ResolveNearestAction, previous_action: Command | None = None
) -> NavigationAction:
    start_position: list[float] = [0, 0, 0]
    if previous_action and isinstance(previous_action, NavigationAction):
        prev_id = previous_action.id
        with get_db_gen() as db:
            db.load_collection("poi")
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
        db.load_collection("poi")
        res = db.query(
            collection_name="poi",
            filter=f"identification in [{','.join(map(str, poi_ids))}]",
        )

    pois = [POI(**hit) for hit in res]
    poi_distances = [(get_distance(poi.position, start_position), poi) for poi in pois]
    distances_sorted = sorted(poi_distances, key=lambda x: x[0])
    return NavigationAction(
        order=action.order,
        target_label=distances_sorted[0][1].name,
        id=distances_sorted[0][1].id,
        # Eventually, consider replacing this with an LLM generated message
        response=f"Guiding you to {distances_sorted[0][1].name}.",
    )


def answer_respond(action: AnswerAction) -> Event:
    return Event(content=types.Content(parts=[types.Part.from_text(text=action.text)]))


def navigation_respond(action: NavigationAction) -> Event:
    return Event(
        content=types.Content(parts=[types.Part.from_text(text=action.response)])
    )


def clarify_respond(action: ClarifyAction) -> Event:
    return Event(
        content=types.Content(parts=[types.Part.from_text(text=action.prompt)])
    )


@node(name="commit_change", rerun_on_resume=True)
def commit_change(
    ctx: Context, node_input: Tuple[ActionsAgentOutput, Command, Command | None]
):
    actions, original_action, changed_action = node_input

    if changed_action is None:
        actions.actions.remove(original_action)

    else:
        index = actions.actions.index(original_action)
        actions.actions[index] = changed_action

    return Event(output=actions)


@node(name="save_to_state", rerun_on_resume=True)
def save_to_state(ctx: Context, node_input: Tuple[ActionsAgentOutput, Command]):
    actions, action_to_resolve = node_input
    return Event(
        state={
            "user:actions": actions.model_dump(),
            "user:action_to_resolve": action_to_resolve.model_dump(),
            "user:resume_resolution": True,
        }
    )


@node(name="load_from_state", rerun_on_resume=True)
def load_from_state(ctx: Context):
    actions = ctx.state.get("user:actions")
    action_to_resolve = ctx.state.get("user:action_to_resolve")
    actions = ActionsAgentOutput.model_validate(actions)
    action_to_resolve = ClarifyAction.model_validate(action_to_resolve)
    return Event(
        output=(actions, action_to_resolve),
        state={
            "user:actions": None,
            "user:action_to_resolve": None,
        },
    )


@node(name="resume_resolution", rerun_on_resume=True)
def resume_resolution(ctx: Context):
    resume = ctx.state.get("user:resume_resolution")
    if resume:
        return Event(
            route="resume",
            state={
                "user:resume_resolution": False,
            },
        )
    return Event(route="full_workflow")


@node(name="resolve_clarify", rerun_on_resume=True)
async def resolve_clarify(
    ctx: Context, node_input: Tuple[ActionsAgentOutput, ClarifyAction]
):
    actions, action_to_resolve = node_input
    user_input = get_last_user_input(ctx)
    assert user_input is not None

    resolved_action = await ctx.run_node(
        clarify_agent,
        ClarifyInput(user_input=user_input, clarification_action=action_to_resolve),
    )

    yield Event(output=(actions, action_to_resolve, resolved_action))


@node(name="resolve_conversation", rerun_on_resume=True)
def resolve_conversation(
    ctx: Context, node_input: ActionsAgentOutput | ConversationOutput
):
    if isinstance(node_input, ConversationOutput):
        return Event(
            content=types.Content(
                parts=[types.Part.from_text(text=node_input.response)]
            )
        )
    return Event(route="navigation", output=node_input)


mock_frontend_workflow = Workflow(
    name="mock_frontend",
    edges=[
        ("START", resume_resolution),
        (
            resume_resolution,
            {
                "resume": load_from_state,
                "full_workflow": full_workflow,
            },
        ),
        (load_from_state, resolve_clarify, commit_change),
        (full_workflow, resolve_conversation),
        (resolve_conversation, {"navigation": resolve_actions}),
        (
            resolve_actions,
            {
                "commit": commit_change,
                "clarify": save_to_state,
            },
        ),
        (commit_change, resolve_actions),
    ],
)

agent = mock_frontend_workflow
root_agent = mock_frontend_workflow
