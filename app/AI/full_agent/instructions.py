from google.adk.agents.readonly_context import ReadonlyContext


def shared_instruction_provider(context: ReadonlyContext) -> str:
    agent_name = context.agent_name
    with open(f"instructions/{agent_name}.md") as f:
        instructions = f.readlines()

    return "\n".join(instructions)
