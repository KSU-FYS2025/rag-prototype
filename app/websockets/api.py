from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Annotated
from google.adk import Runner
from google.genai import types
import logging
from pathlib import Path
import json

from starlette.responses import HTMLResponse

from app.AI.full_agent.actions_agent.schema import ActionsAgentOutput
from app.AI.full_agent.agent import full_workflow
from app.AI.full_agent.clarify_agent.agent import clarify_agent
from app.AI.full_agent.clarify_agent.schema import ClarifyInput
from app.AI.full_agent.actions_agent.schema import Command
from app.AI.full_agent.conversation_agent.schema import ConversationOutput
from app.websockets.session import create_runner
from websocket_route import websocket_route


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
            return await self.process_navigation(message["message"])
        clarify_input = ClarifyInput.model_validate(message)
        return await self.process_clarify(clarify_input)

    async def process_navigation(
        self, message: str
    ) -> ActionsAgentOutput | ConversationOutput | None:
        assert self.full_workflow_runner is not None
        response: ActionsAgentOutput | ConversationOutput | None = None

        async for event in self.full_workflow_runner.run_async(
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
            session_id=self.session_id,
            user_id=self.user_id,
        ):
            if event.is_final_response() and event.author in [
                "actions_agent",
                "conversation_agent",
            ]:
                response = event.output

        if response is None:
            logging.error("no response from navigation agent!")
            return None

        return response

    async def process_clarify(self, message: ClarifyInput) -> Command | None:
        assert self.resolve_clarify_runner is not None
        response: Command | None = None

        async for event in self.resolve_clarify_runner.run_async(
            new_message=types.Content(
                role="user", parts=[types.Part(text=message.model_dump_json())]
            ),
            session_id=self.session_id,
            user_id=self.user_id,
        ):
            if event.is_final_response() and event.author == "":
                response = event.output

        if response is None:
            logging.error("no response from clarification agent!")

        return response


# Super simple audio streaming POC
class AudioSocketHandler:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.chunk_count = 0

    async def handle(self):
        await self.websocket.accept()
        await self.on_connect()

        try:
            while True:
                message = await self.websocket.receive()

                if message.get("bytes") is not None:
                    await self.on_audio_chunk(message["bytes"])
                elif message.get("text") is not None:
                    await self.on_text_message(message["text"])
        except WebSocketDisconnect:
            await self.on_disconnect()

    async def on_connect(self):
        await self.websocket.send_json({"event": "connected"})

    async def on_audio_chunk(self, data: bytes):
        self.chunk_count += 1
        await self.websocket.send_json(
            {"event": "chunk", "seq": self.chunk_count, "bytes": len(data)}
        )

        await self.websocket.send_bytes(data)

    async def on_text_message(self, data: str):
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {"raw": data}

        if payload.get("event") == "stop":
            await self.websocket.send_json(
                {"event": "stopped", "total_chunks": self.chunk_count}
            )

    async def on_disconnect(self):
        pass


router = APIRouter(routes=None)

STATIC_DIR = Path(__file__).parent / "static"


@router.get("/audio/test")
async def index():
    html = (STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)


router.add_api_websocket_route("/ws/AI", websocket_route(NavigationWebsocketHandler))
router.add_api_websocket_route("/ws/audio", websocket_route(AudioSocketHandler))
