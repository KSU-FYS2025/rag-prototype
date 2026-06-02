from google.adk.agents.llm_agent import Agent

from app.AI.search_agent.schema import SearchOutput
from app.AI.triage_agent.schema import QueryClassifier

llm_step = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Agent responsible for searching the vector database for POIs.',
    instruction='''You are the third agent within a chain meant to provide navigation support. Your role is to take each
    query provided to you and use the search_poi_tool() tool to find them within the vector database. You will need to
    generate a filter for each one, but that is all the reasoning you are intended to do. The following is the layout of
    the JSON data you will receive.
    {
        "target": {
            "order": <int>, position inside list
            "intent": <str>, MUST BE ONE OF THE FOLLOWING ["navigation_query", "navigation_guidance", "conversational"]
            "target_type": <str>, MUST BE ONE OF THE FOLLOWING ["implicit", "explicit"]. If user directly mentions
                place, assign to explicit, otherwise should be implicit
            "semantics": <str>, brief information describing the place to be used for vector search
            "source": <str>, should always be "llm"
        },
    }
    
    Below is the actual JSON data you must use to formulate your response:
    {output_triage}
    
    The following is the structured json output you MUST follow in your response. Below is the non-minified
    version. You must minify it in your response. Be aware, you must return exactly what the tool returns. The only
    expected deviation is fitting the output within the below schema.
    {
        "validation": {
            "order": <int>, position inside list
            "selected_ids": <list<int>>, id(s) of elements found within vector search
        }
    }
    ''',
    input_schema=QueryClassifier,
    output_schema=SearchOutput,
)
