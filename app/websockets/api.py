import asyncio

from google.adk.agents import RunConfig, LiveRequestQueue
from google.adk.sessions import InMemorySessionService

from app.AI import audio_relay
from google.adk import Agent
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk import Runner
from google.adk.runners import InMemoryRunner
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


# Super simple audio streaming POC
class SampleAIAudioHandler:
    app_name = "RagPrototype"

    agent = audio_relay.agent.root_agent

    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=InMemorySessionService(),
    )

    test_credentials = {
        "app_name": app_name,
        "user_id": "test_u_2",
        "session_id": "test_s_2",
    }

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.chunk_count = 0

    async def get_session(self):
        session = await self.runner.session_service.get_session(**self.test_credentials)

        if not session:
            await self.runner.session_service.create_session(**self.test_credentials)

        self.run_config = RunConfig(
            response_modalities=["AUDIO"],
            session_resumption=types.SessionResumptionConfig(),
        )

        self.queue = LiveRequestQueue()

    async def handle(self):
        await self.websocket.accept()
        await self.get_session()

        tasks = [
            asyncio.create_task(self.client_stream()),
            asyncio.create_task(self.adk_stream()),
        ]

        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            self.queue.close()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        for task in done:
            if not task.cancelled():
                task.result()

    async def client_stream(self):
        try:
            while True:
                message = await self.websocket.receive()

                if message["type"] == "websocket.disconnect":
                    return

                if message.get("bytes") is not None:
                    self.queue.send_realtime(
                        types.Blob(
                            data=message["bytes"], mime_type="audio/pcm;rate=16000"
                        )
                    )
                elif message.get("text") is not None:
                    payload = json.loads(message["text"])
                    if payload.get("event") == "stop":
                        self.queue.send_audio_stream_end()
                    elif payload.get("event") == "text":
                        self.queue.send_content(
                            types.Content(
                                role="user", parts=[types.Part(text=payload["text"])]
                            )
                        )
        except WebSocketDisconnect:
            return

    async def adk_stream(self):
        async for event in self.runner.run_live(
            user_id=self.test_credentials["user_id"],
            session_id=self.test_credentials["session_id"],
            live_request_queue=self.queue,
            run_config=self.run_config,
        ):
            if event.interrupted:
                await self.websocket.send_json({"event": "interrupted"})

            if event.input_transcription and event.input_transcription.text:
                await self.websocket.send_json(
                    {
                        "event": "user_transcript",
                        "text": event.input_transcription.text,
                    }
                )

            if event.output_transcription and event.output_transcription.text:
                await self.websocket.send_json(
                    {
                        "event": "agent_transcript",
                        "text": event.output_transcription.text,
                    }
                )

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.inline_data and part.inline_data.data:
                        await self.websocket.send_bytes(part.inline_data.data)
            if event.turn_complete:
                await self.websocket.send_json({"event": "turn_complete"})

    async def on_disconnect(self):
        pass


router = APIRouter()

STATIC_DIR = Path(__file__).parent / "static"


@router.get("/audio/test")
async def index():
    html = (STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)


@router.websocket("/ws/AI")
async def ai_websocket(websocket: WebSocket, user_id: str, session_id: str):
    handler = NavigationWebsocketHandler(websocket, user_id, session_id)
    await handler.handle_loop()


@router.websocket("/ws/audio")
async def audio_loopback_websocket(websocket: WebSocket):
    handler = AudioSocketHandler(websocket)
    await handler.handle()


@router.websocket("/ws/AI/live")
async def live_ai_websocket(websocket: WebSocket):
    handler = SampleAIAudioHandler(websocket)
    await handler.handle()


# router.add_api_websocket_route("/ws/AI", websocket_route(NavigationWebsocketHandler))
# router.add_api_websocket_route("/ws/audio", websocket_route(AudioSocketHandler))
