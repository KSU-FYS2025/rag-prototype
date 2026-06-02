from google.adk.agents.llm_agent import Agent

from app.AI.schema import ValidationAgent
from app.AI.triage_agent.schema import TriageAgentOutput

triage_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='An agent that separates and classifies queries within a full user query',
    instruction='''You are the second agent within a chain meant to provide navigation support. Your role is to take the
    user's query and separate it into separate queries if applicable, and provide meaningful information related to the
    query. The following is the structured json output you MUST follow in your response. Below is the non-minified
    version. You must minify it in your response.
    {
        "targets": [
            {
                "order": <int>, position inside list
                "intent": <str>, MUST BE ONE OF THE FOLLOWING ["navigation_query", "navigation_guidance", "conversational"]
                "target_type": <str>, MUST BE ONE OF THE FOLLOWING ["implicit", "explicit"]. If user directly mentions
                    place, assign to explicit, otherwise should be implicit
                "semantics": <str>, brief information describing the place to be used for vector search
                "source": <str>, should always be "llm"
            },
            ...
        ]
        "extraction_method": <str>, should always be "hybrid"
    }
    
    example data:
    {
        "targets": [
            {
                "order": 1,
                "intent": "navigation",
                "target_type": "specific",
                "semantics": "Room 3117",
                "filter": "name LIKE '%3117%'",
                "source": "llm"
            },
            {
                "order": 2,
                "intent": "navigation",
                "target_type": "generic",
                "semantics": "elevator, lift, 3rd floor",
                "filter": "type == 'Elevator'",
                "source": "llm"
            }
        ],
        "extraction_method": "hybrid"
    }''',
    output_key="output_triage"
)

triage_validation_agent = ValidationAgent(
    name="TriageValidationAgent",
    description="Validates the json output of root_agent",
    state_key="output_intent",
    schema=TriageAgentOutput
)
