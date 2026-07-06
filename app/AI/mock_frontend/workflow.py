import math

from app.poi.models import POI
from typing import Generator

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

workflow = Workflow(name="mock_frontend", edges=[("START", full_workflow)])

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


def resolution_helper(
    _actions: list[Command],
) -> Generator[tuple[int, Command] | None, list[Command], None]:
    actions = _actions.copy()
    while actions:
        action_types: list[str] = [action.cmd for action in actions]
        for resolution_stage in RESOLUTION_ORDER:
            index = proper_index(action_types, resolution_stage)
            # If the current resolution stage does not exist in actions, skip it and go to the next one.
            if index is None:
                continue

            # If the resolution_stage is resolve nearest, and any of the actions beforehand are clarify, skip this
            # resolution stage and go to the next one.
            if resolution_stage == "resolve_nearest" and any(
                action.cmd == "clarify" for action in actions[:index]
            ):
                continue

            action = actions[index]
            yield index, action
            break

        actions = yield


@node(name="resolve_actions")
async def resolve_actions(ctx: Context, node_input: ActionsAgentOutput):
    actions = node_input.actions.copy()

    res_gen = resolution_helper(actions)

    for output in res_gen:
        assert output is not None
        index, action = output

        resolved_action = None
        match action:
            case ResolveNearestAction() as action:
                resolved_action = resolve_nearest(
                    action, None if index == 0 else actions[index - 1]
                )

            case AnswerAction() as action:
                resolved_action = resolve_answer(action)

            case ClarifyAction() as action:
                resolved_action = await resolve_clarify(action, ctx)

            case NavigationAction() as action:
                resolved_action = resolve_navigation(action)

        # If the action resolves into another action, replace the action with the new one
        if isinstance(resolved_action, Command.__value__):
            actions[index] = resolved_action

        # If the action resolves into an event, yield it.
        if isinstance(resolved_action, Event):
            yield resolved_action

        res_gen.send(actions)


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


def resolve_clarify(action: ClarifyAction, ctx: Context):
    user_input = RequestInput(message=action.prompt)
    return ctx.run_node(clarify_agent, user_input)


def resolve_navigation(action: NavigationAction) -> Event:
    return Event(
        content=types.Content(parts=[types.Part.from_text(text=action.response)])
    )


agent = workflow
root_agent = workflow
