from google.adk import Workflow, Agent, Runner
from google.adk.sessions import InMemorySessionService


async def create_runner(
    user_id: str, session_id: str, app_name: str, workflow: Workflow | Agent
) -> Runner:
    session_service = InMemorySessionService()
    runner = Runner(
        app_name=app_name,
        node=workflow,
        session_service=session_service,
    )

    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )

    return runner
