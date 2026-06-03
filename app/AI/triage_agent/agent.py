from google.adk.agents.llm_agent import Agent

from app.AI.triage_agent.schema import TriageAgentOutput

triage_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
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
    }''',
    output_key="output_triage",
    output_schema=TriageAgentOutput,
)
