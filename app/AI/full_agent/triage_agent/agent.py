from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.root_agent.schema import RootOutput
from app.AI.full_agent.triage_agent.schema import TriageAgentOutput

triage_agent = Agent(
    model='gemini-2.5-flash',
    name='triage_agent',
    description='An agent that separates and classifies queries within a full user query',
    instruction='''You are the second agent within a chain meant to provide navigation support. Your role is to take the
    user's query and separate it into separate queries if applicable, and provide meaningful information related to the
    query.
    example data:
    {
        "targets": [
            {
                "order": 1,
                "intent": "navigation",
                "target_type": "specific",
                "semantics": "Room 3117",
                "filter": "name LIKE '%3117%'",
                "source": "LLM"
            },
            {
                "order": 2,
                "intent": "navigation",
                "target_type": "generic",
                "semantics": "elevator, lift, 3rd floor",
                "filter": "type == 'Elevator'",
                "source": "LLM"
            }
        ],
        "extraction_method": "llm"
    }
    An example POI has this format:
        {
            "name": "Room 3416",
            "title": "Room 3416",
            "identification": 154,
            "poiName": "Room 3416",
            "description": "",
            "type": "Room",
            "position": {
                "x": 4.190999984741211,
                "y": 0.2370000034570694,
                "z": -23.670000076293947
            },
            "rotation": {
                "x": 0.0,
                "y": 280.4602355957031,
                "z": 0.0
            },
            "localPosition": {
                "x": 2.2799999713897707,
                "y": 0.2370000034570694,
                "z": -23.670000076293947
            },
            "localRotation": {
                "x": 0.0,
                "y": 280.4602355957031,
                "z": 0.0
            },
            "parentName": "3rd Floor"
        }
    You may reference this format when constructing your filter
    ''',
    input_schema=RootOutput,
    output_schema=TriageAgentOutput,
)
