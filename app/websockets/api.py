from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Annotated
from google.adk import Runner
import logging

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.agent import full_workflow
from app.AI.full_agent.clarify_agent.agent import clarify_agent
from app.AI.full_agent.clarify_agent.schema import ClarifyInput
from app.AI.full_agent.actions_agent.schema import Command
from app.websockets.session import create_runner


class NavigationWebsocketHandler:
    app_name = "RagPrototype"

    def __init__(self, websocket: WebSocket, user_id: str, session_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.session_id = session_id
        self.resolve_clarify = False
        self.resolve_clarify_runner: Runner | None = None
        self.full_workflow_runner: Runner | None = None

    async def authenticate(self) -> bool:
        self.resolve_clarify_runner = await create_runner(
            user_id=self.user_id,
            session_id=self.session_id,
            app_name=self.app_name,
            workflow=clarify_agent,
        )
        self.full_workflow_runner = await create_runner(
            user_id=self.user_id,
            session_id=self.session_id,
            app_name=self.app_name,
            workflow=full_workflow,
        )

        await self.websocket.accept()
        return True

    async def handle_loop(self):
        try:
            await self.authenticate()
            while True:
                data = await self.websocket.receive_json()

                response = await self.process_message(data)

                await self.websocket.send_json(response)

        except WebSocketDisconnect:
            await self.websocket.close(code=1000)

        except Exception as ex:
            logging.error(ex)
            await self.websocket.close(code=1011)

    async def process_message(self, message: dict):
        if "message" in message.keys():
            return await self.process_navigation(message)
        clarify_input = ClarifyInput.model_validate(message)
        return await self.process_clarify(clarify_input)

    async def process_navigation(self, message: str):
        assert self.full_workflow_runner is not None
        response: ActionsAgentOutput = await self.full_workflow_runner.run_async(
            message
        )
        return response

    async def process_clarify(self, message: ClarifyInput) -> Command:
        assert self.resolve_clarify_runner is not None
        response: Command = await self.resolve_clarify_runner.run_async(message)
        return response


router = APIRouter(routes=None)


@router.websocket("/ws/AI")
async def ai_websocket(
    websocket: WebSocket,
    user_id: Annotated[
        str, Query(description="The user identifier for the Unity client runner.")
    ],
    session_id: Annotated[
        str, Query(description="The session identifier for the Unity client runner.")
    ],
):
    handler = NavigationWebsocketHandler(websocket, user_id, session_id)
    await handler.handle_loop()
