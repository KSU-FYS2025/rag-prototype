from math import sqrt

from google.adk import Workflow, Context, Event, Agent
from google.adk.workflow import node, JoinNode

from app.AI.full_agent.search_agent.schema import DistanceAndVector, DistanceBetweenPOIs, Vector, DistanceOutput, SearchOutput
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput, QueryClassifier
from app.database.db import search_poi
from app.poi.models import POI

@node(name="search_poi", rerun_on_resume=True)
async def search_poi_node(
        node_input: QueryClassifier
) -> Event:
    query, top_n, fields, filter_expression = node_input.semantics, 5, None, node_input.filter
    return Event(output=search_poi(query, top_n, fields, filter_expression))


@node(name="validate_pois", rerun_on_resume=True)
async def validate_pois(
        node_input: list[tuple[dict, float]]
) -> Event:
    collect: list[tuple[POI, float]] = []
    for item, distance in node_input:
        try:
            collect.append((POI(**item), distance))
        except TypeError as e:
            raise TypeError(f"Unable to validate POI: {item}!\n{e}")

    return Event(output=collect)

baseWorkflow = Workflow(
    name="BaseWorkflow",
    edges=[
        ("START", search_poi_node, validate_pois),
    ]
)

@node(name="router", rerun_on_resume=True)
async def parallel_router(
        ctx: Context,
        node_input: TriageAgentOutput
):
    join = JoinNode(name="JoinRouter")

    workflow = Workflow(
        name="Router",
        edges=[
            *[("START", baseWorkflow, join) for _ in node_input.targets],
            (join,)
        ]
    )

    return Event(output=await ctx.run_node(workflow, node_input))

@node(name="distance_calculator", rerun_on_resume=True)
async def distance_calculator(
        node_input: list[list[tuple[POI, float]]]
) -> Event:
    distances: list[DistanceBetweenPOIs] = []
    for query1, query2 in zip(node_input, node_input[1:]):
        for (poi1, _), (poi2, _) in zip(query1, query2):
            distance_vector = Vector(
                dx=poi2.localPosition[0] - poi1.localRotation[0],
                dy=poi2.localPosition[1] - poi1.localRotation[1],
                dz=poi2.localPosition[2] - poi1.localRotation[2]
            )
            distance_scalar = sqrt(distance_vector.dx**2 + distance_vector.dy**2 + distance_vector.dz**2)

            distance_obj = DistanceAndVector(distance=distance_scalar, vector=distance_vector)

            distances.append(DistanceBetweenPOIs(
                poi1=poi1.id,
                poi2=poi2.id,
                distance=distance_obj
            ))

    distance_output = DistanceOutput(
        POIs=node_input,
        distances=distances
    )

    return Event(output=distance_output)

synthesis_agent = Agent(
    model='gemini-2.5-flash',
    name='synthesis agent',
    description='Agent that takes in all the vector search information and creates a path',
    instruction='Take in the data provided to you and create a path between the Points of Interest that most closely'
                'match the user\'s request. Only use the information presented to you within the POI\'s data fields to'
                'reach a conclusion, do not rely on any outside knowledge in your decision making process other than'
                'common sense. If the POI has a room number as its name, the first digit is always the floor of the room'
                'and the second digit is which end of the building it is on. Included in your information is a list of'
                'POIs for each query the user has made, as well as distances between them (only the relevant distances'
                'are included). You must plan a path for the user taking into account their wishes. Inside each entry'
                'inside each nested list is both the POI as well as the semantic similarity to information extracted'
                'from the user\'s query',
    input_schema=DistanceOutput,
    output_schema=SearchOutput
)

search_workflow = Workflow(
    name="SearchWorkflow",
    edges=[
        ("START", parallel_router, distance_calculator, synthesis_agent),
    ]
)
