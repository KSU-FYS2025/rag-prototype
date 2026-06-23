from typing import Generator

from google.adk import Workflow, Context
from google.adk.workflow import node

from app.AI.full_agent.actions_agent.schema import (
    ActionsAgentOutput,
    Command,
    ResolveNearestAction,
    AnswerAction,
    ClarifyAction,
    NavigationAction,
)
from app.AI.full_agent.agent import full_workflow

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


def resolution_helper(
    _actions: list[Command],
) -> Generator[tuple[int, Command] | None, list[Command], None]:
    actions = _actions.copy()
    while actions:
        action_types: list[str] = [action.cmd for action in actions]
        for resolution_stage in RESOLUTION_ORDER:
            index = proper_index(action_types, resolution_stage)
            if index is None:
                continue

            if resolution_stage == "resolve_nearest" and any(
                action.cmd == "clarify" for action in actions
            ):
                continue

            action = actions[index]
            yield index, action
            break

        actions = yield


@node(name="resolve_actions")
async def resolve_actions(ctx: Context, node_input: ActionsAgentOutput):
    actions = node_input.actions.copy()

    for output in resolution_helper(actions):
        assert output is not None
        index, action = output

        match action:
            case ResolveNearestAction() as action:
                resolve_nearest(action)

            case AnswerAction() as action:
                resolve_answer(action)

            case ClarifyAction() as action:
                resolve_clarify(action)

            case NavigationAction() as action:
                resolve_navigation(action)


def resolve_nearest(action: ResolveNearestAction): ...


def resolve_answer(action: AnswerAction): ...


def resolve_clarify(action: ClarifyAction): ...


def resolve_navigation(action: NavigationAction): ...
