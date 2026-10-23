"""Custom ADK eval metric that judges navigation results against the POI database.

Registered in ``app/AI/full_agent/test_config.json`` as ``subquery_correctness``.

Score encoding per eval case (taken from the last invocation that produced actions):
    1.0 -> every sub-query correct   (PASSED)
    0.5 -> some sub-queries correct  (FAILED)
    0.0 -> no sub-queries correct    (FAILED)

Per-sub-query verdicts and reasons are stored in ``rubric_scores``.
"""

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional

from google import genai
from google.adk.evaluation.eval_case import ConversationScenario, Invocation
from google.adk.evaluation.eval_metrics import (
    EvalMetric,
    EvalStatus,
    Interval,
    MetricInfo,
    MetricValueInfo,
    RubricScore,
)
from google.adk.evaluation.evaluator import (
    EvaluationResult,
    Evaluator,
    PerInvocationResult,
)
from google.adk.evaluation.metric_evaluator_registry import (
    DEFAULT_METRIC_EVALUATOR_REGISTRY,
)
from google.genai import types
from pydantic import BaseModel

# judge.py -> evals -> full_agent -> AI -> app -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[4]
POI_PATH = PROJECT_ROOT / "UpdatedFloorsAndFireinteraction_POIs.json"
QUERIES_PATH = PROJECT_ROOT / "results" / "ExcelQueries.json"

JUDGE_MODEL = "gemini-2.5-flash"
JUDGE_SAMPLES = 3
ROOM_RE = re.compile(r"\broom\s+([A-Z]?\d{3,4})\b", re.IGNORECASE)

CATEGORY_RULES = {
    "Explicit one-step": (
        "One sub-query naming a specific place. It must resolve to that exact POI. "
        "'Where is ...' questions may be answered with an 'answer' action instead of navigation."
    ),
    "Implicit one-step": (
        "One sub-query describing a place. Any POI that genuinely matches the description is "
        "acceptable; 'resolve_nearest' is acceptable when several POIs match. A 'clarify' is "
        "correct only when the outcome depends on a user preference (e.g. which restroom)."
    ),
    "Explicit multi-step": (
        "Several sub-queries in the order given. Each must resolve to its exact POI, in the same "
        "order as the user's request."
    ),
    "Implicit multi-step": (
        "Several described places in the order given. Judge each against the database "
        "independently; the order of actions must match the user's request."
    ),
    "Erroneous prompts": (
        "The requested place does not exist in the database. The only correct action is "
        "'clarify'. Navigating to, or answering with, any POI is incorrect."
    ),
}


class SubQueryVerdict(BaseModel):
    sub_query: str
    correct: bool
    acceptable_ids: list[int]
    reason: str


class Verdict(BaseModel):
    sub_queries: list[SubQueryVerdict]


@lru_cache(maxsize=1)
def load_pois() -> dict[int, dict]:
    pois = json.loads(POI_PATH.read_text(encoding="utf-8"))["pois"]
    # Only what the judge needs; position/rotation data is left out.
    return {
        p["identification"]: {
            "id": p["identification"],
            "name": p["name"],
            "type": p["type"],
            "floor": p["parentName"],
            "description": p.get("description", ""),
        }
        for p in pois
    }


@lru_cache(maxsize=1)
def load_categories() -> dict[str, str]:
    pairs = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    return {query.strip(): category for query, category in pairs}


def _text(content: Optional[types.Content]) -> str:
    if not content or not content.parts:
        return ""
    texts = [p.text for p in content.parts if p.text and not p.thought]
    return texts[-1] if texts else ""


def _as_command(value: object) -> Optional[dict]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if isinstance(value, dict) and "cmd" in value:
        return value
    return None


def _commands_in(content: Optional[types.Content]) -> list[dict]:
    commands = []
    for part in (content.parts if content and content.parts else []):
        if part.thought:
            continue
        if part.text and (cmd := _as_command(part.text)):
            commands.append(cmd)
        if part.function_call and part.function_call.name == "set_model_response":
            if cmd := _as_command(dict(part.function_call.args or {})):
                commands.append(cmd)
    return commands


def _router_actions(content: Optional[types.Content]) -> Optional[list[dict]]:
    """Returns the action list from the router's ActionsAgentOutput, if present."""
    for part in reversed(content.parts if content and content.parts else []):
        if not part.text or part.thought:
            continue
        try:
            data = json.loads(part.text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            return [a for a in data["actions"] if isinstance(a, dict)]
    return None


def collect_actions(inv: Invocation) -> list[dict]:
    """Returns the workflow's action list for one invocation.

    Prefers the router's combined ActionsAgentOutput, whose order fields come
    from the targets. Falls back to each sub-workflow's actions_agent output
    (one Command each) for runs recorded before the router emitted content.
    """
    events = getattr(inv.intermediate_data, "invocation_events", None) or []
    for content in [inv.final_response, *(e.content for e in reversed(events) if e.author == "router")]:
        if (actions := _router_actions(content)) is not None:
            return actions

    found: list[dict] = []
    for event in events:
        if event.author == "actions_agent":
            found.extend(_commands_in(event.content))
    found.extend(_commands_in(inv.final_response))

    # actions_agent often repeats the same order for every target, so only drop
    # exact duplicates and keep event order among equal orders.
    unique: list[dict] = []
    for cmd in found:
        if cmd not in unique:
            unique.append(cmd)
    return sorted(unique, key=lambda cmd: cmd.get("order", 0))


def _referenced_ids(action: dict) -> list[int]:
    cmd = action.get("cmd")
    if cmd == "navigation":
        return [action["id"]] if "id" in action else []
    if cmd == "resolve_nearest":
        return action.get("candidate_ids", [])
    if cmd == "answer":
        return action.get("source_ids", [])
    return []


def deterministic_override(
    sub_query: str, action: Optional[dict], category: str
) -> Optional[tuple[bool, str]]:
    """Returns (correct, reason) when code can decide this sub-query, or None to keep
    the LLM judge's verdict."""
    pois = load_pois()
    if action is None:
        return False, "No action was produced for this sub-query."

    ids = _referenced_ids(action)
    unknown = [i for i in ids if i not in pois]
    if unknown:
        return False, f"References ids not in the database: {unknown}."

    if category == "Erroneous prompts":
        if action.get("cmd") == "clarify":
            return True, "Place doesn't exist and the system asked for clarification."
        return False, f"Place doesn't exist, but the system returned '{action.get('cmd')}'."

    rooms = ROOM_RE.findall(sub_query)
    if len(rooms) == 1:
        target = f"room {rooms[0]}".lower()
        match = next((p for p in pois.values() if p["name"].lower() == target), None)
        if match is None:
            ok = action.get("cmd") == "clarify"
            return ok, f"'{target}' isn't in the database; got '{action.get('cmd')}'."
        if action.get("cmd") in ("navigation", "answer"):
            ok = match["id"] in ids
            got = [pois[i]["name"] for i in ids]
            return ok, f"Expected {match['name']} (id {match['id']}), got {got}."
    return None


def _transcript(invocations: list[Invocation]) -> str:
    lines = []
    for i, inv in enumerate(invocations):
        lines.append(f"Turn {i + 1} user: {_text(inv.user_content)}")
        actions = collect_actions(inv)
        reply = json.dumps({"actions": actions}) if actions else _text(inv.final_response)
        lines.append(f"Turn {i + 1} assistant: {reply}")
    return "\n".join(lines)


async def llm_verdict(
    client: genai.Client,
    original_request: str,
    category: str,
    transcript: str,
    final_output: str,
) -> Verdict:
    prompt = (
        "You judge a building-navigation assistant using ONLY the POI database below.\n"
        "1. Split the user's ORIGINAL request into its sub-queries, in the order the user gave "
        "them. Use any clarifications the user gave later in the conversation.\n"
        "2. For each sub-query, decide whether the matching action (same position in the "
        "`actions` list of the FINAL assistant output) is correct, and list every POI id that "
        "would be an acceptable answer.\n\n"
        f"Query category: {category}\n"
        f"Rule for this category: {CATEGORY_RULES.get(category, 'No category rule available.')}\n\n"
        f"POI database:\n{json.dumps(list(load_pois().values()))}\n\n"
        f'Original request:\n"""{original_request}"""\n\n'
        f"Conversation:\n{transcript}\n\n"
        f"Final assistant output:\n{final_output}"
    )
    resp = await client.aio.models.generate_content(
        model=JUDGE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=Verdict,
        ),
    )
    if resp.parsed is not None:
        return resp.parsed
    return Verdict.model_validate_json(resp.text or '{"sub_queries": []}')


def majority(verdicts: list[Verdict]) -> list[SubQueryVerdict]:
    """Majority vote per sub-query, among samples that agree on the sub-query count."""
    count = Counter(len(v.sub_queries) for v in verdicts).most_common(1)[0][0]
    agreeing = [v for v in verdicts if len(v.sub_queries) == count]
    merged = []
    for i in range(count):
        votes = [v.sub_queries[i] for v in agreeing]
        winner = Counter(s.correct for s in votes).most_common(1)[0][0]
        merged.append(next(s for s in votes if s.correct == winner))
    return merged


def encode(correct_flags: list[bool]) -> tuple[float, EvalStatus]:
    if correct_flags and all(correct_flags):
        return 1.0, EvalStatus.PASSED
    if any(correct_flags):
        return 0.5, EvalStatus.FAILED
    return 0.0, EvalStatus.FAILED


async def subquery_correctness(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: Optional[list[Invocation]] = None,
    conversation_scenario: Optional[ConversationScenario] = None,
) -> EvaluationResult:
    if not actual_invocations:
        return EvaluationResult(overall_eval_status=EvalStatus.NOT_EVALUATED)

    original_request = (
        conversation_scenario.starting_prompt
        if conversation_scenario
        else _text(actual_invocations[0].user_content)
    ).strip()
    category = load_categories().get(original_request, "Unknown")

    # Grade the last turn that produced actions, so a closing "thanks" from the
    # simulated user doesn't hide the answer. Other turns aren't graded.
    graded = len(actual_invocations) - 1
    for i in range(len(actual_invocations) - 1, -1, -1):
        if collect_actions(actual_invocations[i]):
            graded = i
            break

    results = [
        PerInvocationResult(actual_invocation=inv, eval_status=EvalStatus.NOT_EVALUATED)
        for i, inv in enumerate(actual_invocations)
        if i != graded
    ]

    final_inv = actual_invocations[graded]
    actions = collect_actions(final_inv)
    if actions:
        final_output = json.dumps({"actions": actions})
    else:
        final_output = _text(final_inv.final_response)  # e.g. a conversational reply
    rubric_scores: list[RubricScore] = []
    flags: list[bool] = []

    if not final_output:
        flags.append(False)
        rubric_scores.append(RubricScore(
            rubric_id="final_response",
            score=0.0,
            rationale="The workflow produced no final response.",
        ))
    else:
        client = genai.Client()
        transcript = _transcript(actual_invocations[: graded + 1])
        samples = [
            await llm_verdict(client, original_request, category, transcript, final_output)
            for _ in range(JUDGE_SAMPLES)
        ]
        sub_verdicts = majority(samples)

        for i, sv in enumerate(sub_verdicts):
            action = actions[i] if i < len(actions) else None
            override = deterministic_override(sv.sub_query, action, category)
            correct, reason = override if override else (sv.correct, sv.reason)
            flags.append(correct)
            rubric_scores.append(RubricScore(
                rubric_id=f"subquery_{i}",
                score=1.0 if correct else 0.0,
                rationale=f"{sv.sub_query!r}: {reason}",
            ))

        if len(actions) > len(sub_verdicts):
            flags.append(False)
            rubric_scores.append(RubricScore(
                rubric_id="extra_actions",
                score=0.0,
                rationale=f"{len(actions) - len(sub_verdicts)} more action(s) than sub-queries.",
            ))

    score, status = encode(flags)
    print(f"[subquery_correctness] {original_request!r} ({category}): {score}")
    results.insert(graded, PerInvocationResult(
        actual_invocation=final_inv,
        score=score,
        eval_status=status,
        rubric_scores=rubric_scores,
    ))

    return EvaluationResult(
        overall_score=score,
        overall_eval_status=status,
        per_invocation_results=results,
        overall_rubric_scores=rubric_scores,
    )


class SubqueryCorrectnessEvaluator(Evaluator):
    """Evaluator wrapper so adk web, which never reads test_config.json, can run the
    judge from ADK's default metric registry."""

    def __init__(self, eval_metric: EvalMetric):
        self._eval_metric = eval_metric

    async def evaluate_invocations(
        self,
        actual_invocations: list[Invocation],
        expected_invocations: Optional[list[Invocation]] = None,
        conversation_scenario: Optional[ConversationScenario] = None,
    ) -> EvaluationResult:
        return await subquery_correctness(
            self._eval_metric,
            actual_invocations,
            expected_invocations,
            conversation_scenario,
        )


DEFAULT_METRIC_EVALUATOR_REGISTRY.register_evaluator(
    MetricInfo(
        metric_name="subquery_correctness",
        description=(
            "Judges navigation actions against the POI database. "
            "1.0 = all sub-queries correct, 0.5 = some correct, 0.0 = none correct."
        ),
        metric_value_info=MetricValueInfo(
            interval=Interval(min_value=0.0, max_value=1.0)
        ),
    ),
    SubqueryCorrectnessEvaluator,
)
