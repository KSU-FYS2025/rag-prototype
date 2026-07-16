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
    return Event(output=(results, node_input.user_query), partial=True)


@node(name="validate_pois", rerun_on_resume=True)
async def validate_pois(node_input: tuple[list[tuple[dict, float]], str]) -> Event:
    pois, user_query = node_input
    logging.info(f"validate_pois called with {node_input}")
    collect: list[POIAndSemanticDistance] = []
    for item, distance in pois:
        try:
            logging.info(f"validating poi: {item}")
            collect.append(
                POIAndSemanticDistance(poi=POI(**item), semantic_distance=distance)
            )
        except TypeError as e:
            raise TypeError(f"Unable to validate POI: {item}!\n{e}")

    return Event(
        output=ParallelOutput(POIs=collect, user_query=user_query), partial=True
    )


synthesis_agent = AgentBuilder(
    name="synthesis_agent",
    description="Agent that takes in all the vector search information and creates a path",
    input_schema=ParallelOutput,
    output_schema=Validation,
)
