import asyncio
from google.adk import Workflow, Context
from google.adk.workflow import node

from app.AI.triage_agent.schema import TriageAgentOutput, QueryClassifier
from app.database.db import search_poi
from app.poi.models import POI

@node(name="search_poi", rerun_on_resume=True)
async def search_poi_node(
        item: QueryClassifier
) -> list[tuple]:
    query, top_n, fields, filter_expression = item.semantics, 5, None, item.filter
    return search_poi(query, top_n, fields, filter_expression)


@node(name="validate_pois", rerun_on_resume=True)
async def validate_pois(node_input: list[dict]) -> list[POI]:
    collect = []
    for item in node_input:
        try:
            collect.append(POI(**item))
        except TypeError as e:
            raise TypeError(f"Unable to validate POI: {item}!\n{e}")

    return collect

@node(name="router", rerun_on_resume=True)
async def router(
        ctx: Context,
        node_input: TriageAgentOutput
):
    tasks = []
    for item in node_input.targets:
        tasks.append(ctx.run_node(search_poi_node, item))

    results = await asyncio.gather(*tasks)
    return results


workflow = Workflow(
    name="search_agent",
    edges=[
        ("START", )
    ]
)