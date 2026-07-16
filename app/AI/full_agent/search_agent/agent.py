from app.AI.full_agent.search_agent.schema import Validation
import asyncio
import logging
import re

from google.adk import Workflow, Context, Event
from google.adk.workflow import node
from pymilvus import MilvusException

from app.AI.full_agent.agent_builder import AgentBuilder
from app.AI.full_agent.search_agent.schema import (
    POIAndSemanticDistance,
    ParallelOutput,
)
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput, QueryClassifier
from app.database.db import search_poi
from app.poi.models import POI

logging.basicConfig(level=logging.INFO)


def sanitize_filter(filter_expr: str) -> str:
    if not filter_expr:
        return filter_expr

    # Replace single-quoted strings with double-quoted equivalents
    def swap_quotes(match):
        inner = match.group(1).replace("''", "'")  # unescape doubled single quotes
        # In Milvus, if enclosed by double quotes, a double quote within must be \"
        # and a single quote can be ' or \'
        inner = inner.replace('"', '\\"')
        return f'"{inner}"'

    # Pattern matches text between single quotes, allowing for escaped single quotes ''
    return re.sub(r"'((?:[^']|'')*)'", swap_quotes, filter_expr)


@node(name="search_poi", rerun_on_resume=True)
async def search_poi_node(node_input: QueryClassifier) -> Event:
    # logging.info(f"search_poi called with {node_input}")
    query, top_n, fields, filter_expression = (
        node_input.semantics,
        5,
        None,
        node_input.filter,
    )
    results = None
    try:
        if filter_expression:
            try:
                # logging.info(f"Trying search with original filter: {filter_expression}")
                results = search_poi(query, top_n, fields, filter_expression)
            except MilvusException as e:
                sanitized = sanitize_filter(filter_expression)
                # logging.warning(
                #     f"Filter failed, trying sanitized filter: {sanitized}. Error: {e}"
                # )
                results = search_poi(query, top_n, fields, sanitized)
    except Exception as e:
        # logging.error(f"Search with filter failed completely: {e}")
        results = None

    if not results:
        # if filter_expression:
        # logging.info(
        #     f"Search failed or returned no results with filter. Trying without filter."
        # )
        results = search_poi(query, top_n, fields)

    return Event(output=results, partial=True)


@node(name="validate_pois", rerun_on_resume=True)
async def validate_pois(node_input: list[tuple[dict, float]]) -> Event:
    pois = node_input
    # logging.info(f"validate_pois called with {node_input}")
    collect: list[POIAndSemanticDistance] = []
    for item, distance in pois:
        try:
            # logging.info(f"validating poi: {item}")
            collect.append(
                POIAndSemanticDistance(poi=POI(**item), semantic_distance=distance)
            )
        except TypeError as e:
            raise TypeError(f"Unable to validate POI: {item}!\n{e}")

    return Event(output=ParallelOutput(POIs=collect), partial=True)


synthesis_agent = AgentBuilder(
    name="synthesis_agent",
    description="Agent that takes in all the vector search information and creates a path",
    input_schema=ParallelOutput,
    output_schema=Validation,
)
