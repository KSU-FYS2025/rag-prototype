import asyncio
import uuid
from datetime import datetime

from google.adk.agents import RunConfig, LiveRequestQueue
from google.adk.events import Event
from google.genai.errors import APIError
from websockets.exceptions import ConnectionClosed
from google.adk.sessions import InMemorySessionService

from app.AI import audio_relay
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.adk import Runner
from google.genai import types
import logging
import json


class SampleAIAudioHandler:
    app_name = "RagPrototype"

    agent = audio_relay.agent.root_agent

    runner = Runner(
        app_name=app_name,
        agent=agent,
        session_service=InMemorySessionService(),
    )

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.chunk_count = 0
        # Fresh session per connection so stale history (e.g. unanswered
        # function calls) from a previous connection is never replayed.
        self.test_credentials = {
            "app_name": self.app_name,
            "user_id": "test_u_2",
            "session_id": f"test_s_{uuid.uuid4().hex}",
        }

    async def get_session(self):
        session = await self.runner.session_service.get_session(**self.test_credentials)

        if not session:
            await self.runner.session_service.create_session(**self.test_credentials)

        self.run_config = RunConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
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

    @staticmethod
    def _log_event(event: Event):
        ts = datetime.now().isoformat(timespec="milliseconds")

        for fc in event.get_function_calls():
            logging.info(
                f"[{ts}] FUNCTION_CALL id={fc.id} name={fc.name} args={fc.args} "
                f"author={event.author} branch={event.branch} invocation={event.invocation_id}"
            )

        for fr in event.get_function_responses():
            logging.info(
                f"[{ts}] FUNCTION_RESPONSE id={fr.id} name={fr.name} response={fr.response} "
                f"author={event.author} branch={event.branch}"
            )

        if event.interrupted:
            logging.info(f"[{ts}] INTERRUPTED")

        if event.input_transcription and event.input_transcription.text:
            logging.info(
                f"[{ts}] USER_TRANSCRIPT finished={bool(event.input_transcription.finished)} "
                f"text={event.input_transcription.text!r}"
            )

        if event.output_transcription and event.output_transcription.text:
            logging.info(
                f"[{ts}] AGENT_TRANSCRIPT finished={bool(event.output_transcription.finished)} "
                f"text={event.output_transcription.text!r}"
            )

        if event.turn_complete:
            logging.info(f"[{ts}] TURN_COMPLETE")

    async def adk_stream(self):
        try:
            async for event in self.runner.run_live(
                user_id=self.test_credentials["user_id"],
                session_id=self.test_credentials["session_id"],
                live_request_queue=self.queue,
                run_config=self.run_config,
            ):
                self._log_event(event)

                if event.interrupted:
                    await self.websocket.send_json({"event": "interrupted"})

                if event.input_transcription and event.input_transcription.text:
                    await self.websocket.send_json(
                        {
                            "event": "user_transcript",
                            "text": event.input_transcription.text,
                            "finished": bool(event.input_transcription.finished),
                        }
                    )

                if event.output_transcription and event.output_transcription.text:
                    await self.websocket.send_json(
                        {
                            "event": "agent_transcript",
                            "text": event.output_transcription.text,
                            "finished": bool(event.output_transcription.finished),
                        }
                    )

                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.inline_data and part.inline_data.data:
                            await self.websocket.send_bytes(part.inline_data.data)
                if event.turn_complete:
                    await self.websocket.send_json({"event": "turn_complete"})
        except APIError as e:
            logging.error(
                f"[{datetime.now().isoformat(timespec='milliseconds')}] live session APIError "
                f"code={e.code} status={e.status} message={e.message}"
            )
            try:
                await self.websocket.send_json(
                    {"event": "error", "code": e.code, "message": e.message}
                )
            except Exception:
                pass
        except ConnectionClosed as e:
            code = e.rcvd.code if e.rcvd else None
            reason = e.rcvd.reason if e.rcvd else str(e)
            logging.error(
                f"[{datetime.now().isoformat(timespec='milliseconds')}] live connection closed "
                f"code={code} reason={reason}"
            )
            try:
                await self.websocket.send_json(
                    {"event": "error", "code": code, "message": reason}
                )
            except Exception:
                pass

    async def on_disconnect(self):
        pass
