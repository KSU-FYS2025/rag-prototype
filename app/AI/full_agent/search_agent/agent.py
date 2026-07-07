import asyncio
import logging
import re

from google.adk import Workflow, Context, Event, Agent
from google.adk.workflow import node
from pymilvus import MilvusException

from app.AI.full_agent.defaults import planner_defaults
from app.AI.full_agent.search_agent.schema import (
    SearchOutput,
    POIAndSemanticDistance,
    ParallelOutput,
)
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput, QueryClassifier
from app.database.db import search_poi
from app.poi.models import POI

logging.basicConfig(level=logging.INFO)

# logging.getLogger("google_adk").setLevel(logging.DEBUG)
# logging.getLogger("google.adk").setLevel(logging.DEBUG)
# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("opentelemetry").setLevel(logging.WARNING)


def sanitize_filter(filter_expr: str) -> str:
    # Replace single-quoted strings with double-quoted equivalents
    def swap_quotes(match):
        inner = match.group(1).replace("''", "'")  # unescape doubled single quotes
        return f'"{inner}"'

    return re.sub(r"'((?:[^']|'')*)'", swap_quotes, filter_expr)


@node(name="search_poi", rerun_on_resume=True)
async def search_poi_node(node_input: QueryClassifier) -> Event:
    logging.info(f"search_poi called with {node_input}")
    query, top_n, fields, filter_expression = (
        node_input.semantics,
        5,
        None,
        node_input.filter,
    )
    try:
        results = search_poi(query, top_n, fields, filter_expression)
    except MilvusException:
        logging.info(
            f"Filter failed: {filter_expression}\nTrying again with sanitized filter"
        )
        results = search_poi(query, top_n, fields, sanitize_filter(filter_expression))
    if not results:
        logging.info(
            f"search_poi failed with filter: {node_input.filter}\nTrying again without filter"
        )
        results = search_poi(query, top_n, fields)
    return Event(output=results, partial=True)


@node(name="validate_pois", rerun_on_resume=True)
async def validate_pois(node_input: list[tuple[dict, float]]) -> Event:
    logging.info(f"validate_pois called with {node_input}")
    collect: list[POIAndSemanticDistance] = []
    for item, distance in node_input:
        try:
            logging.info(f"validating poi: {item}")
            collect.append(
                POIAndSemanticDistance(poi=POI(**item), semantic_distance=distance)
            )
        except TypeError as e:
            raise TypeError(f"Unable to validate POI: {item}!\n{e}")

    return Event(output=collect, partial=True)


def make_base_workflow(i: int) -> Workflow:
    return Workflow(
        name=f"BaseWorkflow_{i}",
        edges=[
            ("START", search_poi_node, validate_pois),
        ],
    )


@node(name="router", rerun_on_resume=True)
async def parallel_router(ctx: Context, node_input: TriageAgentOutput):
    node_input = TriageAgentOutput.model_validate(node_input.model_dump(mode="json"))
    logging.info(f"parallel_router called with {node_input}")
    workflows = [make_base_workflow(item.order) for item in node_input.targets]

    tasks = [ctx.run_node(wf, item) for wf, item in zip(workflows, node_input.targets)]

    results = await asyncio.gather(*tasks, return_exceptions=False)

    failures = [r for r in results if isinstance(r, Exception)]
    if failures:
        raise RuntimeError(f"One or more sub-workflows failed: {failures}")

    if not isinstance(results[0], list):
        results = [results]

    results_obj = ParallelOutput(
        user_query=node_input.user_query,
        POIs=results,
    )

    return Event(output=results_obj, partial=True)


# @node(name="distance_calculator", rerun_on_resume=True)
# async def distance_calculator(
#         node_input: list[list[POIAndSemanticDistance]]
# ) -> Event:
#     logging.info(f"distance_calculator called with {node_input}")
#     distances: list[DistanceBetweenPOIs] = []
#     for query1, query2 in zip(node_input, node_input[1:]):
#         for poi_semantic1, poi_semantic2 in zip(query1, query2):
#             poi1 = poi_semantic1.poi
#             poi2 = poi_semantic2.poi
#             distance_vector = Vector(
#                 dx=poi2.localPosition[0] - poi1.localRotation[0],
#                 dy=poi2.localPosition[1] - poi1.localRotation[1],
#                 dz=poi2.localPosition[2] - poi1.localRotation[2]
#             )
#             distance_scalar = sqrt(distance_vector.dx**2 + distance_vector.dy**2 + distance_vector.dz**2)
#
#             distance_obj = DistanceAndVector(distance=distance_scalar, vector=distance_vector)
#
#             distances.append(DistanceBetweenPOIs(
#                 poi1=poi1.id,
#                 poi2=poi2.id,
#                 distance=distance_obj
#             ))
#
#     distance_output = DistanceOutput(
#         POIs=node_input,
#         distances=distances
#     )
#
#     logging.info(f"synthesis_agent called with {distance_output}")
#
#     return Event(output=distance_output)

synthesis_agent = Agent(
    model="gemini-2.5-flash",
    name="synthesis_agent",
    description="Agent that takes in all the vector search information and creates a path",
    instruction="Included in your information is a list of POIs for each query the user has made as well as the "
    "semantic distance from the user's query. You must plan a path for the user prioritizing the least "
    "semantic distance. Please take into note: you do not have access to any information about distances "
    "between POIs. DO NOT ASSUME DISTANCE BETWEEN POIs. If the user's query requires distance information, "
    "return a list of POIs that are semantically similar. If there are multiple good candidates for a POI, "
    "you should return all of them, so that the Unity client can decide which is the closest. You are "
    "allowed to return an empty list inside the selected_pois key IF none of the POIs you are given are "
    "close enough. You may decide what close enough is.",
    planner=planner_defaults,
    input_schema=ParallelOutput,
    output_schema=SearchOutput,
)

search_workflow = Workflow(
    name="SearchWorkflow",
    edges=[
        ("START", parallel_router, synthesis_agent),
    ],
)
