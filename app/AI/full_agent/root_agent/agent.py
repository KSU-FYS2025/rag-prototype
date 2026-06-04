from google.adk.agents.llm_agent import Agent

from app.AI.full_agent.root_agent.schema import RootOutput

root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='Agent that serves as an entry point to the user',
    instruction='You are a navigational/ conversational agent. Your role is to either respond to users or, if it is'
                'deemed a navigational query, pass it off to the next agent in the chain. You must respond using the'
                ''''following json output as an example:
                {
                    "intent": <str>, MUST BE ONE OF THE FOLLOWING ["navigation_query", "navigation_guidance", "conversational"]
                    "confidence": <number>, How confident you are in the user intent from 0 to 1 (floating point number)
                }''',
    output_schema=RootOutput
)
